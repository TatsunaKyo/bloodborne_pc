# SPDX-License-Identifier: GPL-2.0-or-later
"""Block diagnostic driver IO and execute the production Present prefix."""
from pathlib import Path
import os,shlex,subprocess,tempfile
root=Path(__file__).resolve().parents[1];name='gpu/shim/bbport_nvidia.cpp'
current=(root/name).read_text()
baseline=subprocess.check_output(['git','show','1139ab91d367e4fd1e5a9507ce11ca450da82729:'+name],cwd=root,text=True)
prefix=r'''
#include "bbport_nvidia_preset.h"
#include <atomic>
#include <cassert>
#include <chrono>
#include <cstdio>
#include <functional>
#include <future>
#include <mutex>
namespace sl {enum class PCLMarker{ePresentEnd};}
namespace Vulkan {struct Frame{int nvidia_token{};};}
namespace BbNvidia {
bool initialized=true;std::mutex mutex;
void Mark(sl::PCLMarker,int){}
std::promise<void> entered,release;
auto gate=release.get_future().share();std::atomic<bool> first{};
void UpdateLatency(){if(!first.exchange(true))entered.set_value();gate.wait();}
'''
main=r'''
}
int main(){
 using namespace std::chrono_literals;using namespace BbNvidia;
 BbNvidia::Preset::Observer observer;
 observer.Start(UpdateLatency,[]{});
 assert(entered.get_future().wait_for(2s)==std::future_status::ready);
 Vulkan::Frame frame;auto present=std::async(std::launch::async,[&]{return Present(&frame,[]{return true;});});
 const bool blocked=present.wait_for(50ms)==std::future_status::timeout;
 release.set_value();assert(present.get());observer.Stop();
 assert(blocked==bool(EXPECT_BLOCKED));
 std::printf("PASS: %s production Present prefix while diagnostic IO is blocked.\n",blocked?"R40 blocks":"Current returns");
}
'''
with tempfile.TemporaryDirectory(prefix='bb-present-telemetry-') as d:
 p=Path(d)
 for label,s,expected in [('control',baseline,1),('current',current,0)]:
  a=s.index('bool Present(Vulkan::Frame*');b=s.index('    if (fg_state && fg_on)',a)
  body=s[a:b]+'    return presented;\n}\n'
  f=p/(label+'.cpp');f.write_text(prefix+body+main)
  exe=p/label
  subprocess.run(shlex.split(os.environ.get('CXX','g++'))+['-std=c++20','-O2','-pthread','-DEXPECT_BLOCKED='+str(expected),'-I'+str(root/'gpu/shim'),str(f),'-o',str(exe)],check=True)
  subprocess.run([str(exe)],check=True)
