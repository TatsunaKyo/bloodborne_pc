"""Execute the production queue/exporter and validate bounded private capture packaging."""
from pathlib import Path
import hashlib, json, os, subprocess, sys, tempfile, zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from fg_diagnostic import cpu_timeline, export_capture, TIMELINE_BUDGET
from support_report import Redactor
fixture=r'''
#include "bbport_hitch_trace.h"
#include "bbport_page_watch_queue.h"
#include <atomic>
#include <cassert>
#include <cstdio>
#include <cstring>
using namespace std::chrono_literals;
std::atomic<bool> entered{},release{};
void Apply(uintptr_t,uint64_t,uint32_t){entered=true;while(!release)std::this_thread::yield();}
int main(int argc,char**){
 using namespace BbHitch::Trace;
 InstallExporter();
 if(!Enabled()){assert(!exporter.load());return 0;}
 assert(exporter.load());
 if(argc>1){
  for(unsigned i=0;i<12;++i){
   const auto now=Clock::now();std::vector<Event> events(16384);
   for(auto& e:events)e={"guest snapshot","copy",now,now+1us,1,0x100000,4096,1,0,1};
   exporter.load()("limit-control",now,now+2us,std::move(events),0,0,false);FlushExporter();
  }
  return 0;
 }
 const auto begin=Clock::now();
 {
  BbPageWatch::Queue<> queue{Apply};queue.Push(0x100000,4096,2,0x100000);
  while(!entered)std::this_thread::yield();
  std::thread reader([&]{SetRole("snapshot test");Scope snapshot{"guest snapshot",0x100000,4096};queue.WaitRange(0x100000,4096);});
  bool registered=false;const auto end=Clock::now()+2s;
  while(!registered){
   assert(Clock::now()<end);
   for(auto& slot:journal){
    if(slot.busy.test_and_set(std::memory_order_acquire))continue;
    const auto event=slot.event;slot.busy.clear(std::memory_order_release);
    registered|=event.stage && std::strcmp(event.stage,"snapshot requires watch")==0;
   }
  }
  release=true;reader.join();queue.Wait();
 }
 Report("controlled-hitch",begin,Clock::now()+1us);FlushExporter();
 puts("PASS: actual queue request/installation/dependency events exported after protected snapshot retirement.");
}
'''
with tempfile.TemporaryDirectory(prefix='cpu-timeline-') as directory:
 root=Path(directory);cpp=root/'timeline.cpp';cpp.write_text(fixture);exe=root/'timeline'
 subprocess.run([os.environ.get('CXX','g++'),'-std=c++20','-O2','-pthread','-Wall','-Wextra','-Werror',
                 '-I'+str(ROOT/'gpu/shim'),str(cpp),str(ROOT/'gpu/shim/bbport_hitch_export.cpp'),'-o',str(exe)],check=True)
 path=root/'cpu-timeline.jsonl';env={**os.environ,'BB_HITCH_TRACE':'1','BB_HITCH_TRACE_PATH':str(path)}
 subprocess.run([str(exe)],env=env,check=True,timeout=20)
 records=[json.loads(line) for line in path.read_text().splitlines()]
 assert records[0]['record']=='clock' and records[0]['window_limited']
 events=[e for r in records if r['record']=='window' for e in r['events']]
 assert events==sorted(events,key=lambda e:e['start_ns'])
 stages={e['stage']:e for e in events}
 assert {'page protection queued','page protection installed','snapshot requires watch',
         'snapshot protection dependency','guest snapshot'} <= stages.keys()
 assert all(e['os_thread']>0 for e in events) and len({e['os_thread'] for e in events})>=2
 assert stages['snapshot requires watch']['depends_on']==stages['page protection installed']['id']
 assert stages['snapshot protection dependency']['id']==stages['snapshot requires watch']['id']
 assert stages['page protection installed']['end_ns']<=stages['snapshot protection dependency']['end_ns']
 warnings=[];data,info=cpu_timeline(path,Redactor(),warnings)
 assert info['status']=='captured' and info['windows']==1 and info['events']==len(events) and not warnings
 records[0]['private_path']='D:\\secret\\password';records[-1]['password']='not exported'
 records[-1]['events'][0]['private_path']='secret'
 path.write_text('\n'.join(json.dumps(r) for r in records)+'\n{"record":')
 warnings=[];data,info=cpu_timeline(path,Redactor(),warnings)
 assert info['status']=='incomplete' and info['windows']==1 and warnings
 assert b'private_path' not in data and b'password' not in data
 # Include and hash the real native output through the normal capture exporter.
 path.write_bytes(data);(root/'session.log').write_text('controlled CPU trace\n')
 result=export_capture(root,root,{'revision':'test','traversal_diagnostic':True,
                               'cpu_hitch_trace':{'causal_timeline':True,'timeline_maximum_bytes':TIMELINE_BUDGET}})
 with zipfile.ZipFile(root/result['archive']) as archive:
  assert archive.testzip() is None
  manifest=json.loads(archive.read('archive-integrity.json'))
  for name,item in manifest.items():
   raw=archive.read(name);assert len(raw)==item['bytes'] and hashlib.sha256(raw).hexdigest()==item['sha256']
  assert archive.read('cpu-timeline.jsonl')==data
  assert json.loads(archive.read('session.json'))['cpu_timeline']['windows']==1
 linked=root/'linked.jsonl';linked.symlink_to(path)
 assert cpu_timeline(linked,Redactor(),[])[1]['status']=='rejected'
 disabled=root/'disabled.jsonl';disabled_env={**env,'BB_HITCH_TRACE':'0','BB_HITCH_TRACE_PATH':str(disabled)}
 subprocess.run([str(exe)],env=disabled_env,check=True,timeout=20);assert not disabled.exists()
 large=root/'large.jsonl'
 subprocess.run([str(exe),'large'],env={**env,'BB_HITCH_TRACE_PATH':str(large)},check=True,timeout=40)
 assert large.stat().st_size<=TIMELINE_BUDGET
 lines=[json.loads(line) for line in large.read_text().splitlines()]
 assert lines[-1]=={'record':'limit','reason':'16 MiB limit'}
 print('PASS: production timeline JSON, chronology/native thread IDs/request links, interrupted-tail recovery, field redaction, archive CRC/hashes, symlink rejection, disabled path and hard 16 MiB limit.')
