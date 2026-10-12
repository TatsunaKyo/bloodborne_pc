# SPDX-License-Identifier: GPL-2.0-or-later
"""Run production submission/sparse-bind methods with recorded Vulkan entry points.

Hold each CPU preparation/retirement phase to check presentation progress. The
queue operations themselves remain serialized; this does not run a GPU.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def method(source, start, end):
    return source[source.index(start):source.index(end, source.index(start))]

scheduler_path = 'gpu/shadps4/video_core/renderer_vulkan/vk_scheduler.cpp'
bind_path = 'gpu/shadps4/video_core/buffer_cache/buffer_cache.cpp'
def extract(revision=None):
    def read(path):
        if revision:
            return subprocess.check_output(['git', 'show', revision + ':' + path], cwd=ROOT, text=True)
        return (ROOT / path).read_text()
    return (method(read(scheduler_path), 'void Scheduler::SubmitExecution(', 'void Scheduler::PriorityPendingOpsThread('),
            method(read(bind_path), 'void BufferCache::SubmitPendingArenaBinds(', '} // namespace VideoCore'))

HARNESS = r'''
#define VULKAN_HPP_NO_CONSTRUCTORS
#define VULKAN_HPP_NO_EXCEPTIONS
#define VULKAN_HPP_DISPATCH_LOADER_DYNAMIC 1
#define TRACY_GPU_ENABLED 0
#include <vulkan/vulkan.hpp>
#include <array>
#include <atomic>
#include <cassert>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <functional>
#include <future>
#include <mutex>
#include <thread>
#include <vector>
using u64=uint64_t; using u32=uint32_t;
VULKAN_HPP_DEFAULT_DISPATCH_LOADER_DYNAMIC_STORAGE
#define ASSERT_MSG(expr, ...) assert(expr)
void Check(vk::Result result) { assert(result==vk::Result::eSuccess); }

std::mutex phase_mutex;
std::condition_variable phase_cv;
int target=-1;
bool blocked=false,released=false;
std::atomic<bool> recorded{},copied{},ended{};
std::atomic<unsigned> queue_active{},submits{},binds{},presents{};
void Phase(int index) {
    std::unique_lock lock{phase_mutex};
    if(target!=index) return;
    blocked=true;phase_cv.notify_all();
    phase_cv.wait(lock,[]{return released;});
}
void QueueCall() {
    assert(queue_active.fetch_add(1)==0);
    for(int i=0;i<5;++i) std::this_thread::yield();
    assert(queue_active.fetch_sub(1)==1);
}
VKAPI_ATTR VkResult VKAPI_CALL End(VkCommandBuffer) {
    assert(recorded && copied);ended=true;return VK_SUCCESS;
}
VKAPI_ATTR VkResult VKAPI_CALL Submit(VkQueue,u32 count,const VkSubmitInfo* info,VkFence) {
    assert(recorded && copied && ended && count==1);
    const auto* timeline=static_cast<const VkTimelineSemaphoreSubmitInfo*>(info->pNext);
    assert(timeline->signalSemaphoreValueCount==1 && *timeline->pSignalSemaphoreValues==7);
    assert(info->waitSemaphoreCount==1 && timeline->waitSemaphoreValueCount==1);
    assert(*timeline->pWaitSemaphoreValues==7); // sparse binding still gates this submission.
    QueueCall();++submits;return VK_SUCCESS;
}
VKAPI_ATTR VkResult VKAPI_CALL Bind(VkQueue,u32 count,const VkBindSparseInfo* info,VkFence) {
    assert(count==1 && info->bufferBindCount==1 && info->pBufferBinds->bindCount==1);
    QueueCall();++binds;return VK_SUCCESS;
}
struct Semaphore {
    u64 NextTick() { return 7; }
    vk::Semaphore Handle() { return vk::Semaphore(reinterpret_cast<VkSemaphore>(1)); }
    void Refresh() { Phase(2); }
};
struct Instance {
    vk::Queue GetGraphicsQueue() const { return vk::Queue(reinterpret_cast<VkQueue>(1)); }
};
namespace ImGui::Core { struct TextureManager { static void Submit() {} }; }
namespace Vulkan {
struct SubmitInfo {
    u32 num_wait_semas{},num_signal_semas{};
    std::array<vk::Semaphore,2> wait_semas{},signal_semas{};
    std::array<u64,2> wait_ticks{},signal_ticks{};
    vk::Fence fence{};
    void AddWait(vk::Semaphore sem,u64 tick) { wait_semas[num_wait_semas]=sem;wait_ticks[num_wait_semas++]=tick; }
    void AddSignal(vk::Semaphore sem,u64 tick) { signal_semas[num_signal_semas]=sem;signal_ticks[num_signal_semas++]=tick; }
};
struct GpuProfiler {
    static GpuProfiler* Get() { return nullptr; }
    bool Records(void*) { return false; }
    template<class F> void Mark(u64,F) {}
};
class Scheduler {
public:
    static std::mutex submit_mutex;
    Semaphore work_semaphore;
    Instance instance;
    std::function<void(SubmitInfo&)> on_submit;
    vk::CommandBuffer current_cmdbuf{reinterpret_cast<VkCommandBuffer>(1)};
    void EndRendering() {}
    void SyncRecording() { Phase(0);recorded=true; }
    void WaitHostCopies() { Phase(1);copied=true; }
    void AllocateWorkerCommandBuffers() { Phase(3); }
    void PopPendingOperations() { Phase(4); }
    void SubmitExecution(SubmitInfo& info);
};
std::mutex Scheduler::submit_mutex;
SCHEDULER_METHOD
}
namespace VideoCore {
struct Arena { vk::Buffer Handle() { return vk::Buffer(reinterpret_cast<VkBuffer>(1)); } };
struct PendingBind { Arena* arena;std::vector<vk::SparseMemoryBind> binds; };
class BufferCache {
public:
    std::vector<PendingBind> pending_binds;
    Semaphore memory_semaphore;
    Instance instance;
    void SubmitPendingArenaBinds(Vulkan::SubmitInfo& info);
};
BIND_METHOD
}

void Prepare(Vulkan::Scheduler& scheduler, VideoCore::BufferCache& cache,VideoCore::Arena& arena) {
    recorded=copied=ended=false;
    cache.pending_binds={{&arena,{vk::SparseMemoryBind{.size=4096}}}};
    scheduler.on_submit=[&](Vulkan::SubmitInfo& info){cache.SubmitPendingArenaBinds(info);};
}
int main() {
    VULKAN_HPP_DEFAULT_DISPATCHER.vkEndCommandBuffer=End;
    VULKAN_HPP_DEFAULT_DISPATCHER.vkQueueSubmit=Submit;
    VULKAN_HPP_DEFAULT_DISPATCHER.vkQueueBindSparse=Bind;
    constexpr bool should_progress=EXPECTED_PROGRESS;
    unsigned progress_cases=0;
    for(int phase=0;phase<5;++phase) {
        Vulkan::Scheduler scheduler;VideoCore::BufferCache cache;VideoCore::Arena arena;
        Prepare(scheduler,cache,arena);
        {std::scoped_lock lock{phase_mutex};target=phase;blocked=released=false;}
        std::thread worker([&]{Vulkan::SubmitInfo info;scheduler.SubmitExecution(info);});
        {std::unique_lock lock{phase_mutex};assert(phase_cv.wait_for(lock,std::chrono::seconds(5),[]{return blocked;}));}
        std::promise<void> done;auto finished=done.get_future();
        std::thread present([&]{std::scoped_lock lock{Vulkan::Scheduler::submit_mutex};QueueCall();++presents;done.set_value();});
        const bool progress=finished.wait_for(std::chrono::milliseconds(150))==std::future_status::ready;
        {std::scoped_lock lock{phase_mutex};released=true;}phase_cv.notify_all();
        worker.join();present.join();
        assert(progress==should_progress);progress_cases+=progress;
        assert(cache.pending_binds.empty());
    }
    {std::scoped_lock lock{phase_mutex};target=-1;}
    Vulkan::Scheduler scheduler;VideoCore::BufferCache cache;VideoCore::Arena arena;
    std::thread present([]{for(int i=0;i<500;++i){std::scoped_lock lock{Vulkan::Scheduler::submit_mutex};QueueCall();++presents;}});
    for(int i=0;i<500;++i) {Prepare(scheduler,cache,arena);Vulkan::SubmitInfo info;scheduler.SubmitExecution(info);}
    present.join();
    assert(!queue_active && submits==505 && binds==505 && presents==505);
    std::printf("Queue lock: %u/5 blocked host phases permit presentation; 505 submit/bind/present calls each serialized; recorder/copy completion and sparse waits retained\n",progress_cases);
}
'''

with tempfile.TemporaryDirectory(prefix='bb-queue-scope-') as directory:
    temp = Path(directory)
    headers = ROOT.parent / 'windows-build/sysroot/clang64/include'
    for name in ('vulkan', 'vk_video'):
        shutil.copytree(headers / name, temp / name)
    for label, revision, progress in [('Revision19', '194e477e148bb99a0841f9f2232ee5565f1b009f', False), ('production', None, True)]:
        scheduler, bind = extract(revision)
        code = HARNESS.replace('SCHEDULER_METHOD', scheduler).replace('BIND_METHOD', bind).replace('EXPECTED_PROGRESS', str(progress).lower())
        (temp / 'queue.cpp').write_text(code)
        subprocess.run(['g++', '-std=c++20', '-O1', '-g', '-pthread', '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-I' + str(temp), str(temp / 'queue.cpp'), '-o', str(temp / 'queue-test')], check=True)
        print(label, flush=True)
        subprocess.run([str(temp / 'queue-test')], check=True, timeout=30)
print('PASS: production Vulkan submission methods preserve queue synchronization without holding it through CPU waits.')
