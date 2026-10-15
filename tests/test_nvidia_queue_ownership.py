# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Run production FG queue options, Present and input retirement with delayed SDK fences.

Uses the real Streamline/Vulkan declarations. The SDK/device boundary records
calls; this checks ownership and ordering, not hardware interpolation or FPS.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROGRAM = r'''
#include "video_core/renderer_vulkan/vk_common.h"
#include "bbport_hitch.h"
#include "bbport_settings.h"
#include "bbport_frame_metrics.h"
#include "sl_core_api.h"
#include "sl_dlss_g.h"
#include "sl_reflex.h"
#include "sl_pcl.h"
#include <algorithm>
#include <cassert>
#include <condition_variable>
#include <cstdio>
#include <future>
#include <functional>
#include <mutex>
using u64=uint64_t;
namespace BbSettings { Values& Get(){static Values values;return values;} }
namespace Vulkan {
struct Frame {
 int nvidia_token{};vk::Semaphore nvidia_fence{};
 u64 nvidia_fence_value{},nvidia_fence_epoch{};
};
struct Scheduler {static inline std::mutex submit_mutex;};
}
namespace Boundary {
std::mutex gate;std::condition_variable cv;
bool hold{},entered{},release{};
unsigned waits{},drains{},off_calls{};std::atomic<bool> reused{};
vk::Semaphore expected_semaphore;u64 expected_value{};
struct Device {
 explicit operator bool()const{return true;}
 vk::Result waitSemaphores(const vk::SemaphoreWaitInfo& info,u64)const {
  assert(info.semaphoreCount==1 && *info.pSemaphores==expected_semaphore && *info.pValues==expected_value);
  std::unique_lock lock{gate};++waits;entered=true;cv.notify_all();
  if(hold)cv.wait(lock,[]{return release;});
  return vk::Result::eSuccess;
 }
 vk::Result waitIdle()const{++drains;return vk::Result::eSuccess;}
};
bool state_has_fence=true,state_succeeds=true;
sl::Result State(const sl::ViewportHandle&,sl::DLSSGState& state,const sl::DLSSGOptions*) {
 state.numFramesActuallyPresented=2;state.numFramesToGenerateMax=3;
 state.status=sl::DLSSGStatus::eOk;
 state.inputsProcessingCompletionFence=state_has_fence ? reinterpret_cast<void*>(0x1234) : nullptr;
 state.lastPresentInputsProcessingCompletionFenceValue=state_has_fence ? 77 : 0;
 return state_succeeds ? sl::Result::eOk : sl::Result::eErrorInvalidParameter;
}
sl::Result Options(const sl::ViewportHandle&,const sl::DLSSGOptions& options){
 if(options.mode==sl::DLSSGMode::eOff)++off_calls;
 return sl::Result::eOk;
}
}
namespace BbNvidia {
std::mutex mutex;
bool initialized=true,fg_on=true,failed{},input_queues_parallel{};
Boundary::Device device;
vk::Semaphore latest_fence;
u64 latest_value{},input_epoch=1,pacing_policy{};
sl::ViewportHandle viewport{0};
auto fg_state=&Boundary::State;auto fg_options=&Boundary::Options;
BbFrameMetrics::Counter frame_metrics;
bool reflex_options_applied{},reflex_supported=true;
sl::ReflexOptions applied_reflex_options;
sl::Result ReflexOptions(const sl::ReflexOptions&){return sl::Result::eOk;}
auto reflex_options=&ReflexOptions;
bool ApplyReflexOptions(const sl::ReflexOptions&){return true;}
bool Wanted(){return true;}
void Mark(sl::PCLMarker,int){}
void Error(const sl::APIError&){}
__RETIREMENT__
sl::DLSSGOptions QueueOptions(){
 struct Source{uint32_t render_width=1920,render_height=1080;}source;
 struct Snapshot{uint32_t width=3840,height=2160;}saved;
 auto* snapshot=&saved;uint32_t generated=1,buffers=3;
 const auto format=vk::Format::eR8G8B8A8Srgb;
 __OPTIONS__
 input_queues_parallel=options.queueParallelismMode==sl::DLSSGQueueParallelismMode::eBlockNoClientQueues;
 return options;
}
__PRESENT__
__WAIT__
}
int main(){
 using namespace BbNvidia;using namespace std::chrono_literals;
 BbSettings::Get().frame_generation=BbSettings::FrameGenerationNvidia;
 assert(QueueOptions().queueParallelismMode==sl::DLSSGQueueParallelismMode::eBlockPresentingClientQueue);
 Vulkan::Frame frame;
 assert(Present(&frame,[]{return true;}));
 assert(frame.nvidia_fence && frame.nvidia_fence_value==77 && frame.nvidia_fence_epoch==1);
 assert(QueueOptions().queueParallelismMode==sl::DLSSGQueueParallelismMode::eBlockNoClientQueues);
 Boundary::expected_semaphore=frame.nvidia_fence;Boundary::expected_value=77;
 Boundary::hold=true;
 auto rewrite=std::async(std::launch::async,[&]{WaitForInputs(&frame);Boundary::reused=true;});
 {std::unique_lock lock{Boundary::gate};assert(Boundary::cv.wait_for(lock,2s,[]{return Boundary::entered;}));}
 assert(!Boundary::reused && rewrite.wait_for(30ms)==std::future_status::timeout);
 {std::scoped_lock lock{Boundary::gate};Boundary::release=true;Boundary::cv.notify_all();}
 assert(rewrite.wait_for(2s)==std::future_status::ready);rewrite.get();
 assert(Boundary::reused && !frame.nvidia_fence && !frame.nvidia_fence_value);
 Boundary::hold=false;
 // Turning FG off retires the last SDK inputs before releasing its semaphore.
 const auto old_epoch=input_epoch;Off();
 assert(input_epoch==old_epoch+1 && !latest_fence && !latest_value && !fg_on && !input_queues_parallel);
 assert(Boundary::off_calls==1 && Boundary::waits==2);
 // Old frame handles were destroyed by SL after that complete epoch; never wait on them.
 frame.nvidia_fence=Boundary::expected_semaphore;frame.nvidia_fence_value=77;frame.nvidia_fence_epoch=old_epoch;
 WaitForInputs(&frame);assert(Boundary::waits==2);
 // Bootstrap may have no fence. Parallel operation may not silently lose ownership.
 fg_on=true;Boundary::state_has_fence=false;
 assert(QueueOptions().queueParallelismMode==sl::DLSSGQueueParallelismMode::eBlockPresentingClientQueue);
 assert(Present(&frame,[]{return true;}) && fg_on && Boundary::drains==0);
 input_queues_parallel=true;
 assert(Present(&frame,[]{return true;}));
 assert(Boundary::drains==1 && !fg_on && failed && !input_queues_parallel);
 // A failed GetState follows the same conservative GPU drain, preserving real frames.
 failed=false;fg_on=true;Boundary::state_succeeds=false;
 assert(Present(&frame,[]{return true;}));assert(Boundary::drains==2 && !fg_on && failed);
 std::puts("PASS: production SDK options bootstrap safely, enable queue overlap only with ownership, block input reuse until retirement, invalidate destroyed epochs, and drain on missing/failed parallel ownership.");
}
'''


def main():
    source = (ROOT/'gpu/shim/bbport_nvidia.cpp').read_text()
    retirement = source[source.index('void WaitLatestInputs() {'):source.index('using Matrix=')]
    present = source[source.index('bool Present(Vulkan::Frame*'):source.index('void WaitForInputs(')]
    wait = source[source.index('void WaitForInputs('):source.index('void BeforeSwapchainChange()')]
    start = source.index('    sl::DLSSGOptions options;options.mode=sl::DLSSGMode::eOn;')
    options = source[start:source.index('    sl::Constants c;', start)]
    with tempfile.TemporaryDirectory(prefix='nvidia-queue-ownership-') as temp:
        folder = Path(temp);cpp = folder/'test.cpp';exe = folder/'test'
        cpp.write_text(PROGRAM.replace('__RETIREMENT__',retirement).replace('__PRESENT__',present)
                       .replace('__WAIT__',wait).replace('__OPTIONS__',options))
        subprocess.run(['g++','-std=c++23','-O1','-pthread','-UNDEBUG',
                        '-Igpu/shadps4','-Igpu/shim','-Igpu/third_party/streamline-headers',
                        '-Iout/test-headers',str(cpp),'-o',str(exe)],cwd=ROOT,check=True)
        subprocess.run([str(exe)],check=True,timeout=30)


if __name__ == '__main__':
    main()
