"""Run the refreshed production page/region trackers on protected host mappings.

Uses actual watcher accounting, summary words, dirty transitions and fault
dispatch. GPU execution is replaced by an explicitly completed byte-array copy.
"""
from pathlib import Path
import os
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
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
#include <utility>
#include <csignal>
#include <sys/mman.h>
#include <ucontext.h>
#include <unistd.h>
#include "bbport_toggles.h"
#include "bbport_hitch_trace.h"
#include "common/adaptive_mutex.h"
#include "common/multi_level_page_table.h"
#include "video_core/buffer_cache/region_definitions.h"
extern "C" {uint64_t runtime_disabled_optimizations=0;}
#define RENDERER_TRACE ((void)0)
#define LOG_WARNING(...) ((void)0)
#define ASSERT_MSG(x,...) assert(x)
#define ASSERT(x) assert(x)
namespace Common {
template<class T,class U>auto DivCeil(T a,U b){return (a+b-1)/b;}
template<class T>T AlignDown(T a,T b){return a&~(b-1);}
bool IsWriteError(void* context){return static_cast<ucontext_t*>(context)->uc_mcontext.gregs[REG_ERR]&2;}
}
namespace Core {
enum class MemoryPermission:u8{None=0,Read=1,Write=2};
constexpr MemoryPermission operator|(MemoryPermission a,MemoryPermission b){return MemoryPermission(u8(a)|u8(b));}
}
enum GpuReadbacksMode{Disabled=0,Relaxed=1,Precise=2};
struct Settings{u32 mode=Precise;u32 GetReadbacksMode()const{return mode;}} EmulatorSettings;
namespace VideoCore {class BufferCache;}
namespace Vulkan {struct Rasterizer {
 VideoCore::BufferCache* cache{};
 bool IsMapped(VAddr,u64);bool IsGpuSideThread(){return false;}
 bool OnWriteFault(VAddr,bool=false);bool ReadMemory(VAddr,u64,bool=false);
 bool InvalidateMemory(VAddr,u64,bool=false);void DrainDrawPipe(){}
};}
namespace VideoCore {
enum class PageOp:s8{None=0,Track=1,Untrack=-1};
class PageManager {
public:
 static constexpr u64 PM_PAGE_BITS=12,PM_PAGE_SIZE=4096;
 struct Impl;Impl* impl{};
 static constexpr VAddr GetNextPageAddr(VAddr a){return (a+4096)&~VAddr(4095);}
 void UpdatePageWatchers(VAddr,u64,PageOp)const;
 void UpdatePageWatchersForRegion(VAddr,const Bounds&,const RegionBits&,const RegionBits&,PageOp,PageOp)const;
};
@IMPL@
void PageManager::UpdatePageWatchers(VAddr a,u64 n,PageOp op)const{impl->UpdatePageWatchers(a,n,op);}
void PageManager::UpdatePageWatchersForRegion(VAddr a,const Bounds& b,const RegionBits& w,const RegionBits& r,PageOp wo,PageOp ro)const{
 impl->UpdatePageWatchersForRegion(a,b,w,r,wo,ro);
}
using LockType=Common::AdaptiveMutex;
@REGION@
@MEMORY@
class BufferCache {
public:
 explicit BufferCache(PageManager& pages):memory_tracker(std::make_unique<MemoryTracker>(pages)){}
 std::unique_ptr<MemoryTracker>memory_tracker;
 void ExtendWriteFault(VAddr);
};
@EXTEND@
}
using namespace VideoCore;using Core::MemoryPermission;
constexpr VAddr Base=0x1000000;constexpr u64 Bytes=32_MB,Pages=Bytes/4096;
u8*guest{};u8*backing{};std::vector<u8>gpu(Bytes);
std::atomic<u64>faults{},protects{},uploaded{};
struct Driver:PageManager::Impl {
 void Protect(VAddr a,size_t n,MemoryPermission p)override{
  assert(a>=Base && a+n<=Base+Bytes && a%4096==0 && n%4096==0);++protects;
  int flags=(u8(p)&1?PROT_READ:0)|(u8(p)&2?PROT_WRITE:0);
  assert(mprotect(reinterpret_cast<void*>(a),n,flags)==0);
 }
};
bool Vulkan::Rasterizer::IsMapped(VAddr a,u64 n){return a>=Base && a<Base+Bytes && n<=Base+Bytes-a;}
bool Vulkan::Rasterizer::InvalidateMemory(VAddr a,u64 n,bool){
 if(!IsMapped(a,n))return false;auto& t=*cache->memory_tracker;
 t.InvalidateRegion(a,n,[&]{
  t.ForEachDownloadRange<true>(a,n,[&](VAddr b,u64 bytes){memcpy(backing+b-Base,gpu.data()+b-Base,bytes);});
  t.MarkRegionAsCpuModified(a,n);
 });return true;
}
bool Vulkan::Rasterizer::ReadMemory(VAddr a,u64 n,bool){
 if(!IsMapped(a,n))return false;cache->memory_tracker->ForEachDownloadRange<true>(a,n,[&](VAddr b,u64 bytes){
  memcpy(backing+b-Base,gpu.data()+b-Base,bytes);
 });return true;
}
@FAULT@
void Fault(int,siginfo_t* i,void* context){++faults;if(!PageManager::Impl::GuestFaultSignalHandler(context,i->si_addr))_exit(81);}
struct Session {
 Driver driver;PageManager pages;BufferCache cache;Vulkan::Rasterizer raster;
 Session(u32 mode=Precise):cache((EmulatorSettings.mode=mode,pages)){
  mprotect(guest,Bytes,PROT_READ|PROT_WRITE);memset(backing,0,Bytes);std::fill(gpu.begin(),gpu.end(),0);
  pages.impl=&driver;raster.cache=&cache;PageManager::Impl::rasterizer=&raster;driver.OnMap(Base,Bytes);faults=protects=uploaded=0;
 }
 void Upload(u64 page,u64 count=1,bool written=false){cache.memory_tracker->ForEachUploadRange(Base+page*4096,count*4096,written,[&](VAddr a,u64 n){
  uploaded+=n;memcpy(gpu.data()+a-Base,reinterpret_cast<void*>(a),n);
 });}
 bool Dirty(u64 p){return cache.memory_tracker->IsRegionCpuModified(Base+p*4096,4096);}
 bool GpuDirty(u64 p){return cache.memory_tracker->IsRegionGpuModified(Base+p*4096,4096);}
 void Write(u64 p,u8 n){*static_cast<volatile u8*>(guest+p*4096)=n;std::atomic_signal_fence(std::memory_order_seq_cst);}
 u8 Read(u64 p){auto value=*static_cast<volatile u8*>(guest+p*4096);std::atomic_signal_fence(std::memory_order_seq_cst);return value;}
};
int main(){
 int fd=memfd_create("renderer-tracker",0);assert(fd>=0 && ftruncate(fd,Bytes)==0);
 guest=static_cast<u8*>(mmap(reinterpret_cast<void*>(Base),Bytes,PROT_READ|PROT_WRITE,MAP_SHARED|MAP_FIXED_NOREPLACE,fd,0));assert(guest==reinterpret_cast<void*>(Base));
 backing=static_cast<u8*>(mmap(nullptr,Bytes,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0));assert(backing!=MAP_FAILED);close(fd);
 struct sigaction action{};action.sa_sigaction=Fault;action.sa_flags=SA_SIGINFO;sigemptyset(&action.sa_mask);assert(sigaction(SIGSEGV,&action,nullptr)==0);
 for(u32 mode:{u32(Disabled),u32(Relaxed),u32(Precise)}){
  Session s(mode);s.Write(0,17);s.Upload(0,3);assert(uploaded==3*4096 && gpu[0]==17 && !s.Dirty(0) && s.Dirty(3));
  auto copied=uploaded.load();s.Upload(0,3);assert(uploaded==copied);
  s.Write(1,91);assert(faults==1 && s.Dirty(1));s.Upload(1);assert(gpu[4096]==91 && !s.Dirty(1));
  // Fault window widening never reclassifies GPU-authored neighbours as CPU writes.
  s.Upload(8,1,true);gpu[8*4096]=211;assert(s.GpuDirty(8));s.Write(2,42);assert(s.GpuDirty(8));
  if(mode==Precise){assert(s.Read(8)==211 && !s.GpuDirty(8));}
  // Cross both a 64-page bitmap word and a 16-MiB manager boundary.
  for(u64 p:{63,64,65,4094,4095,4096,4097}){s.Write(p,u8(p+7));s.Upload(p);assert(!s.Dirty(p) && gpu[p*4096]==u8(p+7));}
  // Every store to an uploaded page must fault or have been widened to CPU-dirty.
  u64 random=0x49216;
  for(unsigned i=0;i<10000;++i){random=random*6364136223846793005ULL+1;u64 p=128+(random%7800);u8 v=u8(i+1);
   s.Write(p,v);assert(s.Dirty(p));s.Upload(p);assert(!s.Dirty(p) && gpu[p*4096]==v);}
  printf("PASS: readback mode %u, 10000 real writes, cross-word/region snapshots and GPU neighbour isolation; faults %llu\n",mode,(unsigned long long)faults.load());
 }
 // Two independent owners may watch one page: the first untrack must retain protection.
 {
  Session s;auto p=Base+7*4096;s.pages.UpdatePageWatchers(p,4096,PageOp::Track);auto n=protects.load();
  s.pages.UpdatePageWatchers(p,4096,PageOp::Track);assert(protects==n);
  s.pages.UpdatePageWatchers(p,4096,PageOp::Untrack);assert(protects==n);
  s.pages.UpdatePageWatchers(p,4096,PageOp::Untrack);assert(protects==n+1);
  guest[7*4096]=9;assert(faults==0);
 }
 munmap(guest,Bytes);munmap(backing,Bytes);puts("PASS: overlapping image/buffer watch ownership retained until its last owner releases it.");
}
'''


def method(text, name):
    start = text.index(name)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


def fixture():
    pages = (ROOT / "gpu/shadps4/video_core/page_manager.cpp").read_text()
    impl = pages[pages.index("struct PageManager::Impl {"):pages.index("#ifdef __linux__\n// bbport:")]
    values = {"@IMPL@": impl}
    for key, filename, name in (("@REGION@", "region_manager.h", "class RegionManager {"),
                                ("@MEMORY@", "memory_tracker.h", "class MemoryTracker {")):
        text = (ROOT / "gpu/shadps4/video_core/buffer_cache" / filename).read_text()
        values[key] = text[text.index(name):text.rindex("} // namespace")]
    cache = (ROOT / "gpu/shadps4/video_core/buffer_cache/buffer_cache.cpp").read_text()
    values["@EXTEND@"] = method(cache, "void BufferCache::ExtendWriteFault(")
    raster = (ROOT / "gpu/shadps4/video_core/renderer_vulkan/vk_rasterizer.cpp").read_text()
    values["@FAULT@"] = method(raster, "bool Rasterizer::OnWriteFault(").replace(
        "bool Rasterizer::", "bool Vulkan::Rasterizer::").replace("buffer_cache.", "cache->")
    text = HARNESS
    for key, value in values.items():
        text = text.replace(key, value)
    return text


def main():
    text = fixture()
    with tempfile.TemporaryDirectory(prefix="renderer-tracker-") as temporary:
        cpp = Path(temporary) / "tracker.cpp"
        cpp.write_text(text)
        exe = cpp.with_suffix("")
        subprocess.run([*shlex.split(os.environ.get("CXX", "g++")), "-std=c++23", "-O1", "-UNDEBUG", "-pthread",
                        "-I" + str(ROOT / "gpu/shadps4"), "-I" + str(ROOT / "gpu/shim"),
                        str(cpp), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True, timeout=60)


if __name__ == "__main__":
    main()
