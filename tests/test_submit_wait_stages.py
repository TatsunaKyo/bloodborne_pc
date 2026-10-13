# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Capture the real Scheduler submission and check transfer/compute dependencies."""
import argparse
import ast
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
PATH='gpu/shadps4/video_core/renderer_vulkan/vk_scheduler.cpp'
BASE='ff2025092cef9825837e22b8ccbdbc75db68ee5d'


def prepare(folder):
    folder.mkdir(parents=True,exist_ok=True)
    # Reuse the existing Vulkan entry-point recorder and CPU-preparation stubs.
    tree=ast.parse((ROOT/'tests/test_queue_lock_scope.py').read_text())
    harness=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
                 and any(isinstance(t,ast.Name) and t.id=='HARNESS' for t in n.targets))
    start=harness.index('VKAPI_ATTR VkResult VKAPI_CALL Submit(')
    end=harness.index('VKAPI_ATTR VkResult VKAPI_CALL Bind(',start)
    harness=harness[:start]+r'''
unsigned incomplete_waits=0,waits_checked=0;
VKAPI_ATTR VkResult VKAPI_CALL Submit(VkQueue,u32 count,const VkSubmitInfo* info,VkFence) {
    assert(recorded && copied && ended && count==1);
    const auto* timeline=static_cast<const VkTimelineSemaphoreSubmitInfo*>(info->pNext);
    assert(timeline->waitSemaphoreValueCount==info->waitSemaphoreCount);
    for(u32 i=0;i<info->waitSemaphoreCount;++i) {
        assert(timeline->pWaitSemaphoreValues[i]==7+i);
        const auto stages=info->pWaitDstStageMask[i];
        // An earlier transfer/compute consumer must not bypass frame-ready waits.
        const bool transfer=(stages&(VK_PIPELINE_STAGE_ALL_COMMANDS_BIT|VK_PIPELINE_STAGE_TRANSFER_BIT))!=0;
        const bool compute=(stages&(VK_PIPELINE_STAGE_ALL_COMMANDS_BIT|VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT))!=0;
        incomplete_waits+=!(transfer&&compute);++waits_checked;
    }
    QueueCall();++submits;return VK_SUCCESS;
}
''' + harness[end:]
    harness=harness.replace('std::array<vk::Semaphore,2>','std::array<vk::Semaphore,4>')
    harness=harness.replace('std::array<u64,2>','std::array<u64,4>')
    main=harness.index('int main()')
    harness=harness[:main]+r'''
int main() {
    VULKAN_HPP_DEFAULT_DISPATCHER.vkEndCommandBuffer=End;
    VULKAN_HPP_DEFAULT_DISPATCHER.vkQueueSubmit=Submit;
    VULKAN_HPP_DEFAULT_DISPATCHER.vkQueueBindSparse=Bind;
    const unsigned maximum=CORRECTED ? 4 : 2;
    for(unsigned count=0;count<=maximum;++count) {
        Vulkan::Scheduler scheduler;Vulkan::SubmitInfo info{};
        recorded=copied=true;ended=false;
        for(unsigned i=0;i<count;++i)info.AddWait(vk::Semaphore(reinterpret_cast<VkSemaphore>(uint64_t(i+1))),7+i);
        scheduler.SubmitExecution(info);
    }
    if(CORRECTED) {
        assert(incomplete_waits==0 && waits_checked==10);
        std::puts("PASS: production submissions gate transfer/compute on every dependency, with 0/1/2/3/4 waits; timelines preserved.");
    } else {
        assert(incomplete_waits==1);
        std::puts("PASS: unchanged Revision 29 reproduces the frame-ready wait that permits early transfer/compute reads.");
    }
}
'''
    for label,ref in [('revision29',BASE),('current',None)]:
        source=subprocess.check_output(['git','show',ref+':'+PATH],cwd=ROOT,text=True) if ref else (ROOT/PATH).read_text()
        method=source[source.index('void Scheduler::SubmitExecution('):source.index('void Scheduler::PriorityPendingOpsThread(')]
        # This harness does not use sparse-bind methods, but their stub declaration
        # remains available in the shared recorder.
        bind=(ROOT/'gpu/shadps4/video_core/buffer_cache/buffer_cache.cpp').read_text()
        bind=bind[bind.index('void BufferCache::SubmitPendingArenaBinds('):bind.index('} // namespace VideoCore',bind.index('void BufferCache::SubmitPendingArenaBinds('))]
        program=harness.replace('SCHEDULER_METHOD',method).replace('BIND_METHOD',bind).replace('CORRECTED','true' if ref is None else 'false')
        (folder/(label+'.cpp')).write_text(program)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare',type=Path)
    args=parser.parse_args()
    if args.prepare:prepare(args.prepare)
    else:
        with tempfile.TemporaryDirectory(prefix='workshop-submit-waits-') as temporary:
            folder=Path(temporary);prepare(folder)
            for name in ['revision29','current']:
                binary=folder/name
                subprocess.run(['g++','-std=c++23','-pthread','-UNDEBUG','-Iout/test-headers',str(folder/(name+'.cpp')),'-o',str(binary)],cwd=ROOT,check=True)
                subprocess.run([str(binary)],cwd=ROOT,check=True,timeout=30)
