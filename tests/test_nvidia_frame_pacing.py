# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Exercise production NVIDIA cap translation and the GNM handoff against R34.

The SDK boundary is a CPU model. It checks the exact options and ordering sent
by the application, not the driver's hardware presentation timing.
"""
import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = '1972340d506833adb20367a707d70d57dffdc91e'
spec = importlib.util.spec_from_file_location('token_tests', ROOT/'tests/test_nvidia_token_lifetime.py')
tokens = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tokens)
GNM = 'gpu/shadps4/core/libraries/gnmdriver/gnmdriver.cpp'

SCHEDULE = r'''
using u32=uint32_t;using s32=int32_t;
constexpr s32 ORBIS_OK=0;
namespace BbAmd { void QueueFlip(int,int64_t){} void CancelFlip(int,int64_t){} }
s32 PerformSubmit(u32,const u32**,u32*,const u32**,u32*) {return ORBIS_OK;}
std::mutex gate;
std::condition_variable gate_cv;
std::thread::id first_thread;
bool first_unlocked{},continue_first{};
struct PreemptionMutex {
    std::mutex inner;
    void lock(){inner.lock();}
    void unlock(){
        inner.unlock();
        std::unique_lock lock{gate};
        if(std::this_thread::get_id()==first_thread && !first_unlocked){
            first_unlocked=true;gate_cv.notify_all();
            gate_cv.wait(lock,[]{return continue_first;});
        }
    }
} m_submit_lock;
s32 Submit(int buf_idx,int64_t flip_arg){
    u32 count=0;u32**dcb_gpu_addrs=nullptr;u32*dcb_sizes_in_bytes=nullptr;
    u32**ccb_gpu_addrs=nullptr;u32*ccb_sizes_in_bytes=nullptr;
    std::unique_lock lk{m_submit_lock};
__GNM_TAIL__
}
'''

MAIN = r"""
std::atomic<unsigned> requested_interval{},options_calls{};
bool fail_options{};
sl::Result PacingOptions(const sl::ReflexOptions& options) {
    ++options_calls;requested_interval=options.frameLimitUs;
    return fail_options ? sl::Result::eError : sl::Result::eOk;
}
void Caps() {
    auto& s=BbSettings::Get();
    BbNvidia::reflex_options=&PacingOptions;BbNvidia::reflex_options_applied=false;
    s.frame_generation=BbSettings::FrameGenerationNvidia;s.variable_frame_time=true;
    struct Scenario {int real, output, generated;unsigned effective, interval;};
    const Scenario cases[]{
        {60,120,1,60,8334},{75,130,1,65,7693},{75,0,1,75,6667},
        {75,0,2,75,4445},{60,120,3,30,8334},{0,144,1,72,6945},
        {0,0,1,0,0},{120,0,5,120,1389},{75,225,2,75,4445},
        {-1,120,1,60,8334},{75,130,2,43,7752},{30,0,1,30,16667}
    };
    for (const auto& c:cases) for(int reflex:{0,1,2}) {
        Reset();s.reflex=reflex;s.real_fps_limit=c.real;
        s.limit_generated_fps=c.output>0;s.generated_fps_limit=c.output;
        s.frame_generation_cap_multiplier=c.generated+1;
        BbNvidia::fg_on=true;BbNvidia::configured_generated=c.generated;
        assert(BbSettings::EffectiveFrameLimit(120)==c.effective);
        BbNvidia::NextSimulation();
#if PACED
        assert(requested_interval==c.interval);
        const auto calls=options_calls.load();
        BbNvidia::NextSimulation();assert(options_calls==calls);
        assert(BbNvidia::PacesFrames(c.effective)==(c.interval>0));
        const auto dispatch=VideoPolicy(120);
        assert(dispatch.first==(c.interval ? 0 : c.effective));
        assert(dispatch.second==(c.interval>0));
        if(c.effective) assert(!BbNvidia::PacesFrames(c.effective+1));
        s.nvidia_api_error=true;assert(!BbNvidia::PacesFrames(c.effective));s.nvidia_api_error=false;
        s.frame_generation=BbSettings::FrameGenerationOff;
        assert(!BbNvidia::PacesFrames(c.effective));s.frame_generation=BbSettings::FrameGenerationNvidia;
        s.variable_frame_time=false;assert(!BbNvidia::PacesFrames(c.effective));s.variable_frame_time=true;
        for(int mode:{BbSettings::BackgroundPause,BbSettings::Background30,BbSettings::Background60}) {
            s.background_mode=mode;s.window_focused=false;
            assert(!BbNvidia::PacesFrames(c.effective));
            const auto background=VideoPolicy(120);
            assert(background.first==BbSettings::EffectiveFrameLimit(120) && !background.second);
        }
        s.window_focused=true;s.background_mode=BbSettings::BackgroundRun;
#else
        assert(requested_interval==0);
#endif
    }
    Reset();s.real_fps_limit=60;s.limit_generated_fps=true;s.generated_fps_limit=120;
    s.frame_generation_cap_multiplier=2;BbNvidia::configured_generated=1;BbNvidia::fg_on=true;
    fail_options=true;BbNvidia::NextSimulation();fail_options=false;
#if PACED
    assert(!BbNvidia::PacesFrames(60) && !BbNvidia::simulation_sleeping && !BbNvidia::simulation_pending);
    BbNvidia::NextSimulation();assert(BbNvidia::PacesFrames(60));
    fail_sleep=true;BbNvidia::NextSimulation();fail_sleep=false;
    assert(!BbNvidia::PacesFrames(60) && requested_interval==0);
    BbNvidia::NextSimulation();assert(BbNvidia::PacesFrames(60));
    s.real_fps_limit=45;assert(!BbNvidia::PacesFrames(45));
    BbNvidia::NextSimulation();assert(requested_interval==11112 && BbNvidia::PacesFrames(45));
    s.frame_generation=BbSettings::FrameGenerationOff;
    BbNvidia::Off();assert(requested_interval==0 && !BbNvidia::fg_on && !BbNvidia::PacesFrames(45));
    s.frame_generation=BbSettings::FrameGenerationNvidia;
    BbNvidia::fg_on=true;s.frame_generation_cap_multiplier=2;
    BbNvidia::NextSimulation();assert(BbNvidia::PacesFrames(45));
    s.window_focused=false;s.background_mode=BbSettings::Background30;
    BbNvidia::NextSimulation();assert(requested_interval==0 && !BbNvidia::PacesFrames(30));
    s.window_focused=true;BbNvidia::NextSimulation();assert(BbNvidia::PacesFrames(45));
    std::puts("PASS: production Reflex options preserve 60+60, 65+65, x3/x4/x6, auto/uncapped and arbitrary output ceilings; focus, errors, FG off and live cap changes restore VideoOut ownership; unchanged options avoid driver reconfiguration.");
#else
    std::puts("CONTROL: R34 always sends a zero Reflex interval, leaving capped frames paced only after rendering.");
#endif
#if PACED
    // A swapchain/focus transition can remove the cap while the SDK sleep is
    // unlocked. Its completion must not republish the obsolete policy.
    BbNvidia::Off();Reset();s.real_fps_limit=60;s.limit_generated_fps=true;s.generated_fps_limit=120;
    s.frame_generation_cap_multiplier=2;BbNvidia::fg_on=true;BbNvidia::configured_generated=1;
    {std::scoped_lock lock{sleep_mutex};hold_sleep=true;allow_sleep=false;sleep_entered=false;}
    auto sleeping=std::async(std::launch::async,[]{BbNvidia::NextSimulation();});
    {std::unique_lock lock{sleep_mutex};assert(sleep_cv.wait_for(lock,2s,[]{return sleep_entered;}));}
    assert(!BbNvidia::PacesFrames(60));
    {std::scoped_lock lock{BbNvidia::mutex};BbNvidia::Off();}
    {std::scoped_lock lock{sleep_mutex};allow_sleep=true;sleep_cv.notify_all();}
    assert(sleeping.wait_for(2s)==std::future_status::ready);sleeping.get();
    assert(requested_interval==0 && !BbNvidia::PacesFrames(60));
    assert(VideoPolicy(120).first==60);
    std::puts("PASS: VideoOut defers only the accepted cap; an interrupted Reflex sleep cannot restore an obsolete FG policy.");
#endif
    Reset();s.real_fps_limit=-1;s.limit_generated_fps=false;s.frame_generation_cap_multiplier=0;
    BbNvidia::fg_on=false;
}
int main(){
#ifdef _WIN32
    _putenv_s("BB_FPS_LIMIT","120");_putenv_s("BB_VBLANK_HZ","0");
#else
    setenv("BB_FPS_LIMIT","120",1);setenv("BB_VBLANK_HZ","0",1);
#endif
    Caps();
    BbSettings::Get().reflex=1;
    const auto start=BbNvidia::frame_index+1;
    auto first=std::async(std::launch::async,[]{
        {std::scoped_lock lock{gate};first_thread=std::this_thread::get_id();}
        return Submit(1,1);
    });
    {std::unique_lock lock{gate};assert(gate_cv.wait_for(lock,2s,[]{return first_unlocked;}));}
    auto second=std::async(std::launch::async,[]{return Submit(2,2);});
#if PACED
    assert(second.wait_for(50ms)==std::future_status::timeout);
#else
    assert(second.wait_for(2s)==std::future_status::ready && second.get()==ORBIS_OK);
#endif
    {std::scoped_lock lock{gate};continue_first=true;gate_cv.notify_all();}
    assert(first.wait_for(2s)==std::future_status::ready && first.get()==ORBIS_OK);
#if PACED
    assert(second.wait_for(2s)==std::future_status::ready && second.get()==ORBIS_OK);
#endif
    auto frame1=Finish(1);auto frame2=Finish(2);
    assert(Index(frame1)==start);
#if PACED
    assert(Index(frame2)==start+1);
    std::puts("PASS: production GNM submission reserves the next simulation before unlock; forced preemption preserves consecutive frame tokens.");
#else
    assert(Index(frame2)==start);
    std::puts("CONTROL: R34 assigns two successful flips the same token when preempted at the submission unlock.");
#endif
    Release(frame1);Release(frame2);Reset();
}
"""

def at(path, revision):
    if revision:
        return subprocess.check_output(['git','show',revision+':'+path],cwd=ROOT,text=True)
    return (ROOT/path).read_text()


def prepare(folder):
    folder.mkdir(parents=True,exist_ok=True)
    for name,revision in [('revision34',BASE),('current',None)]:
        source=at(tokens.SOURCE,revision)
        code=tokens.HARNESS.split('int main() {',1)[0]
        start=code.index('namespace BbSettings {')
        end=code.index('u32 BbDisplayRefreshHz()',start)
        code=code[:start]+'#include "bbport_settings.h"\nnamespace BbSettings {auto& settings=Get();}\n'+code[end:]
        code=code.replace('struct FrameToken {', 'enum class DLSSGMode {eOff}; struct DLSSGOptions {DLSSGMode mode{};};\nstruct FrameToken {')
        fg_stub = """
void WaitLatestInputs() {}
int viewport{};
auto fg_options=+[](int,const sl::DLSSGOptions&) {
    assert(!pacing_policy.load());return sl::Result::eOk;
};
struct {void Reset(){}} frame_metrics;
"""
        helpers=tokens.section(source,'void Mark(','void UpdateLatency()')
        off=tokens.section(source,'void Off()','using Matrix=')
        code=code.replace('__HELPERS__',fg_stub+helpers+off)
        code=code.replace('__HANDOFF__',tokens.section(source,'void BeginRender()','void BeforePresent('))
        code=code.replace('__SHUTDOWN__','')
        gnm=at(GNM,revision);start=gnm.index('    BbNvidia::QueueFlip(buf_idx,flip_arg);')
        tail=gnm[start:gnm.index('\n}',start)]
        schedule=SCHEDULE.replace('__GNM_TAIL__',tail)
        driver=at('gpu/shadps4/core/libraries/videoout/driver.cpp',revision)
        start=driver.index('    const auto update_limit = [&] {')
        update=driver[start:driver.index('    std::printf("VideoOut:',start)]
        dispatch = """
std::pair<unsigned,bool> VideoPolicy(unsigned foreground_limit) {
    using u32=uint32_t;
    u32 frame_limit=BbSettings::EffectiveFrameLimit(foreground_limit);
    auto frame_period=std::chrono::nanoseconds(0);
    auto next_flip=std::chrono::steady_clock::now();
    bool reflex_pacing=false;
""" + update + "update_limit();return {frame_limit,reflex_pacing};}\n"

        (folder/(name+'.cpp')).write_text('#define CURRENT 1\n#define PACED '+str(int(not revision))+'\n'+code+schedule+dispatch+MAIN)


def execute(folder):
    compiler=os.environ.get('CXX') or shutil.which('c++') or shutil.which('cl')
    if not compiler:raise RuntimeError('A C++20 compiler is required.')
    msvc=Path(compiler).name.lower() in ('cl','cl.exe')
    for name in ('revision34','current'):
        exe=folder/(name+('.exe' if os.name=='nt' else ''))
        includes=[str(ROOT/p) for p in ('gpu/shim','gpu/shadps4')]
        sources=[str(folder/(name+'.cpp')),str(ROOT/'gpu/shim/bbport_settings.cpp')]
        if msvc:
            cmd=[compiler,'/nologo','/O1','/EHsc','/std:c++20',*('/I'+p for p in includes),*sources,'/Fe:'+str(exe)]
        else:
            cmd=[compiler,'-std=c++20','-O1','-pthread',*('-I'+p for p in includes),*sources,'-o',str(exe)]
        subprocess.run(cmd,cwd=folder,check=True,timeout=60)
        subprocess.run([str(exe)],cwd=ROOT,check=True,timeout=20)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',type=Path)
    args=parser.parse_args()
    if args.prepare:prepare(args.prepare.resolve())
    else:
        with tempfile.TemporaryDirectory(prefix='bb-nvidia-pacing-') as temporary:
            folder=Path(temporary);prepare(folder);execute(folder)
