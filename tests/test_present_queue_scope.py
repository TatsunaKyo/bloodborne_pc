# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Execute the production presentation block with held SDK/queue phases."""
from pathlib import Path
import subprocess,tempfile,argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument("--prepare",type=Path,help="Write fixture C++ for a native Windows compiler")
args=parser.parse_args()
ROOT=Path(__file__).resolve().parents[1]
PATH='gpu/shadps4/video_core/renderer_vulkan/vk_presenter.cpp'
def block(source):
 a=source.index('        bool presented;');b=source.index('        BbOverlay::RecordPresent',a)
 return source[a:b]
HARNESS=r'''
#include "bbport_hitch.h"
#include <cassert>
#include <chrono>
#include <condition_variable>
#include <functional>
#include <future>
#include <mutex>
#include <cstdio>
using namespace std::chrono_literals;
std::mutex gate;std::condition_variable cv;bool entered=false,released=false;int phase;
void Hold(int p){std::unique_lock l(gate);if(phase!=p)return;entered=true;cv.notify_all();cv.wait(l,[]{return released;});}
struct Scheduler{static std::mutex submit_mutex;};std::mutex Scheduler::submit_mutex;
namespace Vulkan { using Scheduler=::Scheduler; }
namespace BbAmd{void BeforePresent(int,bool){}}
namespace BbNvidia{bool Present(void*,const std::function<bool()>& f){Hold(0);bool r=f();Hold(1);return r;}}
struct Frame{int amd_token=1;BbHitch::FramePath hitch_path;};
struct Window{int GetWidth(){return 1920;}int GetHeight(){return 1080;}};
struct Swapchain{bool Present(){Hold(2);return true;}void Recreate(int,int){assert(false);}};
void Present(){Frame value;Frame* frame=&value;Window window;Swapchain swapchain;bool final=true,is_game_frame=true,is_reusing_frame=false;
BLOCK
assert(presented);}
struct Device{int waitIdle(){Hold(3);return 7;}};
void Drain(){Device device;
DRAIN
assert(idle==7);}
int main(){
 for(phase=0;phase<3;++phase){
  entered=released=false;
  auto present=std::async(std::launch::async,Present);
  {std::unique_lock l(gate);assert(cv.wait_for(l,2s,[]{return entered;}));}
  auto submit=std::async(std::launch::async,[]{std::scoped_lock l(Scheduler::submit_mutex);});
  bool progress=submit.wait_for(100ms)==std::future_status::ready;
  {std::scoped_lock l(gate);released=true;}cv.notify_all();present.get();submit.get();
  assert(progress==(EXPECTED && phase!=2));
 }
 if(EXPECTED){
  phase=3;entered=released=false;
  auto drain=std::async(std::launch::async,Drain);
  {std::unique_lock l(gate);assert(cv.wait_for(l,2s,[]{return entered;}));}
  auto submit=std::async(std::launch::async,[]{std::scoped_lock l(Scheduler::submit_mutex);});
  bool progress=submit.wait_for(100ms)==std::future_status::ready;
  {std::scoped_lock l(gate);released=true;}cv.notify_all();drain.get();submit.get();
  assert(!progress);std::puts("PASS production NVIDIA failed-state drain: client queue operations excluded");
 }
 std::puts(EXPECTED?"PASS production present: SDK delays allow rendering; QueuePresent remains serialized":"PASS Revision24 control: SDK work blocks the shared queue");
}
'''
with tempfile.TemporaryDirectory(prefix='crowned-present-') as folder:
 folder=args.prepare.resolve() if args.prepare else Path(folder)
 folder.mkdir(parents=True,exist_ok=True)
 nv=(ROOT/'gpu/shim/bbport_nvidia.cpp').read_text()
 start=nv.index('            const auto idle=[&] {')
 end=nv.index('            }();',start)+len('            }();')
 drain=nv[start:end]
 old=subprocess.check_output(['git','show','4c933548259717befb2d92a4bfec9da24689d590:'+PATH],cwd=ROOT,text=True)
 for label,source,expected in [('revision24',old,False),('current',(ROOT/PATH).read_text(),True)]:
  cpp=folder/(label+'.cpp');exe=folder/label
  cpp.write_text(HARNESS.replace('BLOCK',block(source)).replace('DRAIN',drain).replace('EXPECTED','true' if expected else 'false'))
  if args.prepare:continue
  subprocess.run(['g++','-std=c++20','-pthread','-O1','-Wall','-Wextra','-Werror','-I'+str(ROOT/'gpu/shim'),str(cpp),'-o',str(exe)],check=True)
  subprocess.run([str(exe)],check=True,timeout=20)
