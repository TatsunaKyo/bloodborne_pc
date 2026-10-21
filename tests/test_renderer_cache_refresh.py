"""Execute the shipped R51 and refreshed production containers/texture collector.

The recording backends below do not measure a GPU or gameplay. They exercise
the real collector, real slot storage and real LRU traversal with controlled
resource ages, including the return to an off-screen area before eviction.
"""
from pathlib import Path
import argparse
import os
import re
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = "d7062615e1cd1ee68e591ca7e36956619de1f975"


def source(path, control):
    return (subprocess.check_output(["git", "show", BASE + ":" + path], cwd=ROOT, text=True)
            if control else (ROOT / path).read_text())


def method(text, name):
    start = text.index(name)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        if text[end] == "{":
            depth += 1
        elif text[end] == "}":
            depth -= 1
        end += 1
    return text[start:end]


CONTAINERS = r'''
#include <algorithm>
#include <array>
#include <bit>
#include <cassert>
#include <cstdio>
#include <deque>
#include <memory>
#include <type_traits>
#include "common/lru_cache.h"
#include "common/slot_vector.h"
struct Value {
 static inline unsigned moves=0,alive=0;
 u64 value;std::array<u8,1024> padding{};
 explicit Value(u64 n):value(n){++alive;}
 Value(Value&& v):value(v.value){++moves;++alive;}
 ~Value(){--alive;}
};
#if !CONTROL
struct Node:Common::LRUNode<> {u64 id;};
#endif
int main(){
 {
#if CONTROL
  Common::SlotVector<Value> values;
#else
  Common::SlotVector<Value> values(10000);
#endif
  std::vector<Common::SlotId> ids;std::vector<Value*> pointers;
  for(u64 i=0;i<9000;++i){auto id=values.Insert(i);ids.push_back(id);pointers.push_back(&values[id]);}
  unsigned moved=0;
  for(u64 i=0;i<ids.size();++i){assert(values[ids[i]].value==i);moved+=pointers[i]!=&values[ids[i]];}
#if CONTROL
  assert(moved>0 && Value::moves>0);
#else
  assert(moved==0 && Value::moves==0);
#endif
  for(u64 i=0;i<ids.size();i+=2)values.Erase(ids[i]);
  for(u64 i=0;i<4500;++i){auto id=values.Insert(10000+i);assert(values[id].value==10000+i);}
  for(u64 i=1;i<ids.size();i+=2){assert(values[ids[i]].value==i);
#if !CONTROL
   assert(&values[ids[i]]==pointers[i]);assert(values.GetSlotId(values[ids[i]])==ids[i]);
#endif
  }
  printf("%s: 9000 resources, %u moved addresses, %u move constructors; reuse verified\n",CONTROL?"R51":"current",moved,Value::moves);
 }
 assert(Value::alive==0);
 unsigned visited=0;
#if CONTROL
 Common::LeastRecentlyUsedCache<u32,u64> lru;
 for(u32 i=0;i<10000;++i)lru.Insert(i,1);
 lru.ForEachItemBelow(100,[&](u32){++visited;return true;});
 assert(visited==10000);
#else
 Common::LRUCache<Node> lru;std::array<Node,10000> nodes;
 for(u32 i=0;i<nodes.size();++i){nodes[i].id=i;lru.Insert(nodes[i],1);}
 lru.ForEachItemBelow(100,[&](Node&){++visited;return true;});assert(visited==1);
 for(auto& node:nodes)lru.Free(node);
#endif
 printf("%s: callback requested stop after one item; actual callbacks %u\n",CONTROL?"R51":"current",visited);
}
'''

COLLECTOR = r'''
#include <algorithm>
#include <array>
#include <bit>
#include <cassert>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <functional>
#include <memory>
#include <mutex>
#include <type_traits>
#include <vector>
#include "common/lru_cache.h"
#include "common/slot_vector.h"
#include "bbport_readback_batch.h"
namespace Common {template<class T,class U> constexpr T AlignUp(T a,U b){return (a+b-1)/b*b;}}
namespace BbHitch {struct Scope{explicit Scope(const char*){}};}
using ImageId=Common::SlotId;
enum class ImageFlagBits:u32 {MaybeGpuDirty=1};
bool True(u32 n){return n!=0;}u32 operator&(u32 n,ImageFlagBits f){return n&u32(f);}
enum class DownloadMemoryFlags:u32 {Sync=1,DiscardBufferCache=2};
DownloadMemoryFlags operator|(DownloadMemoryFlags a,DownloadMemoryFlags b){return DownloadMemoryFlags(u32(a)|u32(b));}
u64 XXH3_64bits(const void*,u64){return 0;}
struct Info{VAddr guest_address=0;u64 guest_size=8_MB;bool IsTiled()const{return false;}};
struct Image
#if !CONTROL
 :Common::LRUNode<>
#endif
 {Info info;u32 flags=0;u64 gpu_hash=0,lru_touched_tick=0,cache_id=0;
 bool SafeToDownload()const{return false;}
 bool HasGpuValidData()const{return false;}
 bool CanBeDownloaded()const{return true;}
 };
struct Instance{u64 used=4_GB;bool CanReportMemoryUsage(){return true;}u64 GetDeviceMemoryUsage(){return used;}
 bool IsIntegrated(){return false;}u64 GetDeviceMemoryBudgetNow(){return 16_GB;}};
namespace Core {struct Memory{static Memory* Instance(){static Memory m;return &m;}
 void WaitForPageProtection(VAddr,u64){}};}
struct TextureCache {
 Instance instance;struct {void Finish(){}} scheduler;
 struct{void ReadMemory(VAddr,u64,bool,bool,bool){}}buffer_cache;
 Common::SlotVector<Image> slot_images
#if !CONTROL
 {1000}
#endif
 ;
#if CONTROL
 Common::LeastRecentlyUsedCache<ImageId,u64> lru_cache;
#else
 Common::LRUCache<Image> image_lru_cache;
#endif
 std::mutex mutex;u64 gc_tick=60020,total_used_memory=0,trigger_gc_memory=1_GB,
 pressure_gc_memory=8_GB,critical_gc_memory=14_GB,gc_evictions=0,gc_downloads=0,
 gc_kept=0,gc_kept_bytes=0,gc_dropped=0,gc_second=100;std::array<u64,64>gc_tick_at_second{};
 std::chrono::steady_clock::time_point now=std::chrono::steady_clock::time_point(std::chrono::milliseconds(100033)),gc_report_time=now;
 unsigned freed=0;
 TextureCache(){for(u64 s=40;s<=103;++s)gc_tick_at_second[s%64]=s*600;}
 void Add(unsigned count,u64 tick){for(unsigned i=0;i<count;++i){auto id=slot_images.Insert();auto& image=slot_images[id];image.lru_touched_tick=tick;
#if CONTROL
 image.cache_id=lru_cache.Insert(id,tick);
#else
 image_lru_cache.Insert(image,tick);
#endif
 }}
 void FreeImage(ImageId id){auto& image=slot_images[id];
#if CONTROL
 lru_cache.Free(image.cache_id);
#else
 image_lru_cache.Free(image);
#endif
 instance.used-=image.info.guest_size;total_used_memory-=image.info.guest_size;slot_images.Erase(id);++freed;}
 void DownloadImageMemory(ImageId,bool,BbReadback::Batch*){assert(false);}
 void DownloadImageMemory(ImageId,DownloadMemoryFlags){assert(false);}
 void GarbageCollectImages();
};
@METHOD@
int main(){
 { TextureCache c;c.gc_tick=@INITIAL_TICK@;c.gc_second=0;c.gc_tick_at_second.fill(0);c.Add(12,c.gc_tick);c.GarbageCollectImages();
#if CONTROL
 assert(c.freed==10);
#else
 assert(c.freed==0);
#endif
 printf("%s: startup resources preserved=%s\n",CONTROL?"R51":"current",CONTROL?"no":"yes");
 }
 {
 TextureCache c;c.Add(12,60000);c.GarbageCollectImages();
#if CONTROL
 assert(c.freed==10); // 20 submissions old: only 33 ms at 600 submissions/s.
#else
 assert(c.freed==0); // preserve the off-screen working set for a return traversal.
 c.now=std::chrono::steady_clock::time_point(std::chrono::seconds(121));c.gc_tick=72600;
 c.GarbageCollectImages();assert(c.freed==10);c.GarbageCollectImages();assert(c.freed==12);
#endif
 printf("%s: off-screen textures at 33 ms: %u evicted; later age-based reclamation verified\n",CONTROL?"R51":"current",CONTROL?10:0);
 }
#if !CONTROL
 {
 TextureCache c;c.instance.used=10_GB;c.Add(12,60000);c.gc_tick=61800;
 c.now=std::chrono::steady_clock::time_point(std::chrono::seconds(103));c.GarbageCollectImages();assert(c.freed==0);
 c.gc_tick=63600;c.now=std::chrono::steady_clock::time_point(std::chrono::seconds(106));
 c.GarbageCollectImages();assert(c.freed==12);
 puts("current: under pressure, 3 s idle retained, 6 s idle reclaimed");
 }
 {
 TextureCache c;c.instance.used=15_GB;c.Add(12,59000);c.GarbageCollectImages();assert(c.freed==12);
 puts("current: critical-budget emergency reclamation remains available");
 }
#endif
}
'''


def run(folder, compiler, control):
    case = folder / ("r51" if control else "current")
    (case / "common").mkdir(parents=True)
    for name in ("lru_cache.h", "slot_vector.h"):
        (case / "common" / name).write_text(source("gpu/shadps4/common/" + name, control))
    (case / "common/assert.h").write_text(
        "#pragma once\n#include <cassert>\n#define ASSERT(x) assert(x)\n"
        "#define ASSERT_MSG(x,...) assert(x)\n#define DEBUG_ASSERT(x) assert(x)\n")
    extra = []
    if not control:
        cpp = case / "slots.cpp"
        cpp.write_text(source("gpu/shadps4/common/slot_vector.cpp", False))
        extra.append(str(cpp))
    gc = method(source("gpu/shadps4/video_core/texture_cache/texture_cache.cpp", control),
                "void TextureCache::GarbageCollectImages()")
    gc = gc.replace("std::chrono::steady_clock::now()", "this->now")
    for name, content in (("containers", CONTAINERS), ("collector", COLLECTOR.replace("@METHOD@", gc))):
        if control:
            for object_name in ("values", "slot_images"):
                content = content.replace(object_name + ".Insert(", object_name + ".insert(")
                content = content.replace(object_name + ".Erase(", object_name + ".erase(")
        cpp = case / (name + ".cpp")
        exe = case / name
        if name == "collector":
            header = source("gpu/shadps4/video_core/texture_cache/texture_cache.h", control)
            initial = re.search(r"u64 gc_tick = (\d+)", header).group(1)
            content = content.replace("@INITIAL_TICK@", initial)
        cpp.write_text(content)
        subprocess.run([*shlex.split(compiler), "-std=c++23", "-O1", "-UNDEBUG", "-DCONTROL=" + str(int(control)),
                        "-I" + str(case), "-I" + str(ROOT / "gpu/shadps4"),
                        "-I" + str(ROOT / "gpu/shim"), str(cpp), *extra, "-pthread", "-o", str(exe)], check=True)
        env = {k: v for k, v in os.environ.items() if not k.startswith("BB_GC_")}
        subprocess.run([str(exe)], env=env, check=True, timeout=30)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default=os.environ.get("CXX", "g++"))
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="renderer-cache-") as temporary:
        for control in (True, False):
            run(Path(temporary), args.compiler, control)


if __name__ == "__main__":
    main()
