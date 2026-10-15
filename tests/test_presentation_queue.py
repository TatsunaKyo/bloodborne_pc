# SPDX-License-Identifier: GPL-2.0-or-later
# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
"""Record actual Scheduler submissions, queue routing and every frame-ready wait.

This dispatch fixture tests command routing and ownership, not GPU throughput.
"""
import ast
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
BASE='2fe3a67fc3c2930352bb88af57f881b9b0829494'
PATH='gpu/shadps4/video_core/renderer_vulkan/vk_scheduler.cpp'


def main():
    tree=ast.parse((ROOT/'tests/test_queue_lock_scope.py').read_text())
    harness=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
                 and any(isinstance(t,ast.Name) and t.id=='HARNESS' for t in n.targets))
    start=harness.index('VKAPI_ATTR VkResult VKAPI_CALL Submit(')
    end=harness.index('VKAPI_ATTR VkResult VKAPI_CALL Bind(',start)
    harness=harness[:start]+r'''
VkQueue actual_queue{};unsigned dependencies{};
VKAPI_ATTR VkResult VKAPI_CALL Submit(VkQueue queue,u32 count,const VkSubmitInfo* info,VkFence) {
    assert(recorded && copied && ended && count==1);
    actual_queue=queue;dependencies=info->waitSemaphoreCount;
    const auto* timeline=static_cast<const VkTimelineSemaphoreSubmitInfo*>(info->pNext);
    assert(timeline->waitSemaphoreValueCount==dependencies);
    for(unsigned i=0;i<dependencies;++i){
        assert(timeline->pWaitSemaphoreValues[i]==7+i);
        assert(info->pWaitDstStageMask[i]&VK_PIPELINE_STAGE_ALL_COMMANDS_BIT);
    }
    return VK_SUCCESS;
}
'''+harness[end:]
    harness=harness[:harness.index('int main()')]+r'''
int main(){
    using Vulkan::QueuePlan::PresentIndex;
    for(unsigned count=0;count<17;++count){
        assert(PresentIndex(0x10de,count)==(count>=2?1u:0u));
        assert(PresentIndex(0x1002,count)==0 && PresentIndex(0x8086,count)==0);
    }
    VULKAN_HPP_DEFAULT_DISPATCHER.vkEndCommandBuffer=End;
    VULKAN_HPP_DEFAULT_DISPATCHER.vkQueueSubmit=Submit;
    Vulkan::Scheduler draw,present;
    present.submission_queue=vk::Queue(reinterpret_cast<VkQueue>(2));
    Vulkan::SubmitInfo frame;
    frame.AddWait(vk::Semaphore(reinterpret_cast<VkSemaphore>(7)),7);
    frame.AddWait(vk::Semaphore(reinterpret_cast<VkSemaphore>(8)),8);
    recorded=copied=true;ended=false;
    present.SubmitExecution(frame);
    assert(dependencies==2);
#if CONTROL
    assert(actual_queue==reinterpret_cast<VkQueue>(1));
    std::puts("R42 CONTROL: the presentation submission ignores its queue and puts swapchain/frame-ready waits in the guest graphics queue.");
#else
    assert(actual_queue==reinterpret_cast<VkQueue>(2));
    Vulkan::SubmitInfo work;ended=false;draw.SubmitExecution(work);
    assert(actual_queue==reinterpret_cast<VkQueue>(1) && dependencies==0);
    std::puts("PASS: actual presentation submissions use queue 1 (second queue), with acquisition/frame-ready dependencies intact; guest rendering uses queue 0. Single-queue and non-NVIDIA adapters retain queue 0.");
#endif
}
'''
    harness='#include "video_core/renderer_vulkan/queue_plan.h"\n'+harness
    bind=(ROOT/'gpu/shadps4/video_core/buffer_cache/buffer_cache.cpp').read_text()
    bind=bind[bind.index('void BufferCache::SubmitPendingArenaBinds('):bind.index('} // namespace VideoCore',bind.index('void BufferCache::SubmitPendingArenaBinds('))]
    with tempfile.TemporaryDirectory(prefix='present-queue-') as temporary:
        folder=Path(temporary)
        for name,control in [('r42',True),('current',False)]:
            source=(subprocess.check_output(['git','show',BASE+':'+PATH],cwd=ROOT,text=True)
                    if control else (ROOT/PATH).read_text())
            method=source[source.index('void Scheduler::SubmitExecution('):source.index('void Scheduler::PriorityPendingOpsThread(')]
            cpp=folder/(name+'.cpp');binary=folder/name
            cpp.write_text(harness.replace('SCHEDULER_METHOD',method).replace('BIND_METHOD',bind))
            subprocess.run(['g++','-std=c++20','-O1','-UNDEBUG','-pthread','-DCONTROL='+str(int(control)),
                '-I'+str(ROOT/'gpu/shadps4'),'-I'+str(ROOT/'gpu/shim'),'-I'+str(ROOT/'out/test-headers'),str(cpp),'-o',str(binary)],check=True)
            subprocess.run([str(binary)],check=True,timeout=15)


if __name__=='__main__':main()
