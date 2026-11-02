"""Exercise production provider/latency ownership across startup and live requests."""
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
def function(path,signature):
    source=(ROOT/path).read_text();a=source.index(signature);b=source.index('{',a)+1;depth=1
    while depth:depth+=(source[b]=='{')-(source[b]=='}');b+=1
    return source[a:b]
nvidia=function('gpu/shim/bbport_nvidia.cpp','bool Wanted()')
low='gpu/shadps4/video_core/renderer_vulkan/vk_low_latency.cpp'
native=function(low,'bool OwnsLatency()')+'\n'+function(low,'bool Wanted()')
source=r'''
#include "bbport_settings.h"
#include <cassert>
#include <cstdio>
#include <string_view>
namespace Nvidia {@NVIDIA@}
namespace Native {std::string_view requested;auto Setting(){return requested;} @NATIVE@}
int main(){
 using namespace BbSettings;auto& s=Get();unsigned cases=0;
 for(bool sdk:{false,true})for(bool native_dlss:{false,true})
 for(int route=0;route<=FrameGenerationNativeFsr402;++route)
 for(int reflex:{0,1,2})for(bool amd:{false,true})for(bool focused:{false,true})
 for(int background:{BackgroundRun,BackgroundPause,Background30,Background60}) {
  s.startup_workshop_nvidia=sdk;s.startup_native_dlss=native_dlss;
  s.frame_generation=route;s.frame_gen=NativeForRoute(route);
  s.fg401_fallback=-1;s.fg401_fallback_source=-1;
  s.reflex=reflex;s.amd_antilag=amd;s.show_fps=false;s.show_latency=false;
  s.window_focused=focused;s.background_mode=background;
  assert(!(Nvidia::Wanted() && Native::Wanted()));
  assert(Native::OwnsLatency()==(!sdk && (focused || background==BackgroundRun)));
  assert(Nvidia::Wanted()==(sdk && (reflex || route==FrameGenerationNvidia) &&
                           (focused || background==BackgroundRun)));
  const bool active_native=!sdk && route>=FrameGenerationNativeFsr &&
      (route!=FrameGenerationNativeDlss || native_dlss);
  assert(s.ActiveFrameGen()==(active_native?NativeForRoute(route):FrameGenOff));
  assert(s.WantsWorkshopInputs()==(route==FrameGenerationFsr || (sdk && route==FrameGenerationNvidia)));
  ++cases;
 }
 // Runtime ML fallback preserves the persisted request.
 SelectFrameGen(FrameGenFsr402);s.startup_workshop_nvidia=false;
 FrameGenFailure(FrameGenFsr402,"fixture rejection");
 assert(s.frame_gen==FrameGenFsr402 && s.frame_generation==FrameGenerationNativeFsr402);
 assert(s.ActiveFrameGen()==FrameGenFsr3);
 FrameGenFailure(FrameGenFsr3,"fallback rejection");assert(s.ActiveFrameGen()==FrameGenOff);
 std::printf("PASS: %u provider/latency ownership cases; no double owner, restart gates, frozen-input routing and saved ML request survive fallback.\n",cases);
}
'''.replace('@NVIDIA@',nvidia).replace('@NATIVE@',native)
with tempfile.TemporaryDirectory(prefix='graphics-session-') as temporary:
    folder=Path(temporary);cpp=folder/'test.cpp';cpp.write_text(source);binary=folder/'test'
    subprocess.run(['g++','-std=c++23','-O1','-pthread','-I'+str(ROOT/'gpu/shim'),str(cpp),
                    str(ROOT/'gpu/shim/bbport_settings.cpp'),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True,timeout=20)
