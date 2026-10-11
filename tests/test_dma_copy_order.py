"""Run production DMA host branches against delayed reads in the real draw/copy queues."""
from pathlib import Path
import argparse
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--compiler', default='g++')
parser.add_argument('--baseline', default='6766a0432c68c3cb43712fd8f0e6a5c70669f8f7')
args = parser.parse_args()
PREFIX = 'gpu/shadps4/video_core/renderer_vulkan/'


def section(text, start, end):
    pos = text.index(start)
    return text[pos:text.index(end, pos)]


waits = (ROOT / (PREFIX+'vk_scheduler.cpp')).read_text()
wait_host = section(waits, 'void Scheduler::WaitHostCopies() {', 'void Scheduler::KickRecording(')
# Release deliberately stalled test copies at the completion boundary, then execute
# the unchanged production wait. This makes the old/new overwrite test deterministic.
wait_host = wait_host.replace('void Scheduler::WaitHostCopies() {',
                             'void Scheduler::WaitHostCopies() { copy_gate.store(true);')
wait_signals = section(waits, 'void Scheduler::WaitDeferredSignals() {', 'void Scheduler::WaitHostCopies(')
scheduler_h = (ROOT / (PREFIX+'vk_scheduler.h')).read_text()
record_copy = section(scheduler_h, '    template <typename Func>\n    void RecordHostCopy(',
                      '    /// bbport: runs `signal`')

fixture = r'''
#include <algorithm>
#include <array>
#include <atomic>
#include <bit>
#include <cassert>
#include <condition_variable>
#include <cstdio>
#include <cstring>
#include <deque>
#include <functional>
#include <memory>
#include <mutex>
#include <span>
#include <thread>
#include <utility>
#include <vector>
#include "bbport_copy.h"
#include "vk_draw_pipe.h"
using VAddr=std::uintptr_t;
extern "C" { std::uint64_t runtime_disabled_optimizations=0; }
namespace BbStats {
std::atomic<u64> host_copies_wait_ns{},copy_threads_wait_ns{},host_copy_waits{};
struct WaitTimer { explicit WaitTimer(std::atomic<u64>&) {} };
}
namespace BbToggle { constexpr u64 OrderedGuestWrites=0; bool Disabled(u64) { return false; } }
namespace vk {
struct CommandBuffer {};
struct BufferCopy { u64 srcOffset,dstOffset,size; };
}
namespace VideoCore { struct Buffer {}; }
struct Scheduler {
    u64 host_copies_issued=0;
    std::atomic<u64> host_copies_done{0},deferred_signals_issued{0};
    std::shared_ptr<std::atomic<u64>> deferred_signals_done=std::make_shared<std::atomic<u64>>(0);
    std::atomic<bool> copy_gate{false};
    std::vector<std::function<void(vk::CommandBuffer)>> pending;
    std::deque<std::function<void(vk::CommandBuffer)>> published;
    std::mutex mutex;
    std::condition_variable cv;
    std::jthread recorder;
    Scheduler() : recorder([this](std::stop_token stop) {
        for(;;) {
            std::function<void(vk::CommandBuffer)> task;
            {
                std::unique_lock lock{mutex};
                cv.wait(lock,[&]{return stop.stop_requested()||!published.empty();});
                if(published.empty()&&stop.stop_requested())return;
                task=std::move(published.front());published.pop_front();
            }
            task({});
        }
    }) {}
    ~Scheduler() { recorder.request_stop();cv.notify_one(); }
    template<class Func> void Record(Func&& task) { pending.emplace_back(std::forward<Func>(task)); }
    @RECORD_COPY@
    void KickRecording(bool) {
        { std::scoped_lock lock{mutex};
          for(auto& task:pending)published.push_back(std::move(task));
          pending.clear(); }
        cv.notify_one();
    }
    void WaitHostCopies();
    void WaitDeferredSignals();
};
@WAIT_HOST@
@WAIT_SIGNALS@
struct BufferCache {
    bool modified=false;
    VideoCore::Buffer buffer;
    bool IsRegionGpuModified(VAddr,u32) const { return modified; }
    const VideoCore::Buffer* GetGdsBuffer() const { return &buffer; }
    std::pair<const VideoCore::Buffer*,u64> ObtainBuffer(VAddr address,u32,bool,bool=false) {
        return {&buffer,address};
    }
};
struct TextureCache {
    void ClearMeta(VAddr) {}
    bool FindImageFromRange(VAddr,u32) const { return false; }
    void InvalidateMemoryFromGPU(VAddr,u32) {}
};
struct Runtime {
    unsigned gpu_fills=0,gpu_copies=0;
    void FillBuffer(const VideoCore::Buffer*,u64,u32,u32) { ++gpu_fills; }
    void CopyBuffer(const VideoCore::Buffer*,const VideoCore::Buffer*,std::span<const vk::BufferCopy>) {
        ++gpu_copies;
    }
};
struct Rasterizer {
    Vulkan::DrawPipe* pipe=nullptr;
    Scheduler scheduler;
    BufferCache buffer_cache;
    TextureCache texture_cache;
    Runtime runtime;
    void DrainDrawPipe() { if(pipe&&!Vulkan::DrawPipe::OnStageB())pipe->Drain(); }
    void FillBuffer(VAddr,u32,u32,bool);
    void CopyBuffer(VAddr,VAddr,u32,bool,bool);
};
@FILL@
@COPY@
struct Command {
    enum Kind { Gate,Read,Write } kind;
    int path=0;
    bool fill=false;
    Rasterizer* r=nullptr;
    const void* source=nullptr;
    void* destination=nullptr;
    const void* replacement=nullptr;
    std::atomic<bool>* gate=nullptr;
};
void SmallCopy(const BbCopy::Item& item) {
    auto* scheduler=static_cast<Scheduler*>(item.context);
    while(!scheduler->copy_gate.load())std::this_thread::yield();
    std::memcpy(reinterpret_cast<void*>(item.destination),
                reinterpret_cast<const void*>(item.source),32);
}
void Record(void*,const u8* data,u32 size) {
    assert(size==sizeof(Command));Command cmd;std::memcpy(&cmd,data,sizeof(cmd));
    if(cmd.kind==Command::Gate) {
        while(!cmd.gate->load())std::this_thread::yield();
        return;
    }
    if(cmd.kind==Command::Write) {
        if(cmd.fill)cmd.r->FillBuffer(VAddr(cmd.source),32,0xeeeeeeee,false);
        else cmd.r->CopyBuffer(VAddr(cmd.source),VAddr(cmd.replacement),32,false,false);
        return;
    }
    if(cmd.path==0)std::memcpy(cmd.destination,cmd.source,32);
    else if(cmd.path==1)BbCopy::QueueCopy({&SmallCopy,&cmd.r->scheduler,
                                         VAddr(cmd.source),VAddr(cmd.destination),32,0});
    else if(cmd.path==2)cmd.r->scheduler.RecordHostCopy([cmd] {
        std::memcpy(cmd.destination,cmd.source,32);
    });
    else BbCopy::Async([cmd] {
        while(!cmd.r->scheduler.copy_gate.load())std::this_thread::yield();
        std::memcpy(cmd.destination,cmd.source,32);
    });
}
void Queue(Vulkan::DrawPipe& pipe,const Command& cmd) {
    std::memcpy(pipe.Begin(sizeof(cmd)),&cmd,sizeof(cmd));pipe.Commit(sizeof(cmd));
}
int main() {
    setenv("BB_COPY_THREADS","2",1);setenv("BB_PIPE_SPIN_US","0",1);
    int corrupted=0,cases=0;
    for(bool stage_b:{false,true})for(bool fill:{false,true})for(int path=0;path<4;++path)
    for(unsigned frame=0;frame<64;++frame) {
        std::array<u32,8> source,snapshot{},replacement;source.fill(1+frame);replacement.fill(0xeeeeeeee);
        auto original=source;
        std::atomic<bool> gate=false;
        Rasterizer r;
        Vulkan::DrawPipe pipe{&Record,nullptr};r.pipe=&pipe;
        // Publish the entire burst before B can consume it. The CPU DMA inside
        // that burst precedes B's end-of-burst TLS publication in the old code.
        Queue(pipe,{Command::Gate,0,false,nullptr,nullptr,nullptr,nullptr,&gate});
        Queue(pipe,{Command::Read,path,false,&r,source.data(),snapshot.data()});
        if(stage_b)Queue(pipe,{Command::Write,0,fill,&r,source.data(),nullptr,replacement.data()});
        gate.store(true);
        if(!stage_b) {
            if(fill)r.FillBuffer(VAddr(source.data()),32,0xeeeeeeee,false);
            else r.CopyBuffer(VAddr(source.data()),VAddr(replacement.data()),32,false,false);
        }
        pipe.Drain();r.scheduler.WaitHostCopies();r.scheduler.WaitDeferredSignals();
        if(snapshot!=original)++corrupted;
        ++cases;assert(source==replacement);
    }
    // GPU-modified and GDS paths must keep recording GPU commands rather than
    // writing the guest pointer or forcing the CPU replacement path.
    Rasterizer r;r.buffer_cache.modified=true;
    r.FillBuffer(0x1000,32,7,false);r.CopyBuffer(0x2000,0x1000,32,false,false);
    r.buffer_cache.modified=false;
    r.FillBuffer(0,32,7,true);r.CopyBuffer(0,0,32,true,true);
    assert(r.runtime.gpu_fills==2&&r.runtime.gpu_copies==2);
    assert(!r.scheduler.copy_gate.load());
    std::printf("CPU DMA replacement cases: %d; corrupted earlier draw snapshots: %d; GPU/GDS paths preserved\n",
                cases,corrupted);
    return corrupted ? 1:0;
}
'''
with tempfile.TemporaryDirectory(prefix='bb-dma-order-') as directory:
    temp=Path(directory)
    (temp/'common').mkdir()
    (temp/'common/types.h').write_text('#pragma once\n#include <cstdint>\nusing u8=std::uint8_t;using u32=std::uint32_t;using u64=std::uint64_t;\n')
    (temp/'common/assert.h').write_text('#pragma once\n#include <cassert>\n#define ASSERT(expr) assert(expr)\n#define ASSERT_MSG(expr,...) assert(expr)\n')
    (temp/'common/thread.h').write_text('#pragma once\nnamespace Common { inline void SetCurrentThreadName(const char*) {} }\n')
    (temp/'vk_draw_pipe.h').write_text((ROOT/(PREFIX+'vk_draw_pipe.h')).read_text())
    for label,old,expected in [('Revision 16',True,1),('production behavior',False,0)]:
        path=PREFIX+'vk_rasterizer.cpp'
        source=(subprocess.check_output(['git','show',args.baseline+':'+path],cwd=ROOT).decode()
                if old else (ROOT/path).read_text())
        fill=section(source,'void Rasterizer::FillBuffer(', 'void Rasterizer::CopyBuffer(')
        copy=section(source,'void Rasterizer::CopyBuffer(', 'u32 Rasterizer::ReadDataFromGds(')
        text=fixture
        for name,replacement in [('RECORD_COPY',record_copy),('WAIT_HOST',wait_host),
                                  ('WAIT_SIGNALS',wait_signals),('FILL',fill),('COPY',copy)]:
            text=text.replace('@'+name+'@',replacement)
        (temp/'fixture.cpp').write_text(text)
        subprocess.run(shlex.split(args.compiler)+['-std=c++23','-O2','-pthread','-Wall','-Wextra','-Werror',
                         '-I'+str(temp),'-I'+str(ROOT/'gpu/shim'),str(temp/'fixture.cpp'),
                         str(ROOT/'gpu/shim/bbport_copy.cpp'),'-o',str(temp/'fixture')],check=True)
        result=subprocess.run([str(temp/'fixture')],capture_output=True,text=True,timeout=60)
        print(label+': '+result.stdout.strip(),flush=True)
        assert result.returncode==expected,(label,result.stdout,result.stderr)
print('PASS: CPU fill/copy completes earlier geometry uploads before replacing their guest source.')
