"""Execute bounded vertex uploads with the production refreshed page trackers."""
from pathlib import Path
import os
import shlex
import subprocess
import tempfile
import test_renderer_memory_refresh as refresh

ROOT = refresh.ROOT
text = refresh.fixture()
text = text[:text.index("int main(){")]
text = text.replace('#include "bbport_hitch_trace.h"', '''
#include "bbport_hitch_trace.h"
#include "common/types.h"
#include "video_core/buffer_cache/vertex_fetch_range.h"
#include <tuple>
namespace vk {struct BufferCopy {u64 srcOffset,dstOffset,size;};}
namespace boost::container {template<class T,size_t>using small_vector=std::vector<T>;}
extern std::vector<u8> gpu;
std::vector<bool> resident(8192);
u64 copied_bytes=0;
''')
text = text.replace("class BufferCache {\npublic:", r'''
struct Buffer{VAddr cpu_addr=0;std::vector<u8> data;u64 Offset(VAddr a)const{return a-cpu_addr;}};
struct Runtime {void CopyBuffer(const Buffer* src,const Buffer* dst,std::span<vk::BufferCopy> copies){
 for(auto c:copies){assert(c.srcOffset+c.size<=src->data.size());
  for(u64 p=c.dstOffset/4096;p<(c.dstOffset+c.size+4095)/4096;++p)assert(resident[p]);
  memcpy(gpu.data()+c.dstOffset,src->data.data()+c.srcOffset,c.size);
 }
}};
class BufferCache {
public:
 static constexpr u64 STREAM_THRESHOLD=16_KB;
 u32 block_shift=16;Buffer arena{0x1000000,{}};Runtime runtime;std::deque<Buffer> staging;
 const Buffer* GetArena(u64,u64){return &arena;}
 void EnsureResident(const Buffer* buffer,u64 first,u64 last){
  for(u64 b=first;b<=last;++b)for(u64 p=0;p<16;++p)resident[((b<<16)-buffer->cpu_addr)/4096+p]=true;
 }
 std::pair<const Buffer*,u64> ObtainBuffer(VAddr a,u32 n){
  EnsureResident(&arena,a>>16,(a+n-1)>>16);SynchronizeMemory(&arena,a,n,false,false);return {&arena,arena.Offset(a)};
 }
 std::pair<const Buffer*,u64> ObtainVertexBuffer(VAddr,u32,std::span<const VertexFetch::Range>);
 bool SynchronizeMemory(const Buffer*,VAddr,u32,bool,bool);
 bool SynchronizeMemoryFromImage(const Buffer*,VAddr,u32){return false;}
 const Buffer* UploadCopies(const Buffer* dest,std::span<vk::BufferCopy> copies,u64 n,bool synchronous){
  if(copies.empty())return nullptr;
  auto& src=staging.emplace_back();src.data.resize(n);copied_bytes+=n;
  for(auto& c:copies){memcpy(src.data.data()+c.srcOffset,reinterpret_cast<void*>(c.dstOffset),c.size);c.dstOffset-=dest->cpu_addr;}
  return &src;
 }
''')
text = text.replace("pages.impl=&driver;raster.cache=&cache;", "resident.assign(8192,false);copied_bytes=0;pages.impl=&driver;raster.cache=&cache;")
source = (ROOT / "gpu/shadps4/video_core/buffer_cache/buffer_cache.cpp").read_text()
a = source.index("std::pair<const Buffer*, u64> BufferCache::ObtainVertexBuffer(")
b = source.index("const Buffer* BufferCache::UploadCopies(", a)
pos = text.index("\nusing namespace VideoCore;")
text = text[:pos] + "\nnamespace VideoCore {\n" + source[a:b] + "\n}\n" + text[pos:]
text += r'''
int main(int argc,char**){
 bool control=argc>1;int fd=memfd_create("vertex-fetch-refresh",0);assert(fd>=0 && ftruncate(fd,Bytes)==0);
 guest=static_cast<u8*>(mmap(reinterpret_cast<void*>(Base),Bytes,PROT_READ|PROT_WRITE,MAP_SHARED|MAP_FIXED_NOREPLACE,fd,0));assert(guest==reinterpret_cast<void*>(Base));
 backing=static_cast<u8*>(mmap(nullptr,Bytes,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0));assert(backing!=MAP_FAILED);close(fd);
 struct sigaction action{};action.sa_sigaction=Fault;action.sa_flags=SA_SIGINFO;sigemptyset(&action.sa_mask);assert(!sigaction(SIGSEGV,&action,nullptr));
 {
  Session s;for(u64 i=0;i<4_MB;++i)backing[i]=u8(i*17+i/4096);
  const VertexFetch::Range reads[]={{52*4096+128,6000}};
  if(control)s.cache.ObtainBuffer(Base,4_MB);
  else{auto [arena,offset]=s.cache.ObtainVertexBuffer(Base,4_MB,reads);assert(arena==&s.cache.arena && offset==0);}
  for(u64 i=reads[0].offset;i<reads[0].offset+reads[0].size;++i)assert(gpu[i]==backing[i]);
  assert(copied_bytes==(control?4_MB:8_KB));
  if(!control){assert(s.Dirty(0) && !resident[0]);
   const VertexFetch::Range later[]={{3_MB,8192}};
   s.cache.ObtainVertexBuffer(Base,4_MB,later);assert(copied_bytes==16_KB);
   for(u64 i=3_MB;i<3_MB+8192;++i)assert(gpu[i]==backing[i]);
   s.Write(53,229);s.cache.ObtainVertexBuffer(Base,4_MB,reads);assert(gpu[53*4096]==229);
   const VertexFetch::Range invalid[]={{4_MB-1,2}};
   s.cache.ObtainVertexBuffer(Base,4_MB,invalid);assert(!s.Dirty(0));
  }
  printf("PASS: actual %s path: 4 MiB descriptor / 6000 fetched bytes, initial upload %llu bytes; later demand, rewritten bytes, unchanged binding and invalid-range fallback verified.\n",control?"full binding":"bounded binding",(unsigned long long)(control?4_MB:8_KB));
 }
 {
  Session s;s.Upload(20,1,true);gpu[20*4096]=211;
  const VertexFetch::Range reads[]={{20*4096,4096}};s.cache.ObtainVertexBuffer(Base,4_MB,reads);assert(gpu[20*4096]==211);
  s.Write(200,159);s.cache.EnsureResident(&s.cache.arena,(Base+200*4096)>>16,(Base+200*4096)>>16);
  s.cache.SynchronizeMemory(&s.cache.arena,Base+200*4096,4096,true,false);
  assert(gpu[200*4096]==159 && s.GpuDirty(200));assert(s.Read(200)==159);
  puts("PASS: GPU-authored neighbours survive; precise writable staging snapshot precedes read revocation.");
 }
 mprotect(guest,Bytes,PROT_READ|PROT_WRITE);munmap(guest,Bytes);munmap(backing,Bytes);
}
'''
with tempfile.TemporaryDirectory(prefix="vertex-fetch-refresh-") as temporary:
    cpp = Path(temporary) / "vertex.cpp"
    cpp.write_text(text)
    exe = cpp.with_suffix("")
    subprocess.run([*shlex.split(os.environ.get("CXX", "g++")), "-std=c++23", "-O1", "-pthread", "-UNDEBUG",
                    "-I" + str(ROOT / "gpu/shim"), "-I" + str(ROOT / "gpu/shadps4"),
                    str(cpp), "-o", str(exe)], check=True)
    for args in (["control"], []):
        subprocess.run([str(exe), *args], check=True, timeout=30)
