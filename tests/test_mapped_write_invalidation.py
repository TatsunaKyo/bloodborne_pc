# SPDX-License-Identifier: GPL-2.0-or-later
"""Run the real Rasterizer invalidation body on fragmented GPU mappings."""
from pathlib import Path
import os,shlex,subprocess,tempfile
from test_streaming_io import function
root=Path(__file__).resolve().parents[1]
body=function((root/'gpu/shadps4/video_core/renderer_vulkan/vk_rasterizer.cpp').read_text(),'Rasterizer::InvalidateMemory')
prefix=r'''
#include "bbport_hitch.h"
#include <boost/icl/interval_set.hpp>
#include <boost/container/small_vector.hpp>
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <limits>
#include <shared_mutex>
#include <utility>
#include <vector>
using VAddr=uint64_t;using u64=uint64_t;
namespace Common {struct RecursiveSharedLock {std::shared_lock<std::shared_mutex> lock;explicit RecursiveSharedLock(std::shared_mutex& m):lock(m){}};}
struct Cache {std::vector<std::pair<VAddr,u64>> spans;void InvalidateMemory(VAddr a,u64 n,bool=false){spans.emplace_back(a,n);}};
struct Rasterizer {
 boost::icl::interval_set<VAddr> mapped_ranges;std::shared_mutex mapped_ranges_mutex;
 Cache buffer_cache,texture_cache;unsigned drains{};
 void DrainDrawPipe(){++drains;}
 bool IsMapped(VAddr a,u64 n){return n && a<=UINT64_MAX-n && boost::icl::contains(mapped_ranges,decltype(mapped_ranges)::interval_type::right_open(a,a+n));}
 bool InvalidateMemory(VAddr,u64,bool=false);
};
'''
main=r'''
int main(){
 Rasterizer r;using I=decltype(r.mapped_ranges)::interval_type;
 constexpr VAddr a=0x1040000000ULL;
 r.mapped_ranges+=I::right_open(a+4096,a+8192);
 r.mapped_ranges+=I::right_open(a+65536,a+98304);
 r.mapped_ranges+=I::right_open(a+1044480,a+1048576);
 assert(r.InvalidateMemory(a,1048576));
 assert(r.drains==1 && r.buffer_cache.spans==r.texture_cache.spans);
 const std::vector<std::pair<VAddr,u64>> expected{{a+4096,4096},{a+65536,32768},{a+1044480,4096}};
 assert(r.buffer_cache.spans==expected);
 r.buffer_cache.spans.clear();r.texture_cache.spans.clear();
 assert(r.InvalidateMemory(a+5000,3000));
 assert((r.buffer_cache.spans==std::vector<std::pair<VAddr,u64>>{{a+5000,3000}}));
 assert(r.drains==2);
 assert(!r.InvalidateMemory(a,4096) && r.drains==2);
 assert(!r.InvalidateMemory(a,0) && !r.InvalidateMemory(UINT64_MAX-3,8));
 assert(r.drains==2);
 // A partial overlap must never invalidate ordinary memory or a disjoint mapping.
 r.buffer_cache.spans.clear();r.texture_cache.spans.clear();
 assert(r.InvalidateMemory(a+8000,100));
 assert((r.buffer_cache.spans==std::vector<std::pair<VAddr,u64>>{{a+8000,100}}));
 std::puts("PASS: real invalidation body preserves all mapped islands, exact bounds and one drain; ordinary/zero/wrapping spans do not drain.");
}
'''
with tempfile.TemporaryDirectory(prefix='bb-mapped-write-') as d:
 p=Path(d);(p/'test.cpp').write_text(prefix+body+main)
 subprocess.run(shlex.split(os.environ.get('CXX','g++'))+['-std=c++20','-O2','-pthread','-I'+str(root/'gpu/shim'),*shlex.split(os.environ.get('CPPFLAGS','')),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
