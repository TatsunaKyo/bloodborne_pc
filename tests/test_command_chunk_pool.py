"""Hold the actual chunk allocator and verify the recorder can return a chunk."""
from pathlib import Path
import os, subprocess, tempfile
ROOT=Path(__file__).resolve().parents[1]
PATH='gpu/shadps4/video_core/renderer_vulkan/'
header=(ROOT/(PATH+'vk_scheduler.h')).read_text()
chunk=header[header.index('class RecordChunk {'):header.index('\nclass Scheduler {')]
fixture=r'''
#include "bbport_hitch_trace.h"
#include <atomic>
#include <cassert>
#include <cstddef>
#include <cstdlib>
#include <memory>
#include <mutex>
#include <new>
#include <thread>
#include <type_traits>
#include <utility>
#include <vector>
#define ASSERT(x) assert(x)
namespace vk {struct CommandBuffer {};}
namespace BbToggle {constexpr unsigned RecordPrefetch=1;bool Disabled(unsigned){return false;}}
@CHUNK@
thread_local bool stall_allocation;
std::atomic<bool> entered{},release_heap{},returned{};
void* operator new(size_t n,std::align_val_t alignment){
 if(stall_allocation && n==sizeof(RecordChunk)){
  entered=true;while(!release_heap)std::this_thread::yield();
 }
 auto* p=std::aligned_alloc(size_t(alignment),(n+size_t(alignment)-1)&~(size_t(alignment)-1));
 if(!p)throw std::bad_alloc();return p;
}
void operator delete(void* p,std::align_val_t)noexcept{std::free(p);}
void operator delete(void* p,size_t,std::align_val_t)noexcept{std::free(p);}
struct Scheduler{
 std::mutex recorder_mutex;
 std::vector<std::unique_ptr<RecordChunk>> free_chunks;
 std::unique_ptr<RecordChunk> AcquireChunk();
};
@ACQUIRE@
void Until(const std::atomic<bool>& flag){
 const auto end=std::chrono::steady_clock::now()+std::chrono::seconds(2);
 while(!flag){assert(std::chrono::steady_clock::now()<end);std::this_thread::yield();}
}
int main(int argc,char**){
 Scheduler s;auto spare=std::make_unique<RecordChunk>();auto* original=spare.get();
 std::unique_ptr<RecordChunk> allocated;
 std::thread producer([&]{stall_allocation=true;allocated=s.AcquireChunk();});Until(entered);
 std::thread recorder([&]{std::scoped_lock lock{s.recorder_mutex};s.free_chunks.push_back(std::move(spare));returned=true;});
 if(argc>1){std::this_thread::sleep_for(std::chrono::milliseconds(20));assert(!returned);}
 else {Until(returned);assert(!release_heap);}
 release_heap=true;producer.join();recorder.join();assert(allocated->Empty() && !allocated->Size());
 unsigned called=0;assert(allocated->Push([&](vk::CommandBuffer){++called;}));
 allocated->Execute({});assert(called==1 && allocated->Empty() && !allocated->Size());
 assert(s.AcquireChunk().get()==original);
 std::puts(argc>1?"PASS: R49 control blocks the recorder behind chunk allocation.":
 "PASS: current actual AcquireChunk allocates outside the recorder mutex; recycling and command initialization survive held heap allocation.");
}
'''.replace('@CHUNK@',chunk)
with tempfile.TemporaryDirectory(prefix='chunk-pool-') as temporary:
 for legacy in (True,False):
  source=subprocess.check_output(['git','show','82f0ce54634fbad2a3faeedf1befb2cb7272fe72:'+PATH+'vk_scheduler.cpp'],cwd=ROOT,text=True) if legacy else (ROOT/(PATH+'vk_scheduler.cpp')).read_text()
  start=source.index('std::unique_ptr<RecordChunk> Scheduler::AcquireChunk()')
  acquire=source[start:source.index('\nvoid Scheduler::SignalAfterHostCopies',start)]
  cpp=Path(temporary)/('old.cpp' if legacy else 'new.cpp');cpp.write_text(fixture.replace('@ACQUIRE@',acquire));exe=cpp.with_suffix('')
  subprocess.run([os.environ.get('CXX','g++'),'-std=c++20','-O2','-pthread','-I'+str(ROOT/'gpu/shim'),str(cpp),'-o',str(exe)],check=True)
  subprocess.run([str(exe)]+(['control'] if legacy else []),check=True,timeout=15)
