"""Execute the actual worker, C mapping contract, trackers and protected snapshots."""
from pathlib import Path
import os,subprocess,tempfile
import test_cold_write_watch as watch
ROOT=watch.ROOT
C=r'''
#include "runtime_memory.c"
#include <assert.h>
void fixture_init(int fd,void* backing) {
 pool_fd=dup(fd);backing_base=backing;
 write_lock();assert(!vma_insert(0,(Vma){0x1000000,0x1800000,KIND_DIRECT,0x33,0,0}));write_unlock();
}
void fixture_remap(void) {
 write_lock();assert(!host_map(0x1000000,8*1024*1024,PROT_READ|PROT_WRITE,0,0));write_unlock();
}
void fixture_grant_under_writer(void) {
 write_lock();assert(!host_protect(0x1000000,4096,PROT_READ|PROT_WRITE));write_unlock();
}
'''

def source():
 s=watch.extract(False);s=s[:s.index('int main(){')]
 s=s.replace('extern "C" {uint64_t runtime_disabled_optimizations=0;}',
             'extern "C" {extern uint64_t runtime_disabled_optimizations;}')
 s=s.replace('#include "bbport_toggles.h"',r'''
#include "bbport_toggles.h"
#include "bbport_hitch.h"
#include "bbport_page_watch_queue.h"
#include "common/types.h"
#include <functional>
extern "C" {
 void runtime_memory_apply_page_protection(uintptr_t,uint64_t,uint32_t);
 void runtime_memory_set_protection_hooks(void (*)(uintptr_t,uint64_t,uint32_t,uintptr_t),void (*)());
 void runtime_memory_wait_page_protection();
 void runtime_memory_gpu_protect(uintptr_t,uint64_t,int,int);
 void runtime_memory_gpu_protect_deferred(uintptr_t,uint64_t);
 int runtime_memory_region(uintptr_t,uintptr_t*,uintptr_t*,int*);
 void fixture_init(int,void*);void fixture_remap();void fixture_grant_under_writer();
}
namespace BbCopy {
 bool Enabled(){return false;}
 template<class F>void ParallelFor(size_t n,F&& f){for(size_t i=0;i<n;++i)f(i);}
}
namespace Core {struct MemoryManager {void CopySparseMemory(VAddr,u8*,u64);};}
''')
 bbgpu=(ROOT/'gpu/shim/bbgpu.cpp').read_text()
 serial=bbgpu[bbgpu.index('static void CopySparseSerial('):bbgpu.index('bool MemoryManager::TryWriteBacking(')]
 # This region includes the actual protected snapshot method and WaitForPageProtection.
 serial=serial.replace('void MemoryManager::WaitForPageProtection() {\n    runtime_memory_wait_page_protection();\n}\n','')
 pos=s.index('namespace VideoCore {class BufferCache;}')
 s=s[:pos]+'namespace Core {\n'+serial+'\n}\nCore::MemoryManager snapshots;\n'+s[pos:]
 a=s.index('struct Driver:PageManager::Impl {');b=s.index('\nVulkan::Rasterizer* raster;',a)
 s=s[:a]+r'''
struct Driver:PageManager::Impl {
 void Protect(VAddr a,size_t n,MemoryPermission p)override{
  ++protect_calls;runtime_memory_gpu_protect(a,n,(u8(p)&1)!=0,(u8(p)&2)!=0);
 }
 void ProtectReadOnlyDeferred(VAddr a,size_t n)override{
  ++protect_calls;runtime_memory_gpu_protect_deferred(a,n);
 }
};
''' +s[b:]
 s=s.replace('''std::memcpy(gpu.data()+start-Base,reinterpret_cast<void*>(start),size);''','''snapshots.CopySparseMemory(start,gpu.data()+start-Base,size);''')
 pos=s.index(' bool Dirty(')
 s=s[:pos]+r'''
 std::vector<std::pair<VAddr,u64>> PendingUpload(u64 page,u64 count=1){
  std::vector<std::pair<VAddr,u64>> ranges;
  cache.memory_tracker->ForEachUploadRange(Base+page*4096,count*4096,false,[&](VAddr a,u64 n){ranges.emplace_back(a,n);},[]{});
  return ranges;
 }
 void Snapshot(const std::vector<std::pair<VAddr,u64>>& ranges){
  for(auto [a,n]:ranges)snapshots.CopySparseMemory(a,gpu.data()+a-Base,n);
 }
''' +s[pos:]
 return s+MAIN

MAIN=r'''
using namespace std::chrono_literals;
std::atomic<bool> hold{},entered{};
std::atomic<unsigned> applied{};
std::thread::id producer;
BbPageWatch::Queue<>* queue;
void Apply(uintptr_t a,uint64_t n,uint32_t p){
 assert(std::this_thread::get_id()!=producer);entered=true;
 while(hold.load())std::this_thread::yield();
 runtime_memory_apply_page_protection(a,n,p);++applied;
}
void WaitFor(const std::atomic<bool>& flag){
 auto until=std::chrono::steady_clock::now()+2s;
 while(!flag.load()){assert(std::chrono::steady_clock::now()<until);std::this_thread::yield();}
}
int main(int argc,char**){
 const bool async=argc==1;producer=std::this_thread::get_id();
 const int fd=memfd_create("async-watch-test",0);assert(fd>=0 && ftruncate(fd,Bytes)==0);
 guest=static_cast<u8*>(mmap(reinterpret_cast<void*>(Base),Bytes,PROT_READ|PROT_WRITE,MAP_SHARED|MAP_FIXED_NOREPLACE,fd,0));
 assert(guest==reinterpret_cast<u8*>(Base));
 backing=static_cast<u8*>(mmap(nullptr,Bytes,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0));assert(backing!=MAP_FAILED);
 fixture_init(fd,backing);close(fd);
 struct sigaction action{};action.sa_sigaction=Fault;action.sa_flags=SA_SIGINFO;sigemptyset(&action.sa_mask);assert(sigaction(SIGSEGV,&action,nullptr)==0);
 BbPageWatch::Queue<> service{Apply};queue=&service;
 if(async){
  BbPageWatch::installed_queue.store(queue);
  runtime_memory_set_protection_hooks([](uintptr_t a,uint64_t n,uint32_t p,uintptr_t domain){queue->Push(a,n,p,domain);},[]{queue->Wait();});
 }
 {
  Session s;
  if(async){hold=true;entered=false;}
  auto pending=s.PendingUpload(0);
  if(async)WaitFor(entered);
  s.Write(0,91); // can precede installation; the protected snapshot must include it
  std::atomic<bool> copied{};
  std::thread copier([&]{s.Snapshot(pending);copied=true;});
  if(async){std::this_thread::sleep_for(15ms);assert(!copied.load());hold=false;}
  copier.join();assert(gpu[0]==91);
  s.Write(0,99);assert(s.Dirty(0));s.Upload(0);assert(gpu[0]==99);
 }
 if(async){
  {
   Session s;hold=true;entered=false;s.PendingUpload(0);WaitFor(entered);
   std::atomic<bool> granted{};
   std::thread grant([&]{s.r.InvalidateMemory(Base,4096);granted=true;});
   std::this_thread::sleep_for(15ms);assert(!granted.load());hold=false;grant.join();
   const auto before=faults.load();s.Write(0,77);assert(faults==before);
   queue->Wait();s.Write(0,88);assert(faults==before); // no late stale RO after the grant
  }
  {
   Session s;hold=true;entered=false;s.PendingUpload(0);WaitFor(entered);
   std::atomic<bool> granted{};
   std::thread writer([&]{fixture_grant_under_writer();granted=true;});
   std::this_thread::sleep_for(15ms);assert(!granted.load());hold=false;writer.join();
   const auto before=faults.load();*static_cast<volatile u8*>(guest)=72;assert(faults==before);
  }
  {
   Session s;hold=true;entered=false;s.PendingUpload(0);WaitFor(entered);
   std::atomic<bool> remapped{};
   std::thread mapper([&]{fixture_remap();remapped=true;});
   std::this_thread::sleep_for(15ms);assert(!remapped.load());hold=false;mapper.join();
   queue->Wait();const auto before=faults.load();*static_cast<volatile u8*>(guest)=44;assert(faults==before);
  }
 }
 {
  Session s;
  for(u64 p=0;p<704;++p){auto ranges=s.PendingUpload(p);s.Snapshot(ranges);}
  queue->Wait();
  for(unsigned i=0;i<2000;++i){const unsigned p=(i*37)%704;s.Write(p,u8(i));s.Upload(p);assert(gpu[p*4096]==u8(i));}
  s.Upload(720,1,true);gpu[720*4096]=173;assert(s.Read(720)==173);s.Write(720,201);s.Upload(720);assert(gpu[720*4096]==201);
 }
 queue->Wait();assert(!async || applied>100);
 BbPageWatch::installed_queue.store(nullptr);runtime_memory_set_protection_hooks(nullptr,nullptr);
 assert(mprotect(guest,Bytes,PROT_READ|PROT_WRITE)==0);munmap(guest,Bytes);munmap(backing,Bytes);
 std::printf("PASS: %s actual worker/C runtime/tracker/snapshot integration; %u worker applications; pre-install stores, snapshot dependency, post-snapshot faults, grants/remaps under VMA writer lock, no stale reprotection, precise readbacks and 2000 write/upload cycles.\n",async?"asynchronous":"synchronous control",applied.load());
}
'''

QUEUE=r'''
#include "bbport_page_watch_queue.h"
#include <cassert>
#include <atomic>
#include <vector>
#include <chrono>
#include <cstdio>
using namespace std::chrono_literals;
std::atomic<unsigned> entered{},allow{};
std::vector<unsigned> order;
void Apply(uintptr_t a,uint64_t,uint32_t){
 entered=unsigned(a);while(allow.load()<a)std::this_thread::yield();order.push_back(unsigned(a));
}
int main(){
 BbPageWatch::Queue<2> q{Apply};q.Push(1,4096,1);
 while(entered<1)std::this_thread::yield();
 q.Push(2,4096,1);const auto checkpoint=q.Seal();q.Push(3,4096,1);
 std::atomic<bool> pushed{};std::thread producer([&]{q.Push(4,4096,1);pushed=true;});
 std::this_thread::sleep_for(15ms);assert(!pushed.load());allow=1;
 producer.join();assert(pushed && q.Issued()==4);
 std::atomic<bool> retired{};std::thread retire([&]{q.Wait(checkpoint);retired=true;});
 allow=2;while(entered<3)std::this_thread::yield();
 retire.join();assert(retired && q.Complete()==2); // never waits for later revocations
 allow=4;q.Wait();assert((order==std::vector<unsigned>{1,2,3,4}));
 allow=10000;
 std::vector<std::thread> waiters;
 for(unsigned t=0;t<8;++t)waiters.emplace_back([&,t]{
  for(unsigned i=0;i<400;++i)q.Wait(5+(i*191+t*37)%6000);
 });
 for(unsigned i=5;i<6005;++i)q.Push(i,4096,1);
 for(auto& t:waiters)t.join();q.Wait();
 assert(order.size()==6004);for(unsigned i=0;i<6004;++i)assert(order[i]==i+1);
 std::puts("PASS: 6000-job/eight-waiter wake-up stress, bounded queue backpressure, FIFO order, exact dependency retirement and no waiting for future epochs.");
}
'''

if __name__=='__main__':
 with tempfile.TemporaryDirectory(prefix='bb-async-watch-') as temp:
  root=Path(temp);c=root/'runtime.c';c.write_text(C);obj=root/'runtime.o'
  subprocess.run([os.environ.get('CC','gcc'),'-std=gnu11','-O2','-ffunction-sections','-fdata-sections','-I'+str(ROOT/'src'),'-c',str(c),'-o',str(obj)],check=True)
  for name,body in [('integration',source()),('queue',QUEUE)]:
   cpp=root/(name+'.cpp');cpp.write_text(body);exe=root/name
   cmd=[os.environ.get('CXX','g++'),'-std=c++20','-O2','-pthread','-ffunction-sections','-fdata-sections','-I'+str(ROOT/'gpu/shim'),'-I'+str(ROOT/'gpu/shadps4'),str(cpp)]
   if name=='integration':cmd.append(str(obj))
   cmd+=['-Wl,--gc-sections','-o',str(exe)]
   subprocess.run(cmd,check=True);subprocess.run([str(exe)],check=True,timeout=60)
   if name=='integration':subprocess.run([str(exe),'sync'],check=True,timeout=60)
