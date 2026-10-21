"""Compile Windows segment dispatch and actual Scheduler retirement bodies."""
from pathlib import Path
import os,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1]

def body(text,name):
 start=text.index(name);start=text.rfind('\n',0,start)+1
 a=text.index('{',start);level=1;b=a+1
 while level:
  level+=(text[b]=='{')-(text[b]=='}');b+=1
 return text[start:b]

memory=(ROOT/'src/runtime_memory.c').read_text()
win=r'''
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <cstdio>
#include <vector>
#include <tuple>
using DWORD=uint32_t;
constexpr DWORD PAGE_READONLY=2,PAGE_EXECUTE_READ=32;
constexpr int PROT_READ=1,PROT_WRITE=2,PROT_EXEC=4;
struct HostRegion{uintptr_t start,end;uint64_t phys;int mapped;};
std::vector<HostRegion> regions;
size_t region_count;
size_t region_index(uintptr_t a){size_t i=0;while(i<regions.size()&&regions[i].end<=a)++i;return i;}
DWORD win_prot(int p){return p==PROT_READ?PAGE_READONLY:p==(PROT_EXEC|PROT_READ)?PAGE_EXECUTE_READ:p==0?1:4;}
using Job=std::tuple<uintptr_t,uint64_t,uint32_t>;
std::vector<Job> queued,applied;
unsigned sync_calls;
int host_protect(uintptr_t,uint64_t,int){++sync_calls;return 0;}
std::vector<uintptr_t> domains;
void (*protection_enqueue)(uintptr_t,uint64_t,uint32_t,uintptr_t);
int VirtualProtect(void* a,uint64_t n,DWORD p,DWORD* old){*old=4;applied.emplace_back(uintptr_t(a),n,p);return 1;}
void win_fail(const char*,uintptr_t,uint64_t){std::abort();}
@APPLY@
@DEFER@
int main(){
 regions={{0x100000,0x110000,0,1},{0x110000,0x120000,0,0},{0x120000,0x130000,0,1}};region_count=regions.size();
 protection_enqueue=[](uintptr_t a,uint64_t n,uint32_t p,uintptr_t domain){queued.emplace_back(a,n,p);domains.push_back(domain);};
 assert(!host_protect_deferred(0x101000,0x21000,PROT_READ));
 assert(queued.size()==2 && sync_calls==0);
 assert((domains==std::vector<uintptr_t>{0x100000,0x120000}));
 assert(queued[0]==Job(0x101000,0xf000,PAGE_READONLY));
 assert(queued[1]==Job(0x120000,0x2000,PAGE_READONLY));
 for(auto [a,n,p]:queued)runtime_memory_apply_page_protection(a,n,p);
 assert(applied==queued);queued.clear();
 host_protect_deferred(0x100000,4096,PROT_READ|PROT_EXEC);
 assert(queued.size()==1 && std::get<2>(queued[0])==PAGE_EXECUTE_READ);
 host_protect_deferred(0x100000,4096,PROT_READ|PROT_WRITE);assert(sync_calls==1);
 host_protect_deferred(0x100000,4096,0);assert(sync_calls==2);
 protection_enqueue=nullptr;host_protect_deferred(0x100000,4096,PROT_READ);assert(sync_calls==3);
 puts("PASS: actual Windows dispatcher clips at committed view boundaries, skips placeholders, captures native RO/RX modes, applies captured segments without VMA access, and keeps grants/no-access/disabled mode synchronous.");
}
'''.replace('@APPLY@',body(memory,'void runtime_memory_apply_page_protection(')).replace('@DEFER@',body(memory,'static int host_protect_deferred('))

scheduler=(ROOT/'gpu/shadps4/video_core/renderer_vulkan/vk_scheduler.cpp').read_text()
fence_prefix=r'''
#include "bbport_hitch.h"
#include "bbport_toggles.h"
#include "bbport_page_watch_queue.h"
#include "bbport_copy.h"
#include <array>
#include <cassert>
#include <functional>
#include <memory>
#include <cstdio>
#include <vector>
using u64=uint64_t;
extern "C" {uint64_t runtime_disabled_optimizations=0;}
namespace vk{struct CommandBuffer{};}
struct Scheduler{
 std::atomic<u64> deferred_signals_issued{},host_copies_done{};
 u64 host_copies_issued{};
 std::shared_ptr<std::atomic<u64>> deferred_signals_done=std::make_shared<std::atomic<u64>>();
 bool IsRecordingDeferred(){return true;}
 void KickRecording(bool){}
 std::vector<std::function<void(vk::CommandBuffer)>> commands;
 template<class F>void Record(F&& f){commands.push_back(std::forward<F>(f));}
 void SignalAfterHostCopies(std::function<void()>);
 void WaitHostCopies();
};
@SIGNAL@
@WAIT@
using namespace std::chrono_literals;
void Until(const std::atomic<bool>& flag){
 const auto end=std::chrono::steady_clock::now()+2s;
 while(!flag){assert(std::chrono::steady_clock::now()<end);std::this_thread::yield();}
}
'''
fence_main=r'''
std::atomic<bool> enteredA{},enteredB{},releaseA{},releaseB{};
constexpr uintptr_t A=0x100000,B=0x200000;
void Apply(uintptr_t a,uint64_t,uint32_t){
 if(a==A){enteredA=true;Until(releaseA);}
 if(a==B){enteredB=true;Until(releaseB);}
}
int main(){
 BbPageWatch::Queue<> queue{Apply};BbPageWatch::installed_queue.store(&queue);
 queue.Push(A,4096,2);Until(enteredA);
 unsigned guest=17,copied=0;std::atomic<bool> signaled{},future{},releaseFuture{};
 BbCopy::Async([&]{queue.WaitRange(A,4096);copied=guest;});
 Scheduler s;s.SignalAfterHostCopies([&]{signaled=true;});
 BbCopy::Async([&]{future=true;Until(releaseFuture);});
 queue.Push(B,4096,2);
 for(auto& f:s.commands)f({});
 std::this_thread::sleep_for(15ms);assert(!signaled);
 releaseA=true;Until(enteredB);Until(signaled);
 assert(copied==17 && !releaseB && !releaseFuture && s.deferred_signals_done->load()==1);
 guest=29;releaseFuture=true;BbCopy::WaitAsync();
 std::atomic<bool> drained{};std::thread empty([&]{s.WaitHostCopies();drained=true;});
 Until(drained);empty.join();assert(!releaseB);
 BbCopy::Async([&]{queue.WaitRange(B,4096);copied=guest;});
 drained=false;std::thread relevant([&]{s.WaitHostCopies();drained=true;});
 std::this_thread::sleep_for(15ms);assert(!drained);releaseB=true;relevant.join();assert(copied==29);
 queue.Wait();BbPageWatch::installed_queue.store(nullptr);
 Scheduler stress;
 std::array<std::atomic<bool>,64> gates{},asyncReady{};
 std::array<unsigned,64> input{},snapshot{};std::vector<unsigned> labels;
 for(unsigned i=0;i<64;++i){
  input[i]=100+i;
  BbCopy::Async([&,i]{Until(gates[i]);snapshot[i]=input[i];});
  stress.SignalAfterHostCopies([&,i]{assert(snapshot[i]==100+i);labels.push_back(i);});
  BbCopy::AfterCopies([&,i]{asyncReady[i]=true;});
 }
 for(unsigned i=0;i<64;++i){
  if(!(i&1))stress.commands[i]({});
  gates[i]=true;Until(asyncReady[i]);
  if(i&1)stress.commands[i]({});
  const auto end=std::chrono::steady_clock::now()+2s;
  while(stress.deferred_signals_done->load()<i+1){assert(std::chrono::steady_clock::now()<end);std::this_thread::yield();}
  assert(labels.size()==i+1 && labels.back()==i);input[i]=9000+i;
 }
 BbCopy::WaitAsync();assert(labels.size()==64 && stress.deferred_signals_done->load()==64);
 puts("PASS: actual Scheduler and copy pool join issue-time async/recording prefixes; disjoint watches and future copies do not delay retirement; relevant snapshots remain protected; 64 alternating arrivals preserve FIFO labels and copied values.");
}
'''
epoch_main=r'''
int main(int argc,char**){
 std::atomic<bool> oldStarted{},releaseOld{},oldCopied{},futureStarted{},releaseFuture{},signaled{};
 BbCopy::Async([&]{oldStarted=true;Until(releaseOld);oldCopied=true;});Until(oldStarted);
 Scheduler s;s.SignalAfterHostCopies([&]{assert(oldCopied);signaled=true;});
 BbCopy::Async([&]{futureStarted=true;Until(releaseFuture);});
 for(auto& f:s.commands)f({});assert(!signaled);
 releaseOld=true;Until(oldCopied);Until(futureStarted);
 if(argc>1){std::this_thread::sleep_for(15ms);assert(!signaled);}
 else{Until(signaled);assert(!releaseFuture);}
 releaseFuture=true;BbCopy::WaitAsync();Until(signaled);assert(s.deferred_signals_done->load()==1);
 puts(argc>1?"PASS: actual R49 control incorrectly includes later copies in the fence epoch.":
 "PASS: current actual Scheduler fence retires while a later copy remains deliberately held.");
}
'''
def retirement(source,main):
 return (fence_prefix+main).replace('@SIGNAL@',body(source,'void Scheduler::SignalAfterHostCopies(')).replace('@WAIT@',body(source,'void Scheduler::WaitHostCopies('))
fence=retirement(scheduler,fence_main)
legacy=subprocess.check_output(['git','show','82f0ce54634fbad2a3faeedf1befb2cb7272fe72:gpu/shadps4/video_core/renderer_vulkan/vk_scheduler.cpp'],cwd=ROOT,text=True)
epochs=[('epoch-r49',retirement(legacy,epoch_main)),('epoch-current',retirement(scheduler,epoch_main))]

BATCH=r'''
#include "bbport_page_watch_queue.h"
#include <sys/mman.h>
#include <cassert>
#include <atomic>
#include <tuple>
#include <vector>
#include <cstdio>
using Job=std::tuple<uintptr_t,uint64_t,uint32_t>;
std::vector<Job> calls;
std::atomic<bool> hold{true},entered{};
constexpr uintptr_t Marker=UINTPTR_MAX;
void Apply(uintptr_t a,uint64_t n,uint32_t p){
 if(a==Marker){entered=true;while(hold)std::this_thread::yield();return;}
 assert(!mprotect(reinterpret_cast<void*>(a),n,int(p)));calls.emplace_back(a,n,p);
}
int main(){
 auto* memory=static_cast<uint8_t*>(mmap(nullptr,512*1024,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0));assert(memory!=MAP_FAILED);
 const uintptr_t base=reinterpret_cast<uintptr_t>(memory);
 BbPageWatch::Queue<256> queue{Apply};queue.Push(Marker,1,1);while(!entered)std::this_thread::yield();
 queue.Push(base+8192,4096,PROT_READ,base);queue.Push(base,4096,PROT_READ,base);queue.Push(base+4096,4096,PROT_READ,base);
 queue.Push(base+16384,4096,PROT_READ,base);queue.Push(base+20480,4096,PROT_READ|PROT_EXEC,base);
 queue.Push(base+32768,4096,PROT_READ,base);queue.Push(base+40960,4096,PROT_READ,base);
 queue.Push(base+61440,4096,PROT_READ,base);queue.Push(base+65536,4096,PROT_READ,base+65536);
 auto token=queue.Seal();hold=false;queue.Wait(token);
 assert(calls.size()==7);
 assert(std::find(calls.begin(),calls.end(),Job{base,12288,PROT_READ})!=calls.end());
 assert(std::find(calls.begin(),calls.end(),Job{base+61440,4096,PROT_READ})!=calls.end());
 assert(std::find(calls.begin(),calls.end(),Job{base+65536,4096,PROT_READ})!=calls.end());
 assert(std::find(calls.begin(),calls.end(),Job{base+20480,4096,PROT_READ|PROT_EXEC})!=calls.end());
 calls.clear();hold=true;entered=false;queue.Push(Marker,1,1);while(!entered)std::this_thread::yield();
 for(unsigned i=0;i<64;++i)memory[131072+i*4096]=uint8_t(i+1);
 for(unsigned i=64;i>0;--i)queue.Push(base+131072+(i-1)*4096,4096,PROT_READ,base+131072);
 token=queue.Seal();hold=false;queue.Wait(token);
 assert(calls.size()==1 && calls[0]==Job(base+131072,262144,PROT_READ));
 for(unsigned i=0;i<64;++i)assert(memory[131072+i*4096]==uint8_t(i+1));
 assert(!mprotect(memory,512*1024,PROT_READ|PROT_WRITE));munmap(memory,512*1024);
 puts("PASS: 64 ready contiguous requests become one real mprotect; out-of-order ranges merge only inside one native view and mode; holes/view boundaries/RO versus RX remain separate; sealed fence boundaries are preserved.");
}
'''

with tempfile.TemporaryDirectory(prefix='page-watch-contract-') as temporary:
 root=Path(temporary)
 (root/'common').mkdir()
 (root/'common/thread.h').write_text('#pragma once\n#include <string>\nnamespace Common {inline void SetCurrentThreadName(const std::string&) {}}\n')
 for name,text in [('windows',win),('fence',fence),('batch',BATCH)]+epochs:
  cpp=root/(name+'.cpp');cpp.write_text(text);exe=root/name
  command=[os.environ.get('CXX','g++'),'-std=c++20','-O2','-pthread','-I'+str(root),'-I'+str(ROOT/'gpu/shim'),str(cpp)]
  if name=='fence' or name.startswith('epoch-'):command.append(str(ROOT/'gpu/shim/bbport_copy.cpp'))
  subprocess.run(command+['-o',str(exe)],check=True)
  subprocess.run([str(exe)]+(['control'] if name=='epoch-r49' else []),check=True,timeout=30)
