"""Execute the production upload path and trackers against the shipped R47 control."""
from pathlib import Path
import os, subprocess, tempfile
import test_cold_write_watch as watch
ROOT=watch.ROOT
BASE='61fe9e4e2af43b0c29b7cc39b50a3690ec2b71b0'

def fixture(control):
    original_base=watch.BASE
    watch.BASE=BASE
    try:
        # R47 has the same fault helper surface as current; substitute all its tracker bodies.
        if control:
            # Build directly, without changing tracked source files.
            code={key:subprocess.check_output(['git','show',BASE+':'+path],cwd=ROOT,text=True) for key,path in watch.paths.items()}
            text=watch.HARNESS
            pieces={
                '__REGION__':code['region'][code['region'].index('class RegionManager {'):code['region'].rindex('} // namespace')],
                '__MEMORY__':code['memory'][code['memory'].index('class MemoryTracker {'):code['memory'].rindex('} // namespace')],
                '__IMPL__':code['pages'][code['pages'].index('struct PageManager::Impl {'):code['pages'].index('#ifdef __linux__\n// bbport:')].replace('1ULL << (40 - PM_PAGE_BITS)','1ULL << (28 - PM_PAGE_BITS)'),
                '__FAULT_CACHE__':code['cache'][code['cache'].index('bool BufferCache::HasPendingCpuUpload('):code['cache'].index('void BufferCache::ReadMemory(')],
                '__FAULT_RASTER__':code['raster'][code['raster'].index('bool Rasterizer::OnWriteFault('):code['raster'].index('bool Rasterizer::ReadMemory(')].replace('bool Rasterizer::','bool Vulkan::Rasterizer::').replace('buffer_cache.','cache->'),
            }
            for key,value in pieces.items():text=text.replace(key,value)
        else:
            text=watch.extract(False)
            code={'cache':(ROOT/watch.paths['cache']).read_text()}
    finally:watch.BASE=original_base
    text=text[:text.index('int main(){')]
    text=text.replace('#include "bbport_toggles.h"','#include "bbport_toggles.h"\n#include "bbport_hitch_trace.h"\n#include <functional>\n#include <utility>')
    text=text.replace('namespace VideoCore {class BufferCache;}',r'''
namespace vk {struct BufferCopy {u64 srcOffset,dstOffset,size;};}
namespace boost::container {template<class T,size_t>using small_vector=std::vector<T>;}
namespace VideoCore {
struct Buffer{VAddr cpu_addr=0;std::vector<u8> data;};
extern u8* gpu_output;
extern std::array<bool,2048> resident;
inline u64 batches=0,copy_commands=0,copied_bytes=0;
inline std::vector<std::function<void()>> pending;
struct Runtime{
 void CopyBuffer(const Buffer* src,const Buffer* dst,std::span<vk::BufferCopy> copies){
  ++copy_commands;
  for(auto c:copies){
   const VAddr a=dst->cpu_addr+c.dstOffset;
   assert(a>=0x1000000 && a+c.size<=0x1800000);
   for(u64 p=(a-0x1000000)/4096;p<(a-0x1000000+c.size)/4096;++p)assert(resident[p]);
   assert(c.srcOffset+c.size<=src->data.size());
   pending.push_back([=]{std::memcpy(gpu_output+a-0x1000000,src->data.data()+c.srcOffset,c.size);});
  }
 }
};
class BufferCache;
}
''')
    text=text.replace('RegionBits ExpandUploadRange(VAddr,const RegionBits&,const RegionBits&,u64)const{return {};}',r'''
 RegionBits ExpandUploadRange(VAddr base,const RegionBits& requested,const RegionBits& eligible,u64 bytes)const;
''')
    text=text.replace('class BufferCache {\npublic:',r'''
class BufferCache {
public:
 Runtime runtime;u64 block_size=64_KB;std::deque<Buffer> staging;bool writable_request=false;
 bool SynchronizeMemory(const Buffer*,VAddr,u32,bool,bool);
 bool SynchronizeMemoryFromImage(const Buffer*,VAddr,u32){return false;}
 const Buffer* UploadCopies(const Buffer* arena,std::span<vk::BufferCopy> copies,size_t bytes){
  if(copies.empty())return nullptr;
  ++batches;copied_bytes+=bytes;auto& b=staging.emplace_back();b.data.resize(bytes);
  for(auto& c:copies){const VAddr a=c.dstOffset;auto* dst=b.data.data()+c.srcOffset;
   // Host snapshots precede all guest-visible retirement, as in Scheduler::WaitHostCopies.
   if(writable_request)std::memcpy(dst,reinterpret_cast<void*>(a),c.size);
   else pending.push_back([=]{std::memcpy(dst,reinterpret_cast<void*>(a),c.size);});
   c.dstOffset-=arena->cpu_addr;
  }
  return &b;
 }
''')
    method=code['cache'][code['cache'].index('bool BufferCache::SynchronizeMemory('):code['cache'].index('const Buffer* BufferCache::UploadCopies(')]
    pos=text.index('\nusing namespace VideoCore;')
    text=text[:pos]+'\nnamespace VideoCore {\n'+method+'\n}\n'+text[pos:]
    text=text.replace('std::array<bool,Pages> mapped;','std::array<bool,Pages> mapped,readable;\nnamespace VideoCore {u8* gpu_output;std::array<bool,2048> resident;}')
    text=text.replace('u8* guest{};u8* backing{};','u8* guest{};u8* backing{};\n'+r'''
namespace VideoCore {
RegionBits PageManager::ExpandUploadRange(VAddr base,const RegionBits& requested,const RegionBits& eligible,u64 bytes)const{
 return ColdWriteWatch::Expand(base,requested,eligible,[](VAddr a,u64 n){
  if(!Impl::rasterizer->IsMapped(a,n))return false;
  for(u64 p=(a-Base)/4096;p<(a-Base+n)/4096;++p)if(!readable[p])return false;
  return true;
 },bytes/4096);
}
}
''')
    # The readable hook is independent of GPU mapping and exercises guest-inaccessible padding.
    text=text.replace('pages.impl=&driver;r.cache=&cache;',r'''
  readable.fill(true);resident.fill(false);gpu_output=gpu.data();batches=copy_commands=copied_bytes=0;pending.clear();
  pages.impl=&driver;r.cache=&cache;''')
    start=text.index(' void Upload(u64 page,')
    end=text.index(' bool Dirty(',start)
    text=text[:start]+r'''
 Buffer arena{Base,{}};
 void Complete(){for(auto& f:pending)f();pending.clear();}
 void Upload(u64 page,u64 count=1,bool gpu_write=false,bool texel=false){
  const u64 block_pages=cache.block_size/4096;
  for(u64 p=page/block_pages*block_pages;p<(page+count+block_pages-1)/block_pages*block_pages;++p)resident[p]=true;
  cache.writable_request=gpu_write;
  cache.SynchronizeMemory(&arena,Base+page*4096,count*4096,gpu_write,texel);
 }
 void WriteAll(u64 page,u64 count,u8 seed){
  r.InvalidateMemory(Base+page*4096,count*4096);
  for(u64 p=page;p<page+count;++p){assert(readable[p]);guest[p*4096]=u8(seed+p);}
 }
''' +text[end:]
    return text+MAIN

MAIN=r'''
int main(){
 const int fd=memfd_create("resident-upload-test",0);assert(fd>=0 && ftruncate(fd,Bytes)==0);
 guest=static_cast<u8*>(mmap(reinterpret_cast<void*>(Base),Bytes,PROT_READ|PROT_WRITE,MAP_SHARED|MAP_FIXED_NOREPLACE,fd,0));
 assert(guest==reinterpret_cast<u8*>(Base));
 backing=static_cast<u8*>(mmap(nullptr,Bytes,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0));assert(backing!=MAP_FAILED);close(fd);
 struct sigaction action{};action.sa_sigaction=Fault;action.sa_flags=SA_SIGINFO;sigemptyset(&action.sa_mask);assert(sigaction(SIGSEGV,&action,nullptr)==0);
 {
  Session s;s.Upload(0,800);s.Complete();s.WriteAll(0,780,31);
  protect_calls=0;batches=copy_commands=copied_bytes=0;
  for(u64 resource=0;resource<156;++resource)s.Upload(resource*5,5);
  s.Complete();for(u64 p=0;p<780;++p)assert(gpu[p*4096]==u8(31+p));
  assert(copied_bytes==780*4096);
#ifdef R47_CONTROL
  const bool batched=false;
#else
  const char* policy=std::getenv("BB_PREFETCH_BUFFER_UPLOADS");
  const bool batched=!policy || policy[0]!='0';
#endif
  if(batched)assert(protect_calls<=49 && batches<=49 && copy_commands<=49);
  else assert(protect_calls==156 && batches==156 && copy_commands==156);
  std::printf("Recycled geometry, 156 bindings / 780 pages: %llu protects, %llu staging batches, %llu copy commands, %llu bytes verified\n",(unsigned long long)protect_calls,(unsigned long long)batches,(unsigned long long)copy_commands,(unsigned long long)copied_bytes);
  // A real guest write following host-copy retirement must invalidate prefetched neighbours.
  s.Write(11,199);s.Upload(10,5);s.Complete();assert(gpu[11*4096]==199);
 }
 {
  Session s;mapped[8]=false;s.Upload(0,5);s.Complete();assert(s.Dirty(7));
  assert(copied_bytes==5*4096); // a hole prevents crossing the sparse block
 }
 {
  Session s;readable[8]=false;assert(mprotect(guest+8*4096,4096,PROT_NONE)==0);
  s.Upload(0,5);s.Complete();assert(s.Dirty(7));assert(copied_bytes==5*4096);
  assert(mprotect(guest+8*4096,4096,PROT_READ|PROT_WRITE)==0);
 }
 {
  Session s;s.Upload(8,1,true);s.Complete();gpu[8*4096]=211;
  s.Upload(0,5);s.Complete();assert(gpu[8*4096]==211); // GPU-authored neighbour must survive
  assert(s.Read(8)==211);s.Write(8,201);s.Upload(8);s.Complete();assert(gpu[8*4096]==201);
 }
 {
  Session s;s.Upload(0,5,true);s.Complete();assert(s.Dirty(7));assert(copied_bytes==5*4096);
 }
 {
  Session s;s.Upload(0,5,false,true);s.Complete();assert(s.Dirty(7));assert(copied_bytes==5*4096);
 }
 {
  Session s;s.cache.block_size=16_KB;s.Upload(3,5);s.Complete();
  // Any padding stays inside the sparse blocks actually resident for the request.
  assert(!resident[8]);assert(s.Dirty(8));
  s.Upload(1022,5);s.Complete();s.Write(1024,153);s.Upload(1024);s.Complete();assert(gpu[1024*4096]==153);
 }
 {
  Session s;
  for(unsigned cycle=0;cycle<1000;++cycle){
   s.WriteAll(0,64,u8(cycle));
   for(u64 r=0;r<12;++r)s.Upload(((r*7)%12)*5,5);
   s.Complete();for(u64 p=0;p<60;++p)assert(gpu[p*4096]==u8(cycle+p));
  }
 }
 assert(mprotect(guest,Bytes,PROT_READ|PROT_WRITE)==0);munmap(guest,Bytes);munmap(backing,Bytes);
 std::puts("PASS: production SynchronizeMemory and trackers; recycled contents, bounded existing residency, GPU-written exclusions, guest-inaccessible padding, GPU mapping holes, precise readbacks, writable/texel exclusions, 16/64 KiB blocks, region boundaries, deferred host/GPU copies and 1000 reuse cycles.");
}
'''
if __name__=='__main__':
    with tempfile.TemporaryDirectory(prefix='bb-resident-upload-') as temp:
        root=Path(temp)
        for control in (True,False):
            name='r47-control' if control else 'batched'
            cpp=root/(name+'.cpp');cpp.write_text(fixture(control));exe=root/name
            cmd=[os.environ.get('CXX','g++'),'-std=c++20','-O2','-pthread','-I'+str(ROOT/'gpu/shim'),'-I'+str(ROOT/'gpu/shadps4'),str(cpp),'-o',str(exe)]
            if control:cmd.insert(1,'-DR47_CONTROL')
            subprocess.run(cmd,check=True);subprocess.run([str(exe)],check=True,timeout=60)
            if not control:
                env=dict(os.environ,BB_PREFETCH_BUFFER_UPLOADS='0')
                subprocess.run([str(exe)],env=env,check=True,timeout=60)
