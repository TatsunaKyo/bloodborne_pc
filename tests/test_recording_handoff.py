# SPDX-License-Identifier: GPL-2.0-or-later
# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
"""Execute the production chunk handoff with recording re-entry at publication."""
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
PATH='gpu/shadps4/video_core/renderer_vulkan/vk_scheduler.cpp'
BASE='2fe3a67fc3c2930352bb88af57f881b9b0829494'
FIXTURE=r'''
#include <atomic>
#include <cassert>
#include <condition_variable>
#include <cstdio>
#include <functional>
#include <memory>
#include <mutex>
#include <utility>
#include <vector>
struct RecordChunk {
    std::vector<int> commands;
    bool Empty()const{return commands.empty();}
    size_t Size()const{return commands.size()*4;}
};
struct Queue {
    std::vector<std::unique_ptr<RecordChunk>> items;std::function<void()> probe;
    void push_back(std::unique_ptr<RecordChunk>&& c){items.push_back(std::move(c));if(probe)probe();}
    size_t size()const{return items.size();}
};
class Scheduler {
public:
    bool recording_threaded=true,direct_mode=true,recorder_sleeping=true;
    std::unique_ptr<RecordChunk> record_chunk=std::make_unique<RecordChunk>();
    std::vector<std::unique_ptr<RecordChunk>> full_chunks;
    Queue recorder_queue;std::mutex recorder_mutex;std::atomic<size_t> queued_chunks{};
    std::condition_variable recorder_cv;unsigned unsafe=0;
    std::unique_ptr<RecordChunk> AcquireChunk(){if(!record_chunk)++unsafe;return std::make_unique<RecordChunk>();}
    void KickRecording(bool force);
};
@METHOD@
int main(){
    Scheduler scheduler;scheduler.record_chunk->commands={1,2};
    auto full=std::make_unique<RecordChunk>();full->commands={-1};scheduler.full_chunks.push_back(std::move(full));
    scheduler.recorder_queue.probe=[&]{
        if(!scheduler.record_chunk){++scheduler.unsafe;return;}
        if(scheduler.recorder_queue.size()==2)scheduler.record_chunk->commands.push_back(3);
    };
    scheduler.KickRecording(true);
#if CONTROL
    assert(scheduler.unsafe>0);std::puts("R42 CONTROL: recording re-entry observes an absent current chunk during publication/allocation.");
#else
    assert(!scheduler.unsafe && !scheduler.direct_mode && scheduler.queued_chunks==2);
    assert(scheduler.recorder_queue.items[0]->commands==std::vector<int>{-1});
    assert(scheduler.recorder_queue.items[1]->commands==(std::vector<int>{1,2}));
    assert(scheduler.record_chunk->commands==std::vector<int>{3});
    scheduler.recorder_queue.probe={};scheduler.KickRecording(true);
    assert(scheduler.recorder_queue.items[2]->commands==std::vector<int>{3});
    assert(scheduler.record_chunk && scheduler.record_chunk->Empty() && scheduler.full_chunks.empty());
    std::puts("PASS: actual chunk handoff keeps a valid recording target throughout publication/allocation; re-entered commands remain ordered after the published work.");
#endif
}
'''


def main():
    with tempfile.TemporaryDirectory(prefix='record-handoff-') as temporary:
        folder=Path(temporary)
        for name,control in [('r42',True),('current',False)]:
            code=(subprocess.check_output(['git','show',BASE+':'+PATH],cwd=ROOT,text=True)
                  if control else (ROOT/PATH).read_text())
            start=code.index('void Scheduler::KickRecording(')
            method=code[start:code.index('\nvoid Scheduler::SyncRecording()',start)]
            source=folder/(name+'.cpp');binary=folder/name;source.write_text(FIXTURE.replace('@METHOD@',method))
            subprocess.run(['g++','-std=c++20','-O1','-UNDEBUG','-pthread','-DCONTROL='+str(int(control)),str(source),'-o',str(binary)],check=True)
            subprocess.run([str(binary)],check=True,timeout=15)


if __name__=='__main__':main()
