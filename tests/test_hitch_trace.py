# SPDX-License-Identifier: GPL-2.0-or-later
# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
"""Execute the flight recorder and actual Scheduler command handoff in both modes."""
from pathlib import Path
import os, subprocess, tempfile
ROOT=Path(__file__).resolve().parents[1]
header=(ROOT/'gpu/shadps4/video_core/renderer_vulkan/vk_scheduler.h').read_text()
chunk=header[header.index('class RecordChunk {'):header.index('\nclass Scheduler {')]
start=header.index('    template <typename Func>\n    void Record(')
methods=header[start:header.index('    /// True when Record()',start)]
fixture=r'''
#include "bbport_hitch_trace.h"
#include <array>
#include <atomic>
#include <cassert>
#include <cstddef>
#include <cstring>
#include <memory>
#include <new>
#include <thread>
#include <type_traits>
#include <utility>
#include <vector>
#define ASSERT(x) assert(x)
namespace vk {struct CommandBuffer {};}
namespace BbToggle {constexpr unsigned RecordPrefetch=1,ThreadedRecording=2;bool Disabled(unsigned){return false;}}
@CHUNK@
struct Scheduler {
 bool recording_threaded=true,direct_mode=false;
 vk::CommandBuffer current_cmdbuf;
 std::unique_ptr<RecordChunk> record_chunk=std::make_unique<RecordChunk>();
 std::vector<std::unique_ptr<RecordChunk>> full_chunks;
 std::unique_ptr<RecordChunk> AcquireChunk(){return std::make_unique<RecordChunk>();}
 void SyncRecording(){assert(false);}
 @METHODS@
};
void QueueFixture(Scheduler& scheduler,std::vector<unsigned>& values){
 for(unsigned i=0;i<400;++i){
  std::array<unsigned,512> payload{};payload[0]=i;payload.back()=i^0xcafe;
  scheduler.Record([&,payload,owned=std::make_unique<unsigned>(i)](vk::CommandBuffer){
   assert(payload[0]==*owned && payload.back()==(*owned^0xcafe));values.push_back(*owned);
  });
 }
}
int main(){
 Scheduler scheduler;std::vector<unsigned> values;
 QueueFixture(scheduler,values);assert(values.empty() && scheduler.full_chunks.size()>1);
 std::jthread thread([&]{
  BbHitch::Trace::SetRole("Vulkan recording");
  for(auto& chunk:scheduler.full_chunks)chunk->Execute({});
  scheduler.record_chunk->Execute({});
 });thread.join();
 assert(values.size()==400);for(unsigned i=0;i<400;++i)assert(values[i]==i);
 const auto before=BbHitch::Trace::writes.load();
 assert(before==(BbHitch::Trace::Enabled()?400u:0u));
 for(auto& slot:BbHitch::Trace::journal)if(slot.event.stage){
  assert(std::strcmp(slot.event.stage,"QueueFixture")==0);
  assert(std::strcmp(slot.event.role,"Vulkan recording")==0);
 }
 scheduler.direct_mode=true;bool direct=false;
 scheduler.Record([&](vk::CommandBuffer){direct=true;});assert(direct);
 assert(BbHitch::Trace::writes.load()==before+(BbHitch::Trace::Enabled()?1u:0u));
 std::puts("PASS: actual Scheduler labels follow move-only captures across chunk overflow and worker execution; direct recording and disabled command layout preserve behavior.");
}
'''.replace('@CHUNK@',chunk).replace('@METHODS@',methods)
with tempfile.TemporaryDirectory(prefix='hitch-trace-') as directory:
    directory=Path(directory);cpp=directory/'scheduler.cpp';cpp.write_text(fixture)
    for name,source in [('journal',ROOT/'tests/test_hitch_trace.cpp'),('scheduler',cpp)]:
        binary=directory/name
        subprocess.run(['g++','-std=c++20','-O2','-pthread','-UNDEBUG','-I'+str(ROOT/'gpu/shim'),str(source),'-o',str(binary)],check=True)
        for enabled in (False,True):
            env=dict(os.environ);env.pop('BB_HITCH_TRACE',None)
            if enabled:env['BB_HITCH_TRACE']='1'
            subprocess.run([str(binary)],env=env,check=True,timeout=30)
