"""Exercise the production bounded resident uploader, without permitting allocations or binds."""
from pathlib import Path
import subprocess,tempfile
root=Path(__file__).resolve().parents[1]
s=(root/'gpu/shadps4/video_core/buffer_cache/buffer_cache.cpp').read_text();a=s.index('void BufferCache::PreuploadResident()');b=s.index('\nvoid BufferCache::InvalidateMemory',a);body=s[a:b]
prefix=r'''
#include <algorithm>
#include <cassert>
#include <chrono>
#include <cstdlib>
#include <cstdint>
#include <vector>
#include <array>
#include <iostream>
using u64=uint64_t;using u32=uint32_t;using VAddr=uintptr_t;
struct RegionManager{static u64 NowMillis(){return 1000;}};
struct Memory {bool allow=true;bool CanReadAhead(VAddr,u32){return allow;}};
struct Tracker{bool allow=true;bool IsPreuploadCandidate(VAddr,u32,u64 before){assert(before==800);return allow;}};
struct Buffer{int index;};struct Range{u64 start,end;};
class BufferCache {
public:
 Memory mem;Tracker tracker;Memory* memory=&mem;Tracker* memory_tracker=&tracker;
 std::vector<Range> resident_ranges;u64 preupload_cursor=0;u32 block_shift=12,arena_page_bits=24;
 std::array<Buffer*,4> address_space{};u64 bytes=0,calls=0;std::vector<std::pair<VAddr,u32>> uploads;
 void PreuploadResident();
 void SynchronizeMemory(const Buffer* arena,VAddr a,u32 size,bool written,bool texel){
  assert(arena && !written && !texel);assert(a>=0x1000000 && a+size<=0x1400000);
  assert(size<=64*1024);bytes+=size;++calls;uploads.emplace_back(a,size);
 }
};
'''
main=r'''
int main(){setenv("BB_PREUPLOAD","1",1);BufferCache cache;Buffer arena{1};cache.address_space[1]=&arena;
 cache.resident_ranges.push_back({0x1000000>>12,0x1400000>>12});
 cache.tracker.allow=false;cache.PreuploadResident();assert(cache.bytes==0);
 cache.tracker.allow=true;cache.mem.allow=false;cache.PreuploadResident();assert(cache.bytes==0);
 cache.mem.allow=true;cache.preupload_cursor=0;cache.PreuploadResident();assert(cache.bytes>0 && cache.bytes<=2*1024*1024 && cache.calls<=256);
 auto before=cache.bytes;for(int i=0;i<8;++i)cache.PreuploadResident();assert(cache.bytes>before);
 cache.address_space[1]=nullptr;before=cache.bytes;cache.PreuploadResident();assert(cache.bytes==before);
 cache.resident_ranges.clear();cache.PreuploadResident();assert(cache.preupload_cursor==0);
 std::cout<<"PASS production resident-only preupload: no allocations/binds, ownership/quiet/alias gates, 64-KiB chunks, 2-MiB and 256-scan bounds, bounded cursor progress.\n";
}
'''
with tempfile.TemporaryDirectory(prefix='preupload-') as d:
 p=Path(d);(p/'test.cpp').write_text(prefix+body+main)
 subprocess.run(['g++','-std=c++20','-O1',str(p/'test.cpp'),'-o',str(p/'test')],check=True);subprocess.run([str(p/'test')],check=True)
