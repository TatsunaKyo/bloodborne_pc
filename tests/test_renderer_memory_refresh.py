"""Execute the current production tracker headers with a recorded protection boundary.

Checks CPU/GPU dirty ranges across 4-MiB regions. OS protection and GPU copies
are boundary models; this does not claim an affected-scene timing result.
"""
from pathlib import Path
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
SOURCE = r'''
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <map>
#include <utility>
#include <vector>
#include "video_core/buffer_cache/memory_tracker.h"
extern "C" {uint64_t runtime_disabled_optimizations=0;}
namespace VideoCore {
struct PageManager::Impl {};
PageManager::PageManager(Vulkan::Rasterizer*) {}
PageManager::~PageManager() = default;
static unsigned protection_calls;
template<bool track> void PageManager::UpdatePageWatchers(VAddr, u64) const {++protection_calls;}
template<bool track,bool read> void PageManager::UpdatePageWatchersForRegion(VAddr, RegionBits&) const {
 ++protection_calls;
}
}
int main() {
 using namespace VideoCore;
 PageManager pages(nullptr);
 MemoryTracker tracker(pages);
 constexpr VAddr base=0x1000000;
 for (unsigned i=0;i<256;++i) {
  const VAddr address=base+(i%8)*TRACKER_HIGHER_PAGE_SIZE+TRACKER_HIGHER_PAGE_SIZE-4096;
  constexpr u64 size=8192;
  assert(tracker.IsRegionCpuModified(address,size));
  u64 uploaded=0;
  tracker.ForEachUploadRange(address,size,false,[&](VAddr a,u64 n){
    assert(a>=address && a+n<=address+size);uploaded+=n;
  },[]{});
  assert(uploaded>0 && !tracker.IsRegionCpuModified(address,size));
  unsigned clean_uploads=0;
  tracker.ForEachUploadRange(address,size,false,[&](VAddr,u64){++clean_uploads;},[]{});
  assert(clean_uploads==0);
  tracker.ForEachUploadRange(address,size,true,[](VAddr,u64){},[]{});
  assert(tracker.IsRegionGpuModified(address,size));
  u64 downloaded=0;
  tracker.ForEachDownloadRange<false>(address,size,[&](VAddr,u64 n){downloaded+=n;});
  assert(downloaded==size && tracker.IsRegionGpuModified(address,size));
  unsigned flushes=0;
  tracker.InvalidateRegion(address,size,[&]{
    ++flushes;
    tracker.ForEachDownloadRange<true>(address,size,[](VAddr,u64){});
    tracker.MarkRegionAsCpuModified(address,size);
  });
  assert(flushes>0 && !tracker.IsRegionGpuModified(address,size));
  assert(tracker.IsRegionCpuModified(address,size));
  tracker.ForEachUploadRange(address,size,false,[](VAddr,u64){},[]{});
  // A readback-disabled path marks CPU dirty without requesting a GPU drain.
  tracker.ForEachUploadRange(address,size,true,[](VAddr,u64){},[]{});
  EmulatorSettings.mode=GpuReadbacksMode::Disabled;
  tracker.InvalidateRegion(address,size,[&]{assert(false);});
  assert(tracker.IsRegionCpuModified(address,size));
  tracker.UnmarkRegionAsGpuModified(address,size);
  EmulatorSettings.mode=GpuReadbacksMode::Precise;
 }
 assert(protection_calls>0);
 std::puts("PASS: 256 current tracker cycles across region boundaries: dirty uploads, clean fast path, GPU readbacks, invalidation and disabled-readback policy.");
}
'''
with tempfile.TemporaryDirectory(prefix='current-memory-tracker-') as temporary:
    folder=Path(temporary)
    for name,body in {
        'common/debug.h':'#pragma once\n#include <cassert>\n#define RENDERER_TRACE ((void)0)\n#define ASSERT(x) assert(x)\n#define ASSERT_MSG(x,...) assert(x)\n',
        'common/logging/log.h':'#pragma once\n#define LOG_WARNING(...) ((void)0)\n',
        'core/emulator_settings.h':'#pragma once\nenum class GpuReadbacksMode {Disabled,Relaxed,Precise};\ninline struct {GpuReadbacksMode mode=GpuReadbacksMode::Precise;auto GetReadbacksMode()const{return mode;}} EmulatorSettings;\n',
    }.items():
        p=folder/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(body)
    cpp=folder/'test.cpp';cpp.write_text(SOURCE)
    binary=folder/'test'
    subprocess.run(['g++','-std=c++23','-O1','-pthread','-I'+str(folder),'-I'+str(ROOT/'gpu/shim'),
                    '-I'+str(ROOT/'gpu/shadps4'),str(cpp),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True,timeout=30)
