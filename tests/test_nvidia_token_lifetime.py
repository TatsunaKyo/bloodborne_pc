# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Run the production NVIDIA frame handoff against Streamline's six-slot token ring.

The SDK model follows slGetNewFrameToken in Streamline 2.14.1. It exercises
host ownership and thread ordering; it does not execute NVIDIA interpolation.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = 'b4e60b00b7759729e202dfac3f15e10335c49c3e'
SOURCE = 'gpu/shim/bbport_nvidia.cpp'

HARNESS = r'''
#include <array>
#include <atomic>
#include <cassert>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <deque>
#include <future>
#include <functional>
#include <limits>
#include <mutex>
#include <thread>
#include <vector>
#include "bbport_nvidia_tokens.h"
using namespace std::chrono_literals;
namespace sl {
constexpr size_t MAX_FRAMES_IN_FLIGHT=6;
enum class Result { eOk, eError };
enum class PCLMarker { eSimulationStart,eSimulationEnd,eRenderSubmitStart,
                       eRenderSubmitEnd,ePresentStart,ePresentEnd };
enum class ReflexMode { eOff,eLowLatency,eLowLatencyWithBoost };
struct ReflexOptions { ReflexMode mode{}; uint32_t frameLimitUs{}; };
struct FrameToken {
    std::atomic<uint32_t> counter{};
    operator uint32_t() const { return counter.load(); }
};
}
namespace BbSettings {
enum { FrameGenerationOff=0,FrameGenerationNvidia=2,BackgroundRun=0,BackgroundPause=1 };
struct Settings {
    std::atomic<int> reflex{1},frame_generation{FrameGenerationNvidia},background_mode{BackgroundRun};
    std::atomic<bool> show_fps{true},show_latency{false},window_focused{true};
    float pc_latency_ms{};
} settings;
Settings& Get() { return settings; }
}
namespace Vulkan {
struct Frame {
#if CURRENT
    BbNvidia::Token nvidia_token;
#else
    sl::FrameToken* nvidia_token{};
#endif
};
}
std::array<sl::FrameToken,sl::MAX_FRAMES_IN_FLIGHT> sdk_tokens;
size_t sdk_slot{};
std::atomic<unsigned> sdk_allocations{};
bool fail_allocation{};
sl::Result NewToken(sl::FrameToken*& token,const uint32_t* index) {
    if(fail_allocation) return sl::Result::eError;
    // The actual SDK mutates a slot in place, rather than returning a new object.
    if(*index!=uint32_t(sdk_tokens[sdk_slot])) {
        sdk_slot=(sdk_slot+1)%sl::MAX_FRAMES_IN_FLIGHT;
        sdk_tokens[sdk_slot].counter=*index;
        ++sdk_allocations;
    }
    token=&sdk_tokens[sdk_slot];return sl::Result::eOk;
}
std::mutex sleep_mutex;
std::condition_variable sleep_cv;
bool hold_sleep{},sleep_entered{},allow_sleep{};
std::atomic<bool> sleep_active{};
std::atomic<unsigned> shutdown_calls{};
uint32_t sleeping_index{};
sl::Result Sleep(const sl::FrameToken& token) {
    std::unique_lock lock{sleep_mutex};
    sleep_active=true;
    sleeping_index=uint32_t(token);sleep_entered=true;sleep_cv.notify_all();
    if(hold_sleep) sleep_cv.wait(lock,[]{return allow_sleep;});
    assert(uint32_t(token)==sleeping_index);sleep_active=false;return sl::Result::eOk;
}
sl::Result Options(const sl::ReflexOptions& options) {
    assert(options.frameLimitUs==0);
    if(options.mode==sl::ReflexMode::eOff) {
        std::scoped_lock lock{sleep_mutex};allow_sleep=true;sleep_cv.notify_all();
    }
    return sl::Result::eOk;
}
void ShutdownApi() { assert(!sleep_active);++shutdown_calls; }
std::vector<std::pair<sl::PCLMarker,uint32_t>> markers;
sl::Result Marker(sl::PCLMarker marker,const sl::FrameToken& token) {
    markers.emplace_back(marker,uint32_t(token));return sl::Result::eOk;
}
namespace BbNvidia {
std::mutex mutex;
std::atomic<bool> initialized{true},reflex_supported{true};
auto new_token=&NewToken;
auto sleep_api=&Sleep;
auto reflex_options=&Options;
auto marker_api=&Marker;
uint32_t frame_index{};
bool rendering{};
#if CURRENT
TokenPool<sl::MAX_FRAMES_IN_FLIGHT> token_pool;
std::condition_variable simulation_ready;
Token simulation_token;
bool simulation_sleeping{};
struct Flip {int index;int64_t argument;Token token;};
#else
sl::FrameToken* simulation_token{};
struct Flip {int index;int64_t argument;sl::FrameToken* token;};
#endif
std::deque<Flip> flips;
#if CURRENT
auto shutdown_api=&ShutdownApi;
void* device{};
void BeforeSwapchainChange() { token_pool.Notify();simulation_ready.notify_all(); }
#endif
__HELPERS__
__HANDOFF__
__SHUTDOWN__
}
uint32_t Index(const Vulkan::Frame& frame) {
    assert(frame.nvidia_token);
#if CURRENT
    const auto native=static_cast<sl::FrameToken*>(frame.nvidia_token->native);
    assert(uint32_t(*native)==frame.nvidia_token->index);
    return frame.nvidia_token->index;
#else
    return uint32_t(*frame.nvidia_token);
#endif
}
void Release(Vulkan::Frame& frame) {
#if CURRENT
    BbNvidia::RetireFrameToken(&frame);
#else
    frame.nvidia_token=nullptr;
#endif
}
void Start(uint32_t id) { BbNvidia::QueueFlip(int(id%3),id); }
Vulkan::Frame Finish(uint32_t id) {
    Vulkan::Frame frame;BbNvidia::FinishRender(&frame,int(id%3),id);return frame;
}
void Reset() {
    std::scoped_lock lock{BbNvidia::mutex};
    BbNvidia::flips.clear();BbNvidia::simulation_token={};
    BbNvidia::rendering=false;
    BbSettings::settings.window_focused=true;
    BbSettings::settings.background_mode=BbSettings::BackgroundRun;
    hold_sleep=false;sleep_entered=false;allow_sleep=false;
}
int main() {
    // An allowed delayed flip can outlive the SDK's six token allocations.
    Start(1);
    for(uint32_t i=2;i<=6;++i) {BbNvidia::NextSimulation();Start(i);}
    auto advance=std::async(std::launch::async,[]{BbNvidia::NextSimulation();});
#if CURRENT
    assert(advance.wait_for(50ms)==std::future_status::timeout);
    assert(sdk_allocations==6);
    auto first=Finish(1);assert(Index(first)==1);
    {std::scoped_lock lock{BbNvidia::mutex};BbNvidia::Mark(sl::PCLMarker::ePresentEnd,first.nvidia_token);}
    Release(first);assert(advance.wait_for(2s)==std::future_status::ready);advance.get();
    assert(sdk_allocations==7);
    for(uint32_t i=2;i<=6;++i) {auto frame=Finish(i);assert(Index(frame)==i);Release(frame);}
    std::puts("PASS: delayed Present keeps its original token; the seventh SDK allocation waits for retirement.");
#else
    assert(advance.wait_for(2s)==std::future_status::ready);advance.get();
    auto first=Finish(1);assert(Index(first)==7);
    std::puts("CONTROL: unchanged Revision 32 reassigns queued frame 1 to SDK token 7.");
    Reset();
#endif
    Reset();
    // Publish the next simulation before Reflex sleeps, but gate its first
    // render until the sleep finishes. Prior-frame Present must remain usable.
    const uint32_t previous=BbNvidia::frame_index+1;
    Start(previous);auto prior=Finish(previous);
    {std::scoped_lock lock{sleep_mutex};hold_sleep=true;allow_sleep=false;sleep_entered=false;}
    auto next=std::async(std::launch::async,[]{BbNvidia::NextSimulation();});
    {std::unique_lock lock{sleep_mutex};assert(sleep_cv.wait_for(lock,2s,[]{return sleep_entered;}));}
    auto render=std::async(std::launch::async,[]{BbNvidia::BeginRender();});
#if CURRENT
    assert(render.wait_for(50ms)==std::future_status::timeout);
    {
        std::scoped_lock lock{BbNvidia::mutex};
        assert(BbNvidia::simulation_token->index==previous+1);
        BbNvidia::Mark(sl::PCLMarker::ePresentEnd,prior.nvidia_token);
    }
#else
    assert(render.wait_for(2s)==std::future_status::ready);render.get();
    Start(previous+1);auto wrong=Finish(previous+1);assert(Index(wrong)==previous);
    std::puts("CONTROL: unchanged Revision 32 assigns a concurrent render to the previous sleeping simulation.");
#endif
    Release(prior);
    {std::scoped_lock lock{sleep_mutex};allow_sleep=true;sleep_cv.notify_all();}
    assert(next.wait_for(2s)==std::future_status::ready);next.get();
#if CURRENT
    assert(render.wait_for(2s)==std::future_status::ready);render.get();
    Start(previous+1);auto correct=Finish(previous+1);assert(Index(correct)==previous+1);Release(correct);
    std::puts("PASS: render/flip waits for its own Reflex simulation while the prior Present progresses.");
    Reset();
    // Exercise the production handoff repeatedly, with three guest buffers and
    // the SDK ring wrapping many times, then cancellation and missing flips.
    for(const int reflex:{0,1,2}) {
      for(const int provider:{BbSettings::FrameGenerationOff,BbSettings::FrameGenerationNvidia}) {
        if(reflex==0 && provider==BbSettings::FrameGenerationOff) continue;
        BbSettings::settings.reflex=reflex;BbSettings::settings.frame_generation=provider;
        for(unsigned i=0;i<24;++i) {
            const auto expected=BbNvidia::frame_index+(BbNvidia::simulation_token?0:1);
            Start(expected);auto frame=Finish(expected);assert(Index(frame)==expected);
            Release(frame);BbNvidia::NextSimulation();
        }
        Reset();
      }
    }
    BbSettings::settings.reflex=1;
    const auto cancel_id=BbNvidia::frame_index+1;
    Start(cancel_id);BbNvidia::CancelFlip(int(cancel_id%3),cancel_id);
    Vulkan::Frame missing;BbNvidia::FinishRender(&missing,int(cancel_id%3),cancel_id);
    assert(!missing.nvidia_token);Reset();
    // Driver allocation errors do not consume a slot or advance the host ID.
    const auto before=BbNvidia::frame_index;fail_allocation=true;
    BbNvidia::BeginRender();assert(!BbNvidia::simulation_token && BbNvidia::frame_index==before);
    fail_allocation=false;BbNvidia::BeginRender();assert(BbNvidia::simulation_token->index==before+1);Reset();
    BbNvidia::frame_index=UINT32_MAX;BbNvidia::BeginRender();assert(BbNvidia::simulation_token->index==0);
    BbNvidia::NextSimulation();assert(BbNvidia::simulation_token->index==1);Reset();
    // A background transition aborts pressure waits without consuming tokens.
    BbNvidia::BeginRender();
    const auto start=BbNvidia::frame_index;
    for(uint32_t i=0;i<6;++i) {if(i) BbNvidia::NextSimulation();Start(start+i);}
    auto background=std::async(std::launch::async,[]{BbNvidia::NextSimulation();});
    assert(background.wait_for(50ms)==std::future_status::timeout);
    {
        std::scoped_lock lock{BbNvidia::mutex};
        BbSettings::settings.background_mode=BbSettings::BackgroundPause;
        BbSettings::settings.window_focused=false;BbNvidia::token_pool.Notify();
    }
    assert(background.wait_for(2s)==std::future_status::ready);background.get();
    assert(!BbNvidia::simulation_token);
    for(uint32_t i=0;i<6;++i) {auto frame=Finish(start+i);assert(Index(frame)==start+i);Release(frame);}
    Reset();
    {std::scoped_lock lock{sleep_mutex};hold_sleep=true;allow_sleep=false;sleep_entered=false;}
    auto sleeping=std::async(std::launch::async,[]{BbNvidia::NextSimulation();});
    {std::unique_lock lock{sleep_mutex};assert(sleep_cv.wait_for(lock,2s,[]{return sleep_entered;}));}
    BbNvidia::Shutdown();
    assert(sleeping.wait_for(2s)==std::future_status::ready);sleeping.get();
    assert(shutdown_calls==1 && !BbNvidia::initialized && !BbNvidia::simulation_sleeping);
    std::puts("PASS: shutdown disables Reflex and retires an in-flight sleep before SDK shutdown.");
    std::puts("PASS: 120 sequential real frames across Reflex/FG modes, cancellation, allocation failure, index wrap and background cancellation.");
    std::puts("PASS: production NVIDIA token lifetime and simulation/flip ordering.");
#else
    Reset();
#endif
}
'''


def source_at(revision=None):
    if revision:
        return subprocess.check_output(['git', 'show', revision + ':' + SOURCE], cwd=ROOT, text=True)
    return (ROOT / SOURCE).read_text()


def section(source, start, end):
    return source[source.index(start):source.index(end, source.index(start))]


def prepare(folder):
    folder.mkdir(parents=True, exist_ok=True)
    for name, revision in [('revision32', BASE), ('current', None)]:
        source = source_at(revision)
        helpers = section(source, 'void Mark(', 'void UpdateLatency()')
        handoff = section(source, 'void BeginRender()', 'void BeforePresent(')
        shutdown = section(source, 'void Shutdown()', '\n}\n#else') if revision is None else ''
        code = (HARNESS.replace('__HELPERS__', helpers).replace('__HANDOFF__', handoff)
                .replace('__SHUTDOWN__', shutdown))
        (folder / (name + '.cpp')).write_text('#define CURRENT ' + ('0' if revision else '1') + '\n' + code)


def execute(folder):
    compiler = os.environ.get('CXX') or shutil.which('c++') or shutil.which('cl')
    if not compiler:
        raise RuntimeError('A C++20 compiler is required.')
    msvc = Path(compiler).name.lower() in ('cl', 'cl.exe')
    for name in ('revision32', 'current'):
        exe = folder / (name + ('.exe' if os.name == 'nt' else ''))
        include = str(ROOT / 'gpu/shim')
        if msvc:
            command = [compiler, '/nologo', '/O1', '/EHsc', '/std:c++20', '/I' + include,
                       str(folder / (name + '.cpp')), '/Fe:' + str(exe)]
        else:
            command = [compiler, '-std=c++20', '-O1', '-pthread', '-I' + include,
                       str(folder / (name + '.cpp')), '-o', str(exe)]
        subprocess.run(command, check=True, timeout=60, cwd=folder)
        subprocess.run([str(exe)], check=True, timeout=20)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', type=Path)
    args = parser.parse_args()
    if args.prepare:
        prepare(args.prepare.resolve())
    else:
        with tempfile.TemporaryDirectory(prefix='bb-nvidia-tokens-') as temporary:
            folder = Path(temporary)
            prepare(folder)
            execute(folder)
