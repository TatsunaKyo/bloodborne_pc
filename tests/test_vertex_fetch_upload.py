"""Execute demanded vertex uploads through the production cache and real trackers."""
from pathlib import Path
import os, subprocess, tempfile
import test_resident_upload_batch as resident
ROOT=resident.ROOT
text=resident.fixture(False);text=text[:text.index('int main(){')]
text=text.replace('#include "bbport_hitch_trace.h"','#include "bbport_hitch_trace.h"\n#include "video_core/buffer_cache/vertex_fetch_range.h"')
text=text.replace('struct Buffer{VAddr cpu_addr=0;std::vector<u8> data;};',
                  'struct Buffer{VAddr cpu_addr=0;std::vector<u8> data;u64 Offset(VAddr a)const{return a-cpu_addr;}};')
text=text.replace(' Runtime runtime;u64 block_size=64_KB;',r'''
 static constexpr u64 STREAM_THRESHOLD=16_KB;
 u32 block_shift=16;Buffer* vertex_arena{};
 const Buffer* GetArena(u64,u64){assert(vertex_arena);return vertex_arena;}
 void EnsureResident(const Buffer* arena,u64 first,u64 last){
  for(u64 b=first;b<=last;++b){
   const auto page=((b<<block_shift)-arena->cpu_addr)/4096;
   for(u64 i=0;i<(1ull<<block_shift)/4096;++i)resident[page+i]=true;
  }
 }
 std::pair<const Buffer*,u64> ObtainBuffer(VAddr a,u32 n,bool){
  EnsureResident(vertex_arena,a>>block_shift,(a+n-1)>>block_shift);
  SynchronizeMemory(vertex_arena,a,n,false,false);return {vertex_arena,vertex_arena->Offset(a)};
 }
 std::pair<const Buffer*,u64> ObtainVertexBuffer(VAddr,u32,std::span<const VertexFetch::Range>);
 Runtime runtime;u64 block_size=64_KB;''')
text=text.replace('pages.impl=&driver;r.cache=&cache;', 'cache.vertex_arena=&arena;pages.impl=&driver;r.cache=&cache;')
source=(ROOT/'gpu/shadps4/video_core/buffer_cache/buffer_cache.cpp').read_text()
a=source.index('std::pair<const Buffer*, u64> BufferCache::ObtainVertexBuffer(')
method=source[a:source.index('bool BufferCache::SynchronizeMemory(',a)]
pos=text.index('\nusing namespace VideoCore;')
text=text[:pos]+'\nnamespace VideoCore {\n'+method+'\n}\n'+text[pos:]
text+=r'''
int main(int argc,char**){
 const bool control=argc>1;
 const int fd=memfd_create("vertex-fetch-test",0);assert(fd>=0 && ftruncate(fd,Bytes)==0);
 guest=static_cast<u8*>(mmap(reinterpret_cast<void*>(Base),Bytes,PROT_READ|PROT_WRITE,MAP_SHARED|MAP_FIXED_NOREPLACE,fd,0));assert(guest==reinterpret_cast<u8*>(Base));
 backing=static_cast<u8*>(mmap(nullptr,Bytes,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0));assert(backing!=MAP_FAILED);close(fd);
 struct sigaction action{};action.sa_sigaction=Fault;action.sa_flags=SA_SIGINFO;sigemptyset(&action.sa_mask);assert(!sigaction(SIGSEGV,&action,nullptr));
 {
  Session s;for(u64 i=0;i<4_MB;++i)backing[i]=u8(i*17+i/4096);
  const VertexFetch::Range reads[]={{52*4096+128,6000}};
  if(control)s.cache.ObtainBuffer(Base,4_MB,false);
  else{const auto [arena,offset]=s.cache.ObtainVertexBuffer(Base,4_MB,reads);assert(arena==&s.arena && offset==0);}
  s.Complete();
  for(u64 i=reads[0].offset;i<reads[0].offset+reads[0].size;++i)assert(gpu[i]==backing[i]);
  if(control)assert(copied_bytes==4_MB);
  else{assert(copied_bytes==64_KB && s.Dirty(0) && !resident[0]);}
  std::printf("%s: 4 MiB descriptor, 6000 fetched bytes: %llu bytes uploaded; original binding base preserved.\n",control?"R50 full binding control":"Demanded ranges",(unsigned long long)copied_bytes);
  if(!control){
   // A later range in the same descriptor must still be dirty and upload then.
   const VertexFetch::Range later[]={{3_MB,8192}};
   s.cache.ObtainVertexBuffer(Base,4_MB,later);s.Complete();assert(copied_bytes==128_KB);
   for(u64 i=3_MB;i<3_MB+8192;++i)assert(gpu[i]==backing[i]);
   s.Write(53,229);s.cache.ObtainVertexBuffer(Base,4_MB,reads);s.Complete();assert(gpu[53*4096]==229);
   // Invalid/unknown footprints conservatively synchronize the full binding.
   const VertexFetch::Range invalid[]={{4_MB-1,2}};
   s.cache.ObtainVertexBuffer(Base,4_MB,invalid);s.Complete();assert(!s.Dirty(0));
  }
 }
 {
  Session s;s.Upload(20,1,true);s.Complete();gpu[20*4096]=211;s.cache.writable_request=false;
  const VertexFetch::Range reads[]={{20*4096,4096}};
  s.cache.ObtainVertexBuffer(Base,4_MB,reads);s.Complete();assert(gpu[20*4096]==211);
 }
 assert(!mprotect(guest,Bytes,PROT_READ|PROT_WRITE));munmap(guest,Bytes);munmap(backing,Bytes);
 puts("PASS: actual ObtainVertexBuffer/SynchronizeMemory with protected pages: needed bytes match, unused pages remain dirty, reused writes and later draws upload, GPU-authored bytes survive, unknown ranges fall back.");
}
'''
with tempfile.TemporaryDirectory(prefix='vertex-fetch-upload-') as temporary:
 p=Path(temporary)/'vertex.cpp';p.write_text(text);exe=p.with_suffix('')
 subprocess.run([os.environ.get('CXX','g++'),'-std=c++20','-O2','-pthread','-I'+str(ROOT/'gpu/shim'),'-I'+str(ROOT/'gpu/shadps4'),str(p),'-o',str(exe)],check=True)
 for args in (['control'],[]):subprocess.run([str(exe),*args],check=True,timeout=30)
