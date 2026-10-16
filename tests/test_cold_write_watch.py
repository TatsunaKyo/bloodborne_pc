"""Exercise actual region/page trackers and write-fault routing on protected host pages."""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
BASE='7f77043936e7e664b57716bc927f424aca96d520'
paths={
 'region':'gpu/shadps4/video_core/buffer_cache/region_manager.h',
 'memory':'gpu/shadps4/video_core/buffer_cache/memory_tracker.h',
 'pages':'gpu/shadps4/video_core/page_manager.cpp',
 'cache':'gpu/shadps4/video_core/buffer_cache/buffer_cache.cpp',
 'raster':'gpu/shadps4/video_core/renderer_vulkan/vk_rasterizer.cpp'}

HARNESS=r'''
#include <algorithm>
#include <array>
#include <atomic>
#include <bit>
#include <cassert>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <memory>
#include <mutex>
#include <span>
#include <thread>
#include <type_traits>
#include <vector>
#include <csignal>
#include <sys/mman.h>
#include <ucontext.h>
#include <unistd.h>
#include "bbport_toggles.h"
extern "C" {uint64_t runtime_disabled_optimizations=0;}
#include "common/bit_array.h"
#include "video_core/buffer_cache/cold_write_watch.h"
#define RENDERER_TRACE ((void)0)
#define LOG_WARNING(...) ((void)0)
#define ASSERT_MSG(x,...) assert(x)
#define ASSERT(x) assert(x)
namespace Common {
using SpinLock=std::mutex;using AdaptiveMutex=std::mutex;
template<class T,class U>auto DivCeil(T a,U b){return (a+b-1)/b;}
template<class T>T AlignDown(T a,T b){return a&~(b-1);}
template<class I>struct RangeLockGuard{
 I first,last;RangeLockGuard(I a,I b):first(a),last(b){for(auto it=a;it!=b;++it)it->lock();}
 ~RangeLockGuard(){for(auto it=first;it!=last;++it)it->unlock();}
};
bool IsWriteError(void* context){return static_cast<ucontext_t*>(context)->uc_mcontext.gregs[REG_ERR]&2;}
}
namespace Core {
enum class MemoryPermission:u8{None=0,Read=1,Write=2};
MemoryPermission operator|(MemoryPermission a,MemoryPermission b){return MemoryPermission(u8(a)|u8(b));}
}
enum GpuReadbacksMode{Disabled=0,Relaxed=1,Precise=2};
struct Settings{u32 mode=Precise;u32 GetReadbacksMode()const{return mode;}};
Settings EmulatorSettings;
namespace VideoCore {class BufferCache;}
namespace Vulkan {
struct Rasterizer {
 VideoCore::BufferCache* cache{};
 bool IsMapped(VAddr,u64);
 bool IsGpuSideThread(){return false;}
 bool OnWriteFault(VAddr,bool=false);
 bool ReadMemory(VAddr,u64,bool=false);
 bool InvalidateMemory(VAddr,u64,bool=false);
 void DrainDrawPipe(){}
};
}
namespace VideoCore {
constexpr size_t PM_PAGE_SIZE=4_KB,PM_PAGE_BITS=12;
class PageManager {
public:
 static constexpr size_t PAGES_PER_LOCK=NUM_PAGES_PER_REGION;
 struct Impl;
 Impl* impl{};bool batch=true;
 template<bool track,bool is_read=false>void UpdatePageWatchersForRegion(VAddr,RegionBits&)const;
 RegionBits ExpandColdWriteWatch(VAddr,const RegionBits&,const RegionBits&)const;
 RegionBits ExpandUploadRange(VAddr,const RegionBits&,const RegionBits&,u64)const{return {};}
};
__IMPL__
template<bool track,bool is_read>void PageManager::UpdatePageWatchersForRegion(VAddr base,RegionBits& bits)const{
 impl->UpdatePageWatchersForRegion<track,is_read>(base,bits);
}
RegionBits PageManager::ExpandColdWriteWatch(VAddr base,const RegionBits& changed,const RegionBits& eligible)const{
 if(!batch)return {};
 return ColdWriteWatch::Expand(base,changed,eligible,[](VAddr a,u64 n){return Impl::rasterizer->IsMapped(a,n);});
}
using LockType=std::mutex;
__REGION__
__MEMORY__
class BufferCache {
public:
 explicit BufferCache(PageManager& page):memory_tracker(std::make_unique<MemoryTracker>(page)){}
 std::unique_ptr<MemoryTracker> memory_tracker;
#ifndef R46_CONTROL
 bool HasPendingCpuUpload(VAddr);
 void ExtendWriteFault(VAddr,bool=false);
#else
 void ExtendWriteFault(VAddr);
#endif
};
__FAULT_CACHE__
}
using namespace VideoCore;
using Core::MemoryPermission;
constexpr VAddr Base=0x1000000;
constexpr u64 Bytes=8_MB,Pages=Bytes/4096;
std::array<bool,Pages> mapped;
u8* guest{};u8* backing{};
std::array<u8,Bytes> gpu;
std::atomic<u64> faults{},protect_calls{};
u64 upload_pages{};
struct Driver:PageManager::Impl {
 void Protect(VAddr a,size_t bytes,MemoryPermission perms)override{
  assert(a>=Base && a+bytes<=Base+Bytes && a%4096==0 && bytes%4096==0);
  ++protect_calls;const int flags=(u8(perms)&1?PROT_READ:0)|(u8(perms)&2?PROT_WRITE:0);
  assert(mprotect(reinterpret_cast<void*>(a),bytes,flags)==0);
 }
};
Vulkan::Rasterizer* raster;
bool Vulkan::Rasterizer::IsMapped(VAddr a,u64 bytes){
 if(a<Base || bytes>Base+Bytes-a || a>=Base+Bytes)return false;
 for(u64 p=(a-Base)/4096;p<(a-Base+bytes+4095)/4096;++p)if(!mapped[p])return false;
 return true;
}
bool Vulkan::Rasterizer::InvalidateMemory(VAddr a,u64 bytes,bool){
 if(!IsMapped(a,bytes))return false;
 auto& t=*cache->memory_tracker;
 t.InvalidateRegion(a,bytes,[&]{
  t.ForEachDownloadRange<true>(a,bytes,[&](VAddr start,u64 size){std::memcpy(backing+start-Base,gpu.data()+start-Base,size);});
  t.MarkRegionAsCpuModified(a,bytes);
 });return true;
}
bool Vulkan::Rasterizer::ReadMemory(VAddr a,u64 bytes,bool){
 if(!IsMapped(a,bytes))return false;
 cache->memory_tracker->ForEachDownloadRange<true>(a,bytes,[&](VAddr start,u64 size){
  std::memcpy(backing+start-Base,gpu.data()+start-Base,size);
 });return true;
}
__FAULT_RASTER__
void Fault(int,siginfo_t* info,void* context){
 ++faults;
 if(!PageManager::Impl::GuestFaultSignalHandler(context,info->si_addr))_exit(81);
}
struct Session {
 Vulkan::Rasterizer r;Driver driver;PageManager pages;BufferCache cache;
 Session():cache(pages){
  assert(mprotect(guest,Bytes,PROT_READ|PROT_WRITE)==0);
  std::memset(backing,0,Bytes);gpu.fill(0);mapped.fill(true);
  pages.impl=&driver;r.cache=&cache;raster=&r;PageManager::Impl::rasterizer=&r;
  faults=0;protect_calls=0;upload_pages=0;
 }
 void Upload(u64 page,u64 count=1,bool gpu_write=false){
  const VAddr a=Base+page*4096;assert(r.IsMapped(a,count*4096));
  cache.memory_tracker->ForEachUploadRange(a,count*4096,gpu_write,[&](VAddr start,u64 size){
   upload_pages+=size/4096;std::memcpy(gpu.data()+start-Base,reinterpret_cast<void*>(start),size);
  },[]{});
 }
 bool Dirty(u64 page){return cache.memory_tracker->IsRegionCpuModified(Base+page*4096,4096);}
 void Write(u64 page,u8 value){volatile u8* ptr=guest+page*4096;*ptr=value;}
 u8 Read(u64 page){volatile const u8* ptr=guest+page*4096;return *ptr;}
};
int main(){
 const int fd=memfd_create("cold-watch-test",0);assert(fd>=0 && ftruncate(fd,Bytes)==0);
 guest=static_cast<u8*>(mmap(reinterpret_cast<void*>(Base),Bytes,PROT_READ|PROT_WRITE,MAP_SHARED|MAP_FIXED_NOREPLACE,fd,0));
 assert(guest==reinterpret_cast<u8*>(Base));
 backing=static_cast<u8*>(mmap(nullptr,Bytes,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0));assert(backing!=MAP_FAILED);close(fd);
 struct sigaction action{};action.sa_sigaction=Fault;action.sa_flags=SA_SIGINFO;sigemptyset(&action.sa_mask);assert(sigaction(SIGSEGV,&action,nullptr)==0);
 {
  Session s;
  for(u64 p=0;p<788;++p){backing[p*4096]=u8(p+1);s.Upload(p);assert(gpu[p*4096]==u8(p+1));}
  assert(upload_pages==788 && !s.Dirty(0) && !s.Dirty(787) && s.Dirty(788));
#ifdef R46_CONTROL
  assert(protect_calls==788);
#else
  assert(protect_calls==50);
#endif
  std::printf("Sequential 788 first-use pages: %llu protection calls, %llu pages uploaded\n",(unsigned long long)protect_calls,(unsigned long long)upload_pages);
 }
 {
  Session s;
  assert(s.Dirty(0)); // create the tracker before a later streaming read fills this region
  s.r.InvalidateMemory(Base,788*4096); // production streaming preparation notification
  for(u64 p=0;p<788;++p)s.Write(p,u8(p+1));
  protect_calls=0;
  for(u64 p=0;p<788;++p){s.Upload(p);assert(gpu[p*4096]==u8(p+1));}
#ifdef R46_CONTROL
  assert(protect_calls==788);
#else
  assert(protect_calls==50);
#endif
  std::printf("Streaming notification before 788 first-use pages: %llu protection calls, %llu pages uploaded\n",(unsigned long long)protect_calls,(unsigned long long)upload_pages);
 }
 {
  Session s;s.Write(0,11);s.Write(1,22);s.Upload(0);auto before=faults.load();s.Write(1,33);s.Write(2,44);
  assert(!s.Dirty(0) && s.Dirty(1) && s.Dirty(2));
#ifdef R46_CONTROL
  assert(faults==before);
#else
  assert(faults==before+1); // release the cold group, retain clean page 0's watch
#endif
  s.Upload(1);s.Upload(2);assert(gpu[4096]==33 && gpu[8192]==44);
  before=faults;s.Write(0,77);assert(faults==before+1 && s.Dirty(0));
  s.Upload(0);assert(gpu[0]==77); // genuine modified data is uploaded again
 }
 {
  Session s;s.Upload(0);
  std::thread a([&]{for(unsigned i=0;i<2000;++i)s.Write(1,u8(i));});
  std::thread b([&]{for(unsigned i=0;i<2000;++i)s.Write(2,u8(i+1));});
  a.join();b.join();assert(!s.Dirty(0));
  s.Upload(1);s.Upload(2);assert(gpu[4096]==u8(1999) && gpu[8192]==u8(2000));
 }
 {
  Session s;mapped[8]=false;s.Upload(0);const auto before=faults.load();
  s.Write(1,5);s.Write(8,9);assert(faults==before); // do not span a GPU-unmapped hole
 }
 {
  Session s;s.Upload(0);s.Upload(1,1,true);gpu[4096]=91;
  assert(s.Read(1)==91); // real read fault/readback and independent GPU watch
  s.Write(1,67);s.Upload(1);assert(gpu[4096]==67);
 }
 {
  Session s;s.Upload(1023);s.Upload(1024);
  s.Write(1025,86);s.Upload(1025);assert(gpu[1025*4096]==86); // tracker boundary
  s.r.InvalidateMemory(Base,4_MB);mapped.fill(false);
  auto before=faults.load();s.Write(0,22);assert(faults==before); // unmap invalidation removes speculative watches
 }
 {
  Session s;u64 rng=0x7359184;
  for(unsigned i=0;i<10000;++i){
   rng=rng*6364136223846793005ull+1;const u64 p=(rng>>32)%512;
   if(rng&4){s.Write(p,u8(rng>>16));}else{
    s.Upload(p);assert(gpu[p*4096]==backing[p*4096]);
   }
  }
 }
 assert(mprotect(guest,Bytes,PROT_READ|PROT_WRITE)==0);
 munmap(guest,Bytes);munmap(backing,Bytes);
 std::puts("PASS: actual trackers/fault routing on protected host pages, first-use upload bytes, speculative fault release, normal writes, map holes, GPU readbacks, region boundaries, unmap and 10000 mixed operations.");
}
'''

def extract(control):
    code={k:(subprocess.check_output(['git','show',BASE+':'+p],cwd=ROOT,text=True)
             if control else (ROOT/p).read_text()) for k,p in paths.items()}
    values={
     '__REGION__':code['region'][code['region'].index('class RegionManager {'):code['region'].rindex('} // namespace')],
     '__MEMORY__':code['memory'][code['memory'].index('class MemoryTracker {'):code['memory'].rindex('} // namespace')],
     '__IMPL__':code['pages'][code['pages'].index('struct PageManager::Impl {'):code['pages'].index('#ifdef __linux__\n// bbport:')].replace('1ULL << (40 - PM_PAGE_BITS)','1ULL << (28 - PM_PAGE_BITS)'),
     '__FAULT_RASTER__':code['raster'][code['raster'].index('bool Rasterizer::OnWriteFault('):code['raster'].index('bool Rasterizer::ReadMemory(')] .replace('bool Rasterizer::','bool Vulkan::Rasterizer::').replace('buffer_cache.','cache->'),
    }
    start=code['cache'].index('void BufferCache::ExtendWriteFault(') if control else code['cache'].index('bool BufferCache::HasPendingCpuUpload(')
    values['__FAULT_CACHE__']=code['cache'][start:code['cache'].index('void BufferCache::ReadMemory(')]
    text=HARNESS
    for key,value in values.items():text=text.replace(key,value)
    return text

if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='bb-cold-watch-') as temp:
        root=Path(temp)
        for control in (True,False):
            name='r46-control' if control else 'grouped'
            cpp=root/(name+'.cpp');cpp.write_text(extract(control));exe=root/name
            cmd=[os.environ.get('CXX','g++'),'-std=c++20','-O2','-pthread',
                 '-I'+str(ROOT/'gpu/shim'),'-I'+str(ROOT/'gpu/shadps4'),str(cpp),'-o',str(exe)]
            if control:cmd.insert(1,'-DR46_CONTROL')
            subprocess.run(cmd,check=True);subprocess.run([str(exe)],check=True)
