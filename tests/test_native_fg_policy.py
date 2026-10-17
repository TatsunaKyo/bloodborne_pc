"""Simulate the production Supermedo presentation policy and provider-family choices."""
from pathlib import Path
import subprocess,tempfile
root=Path(__file__).resolve().parents[1]
def fn(text,name):
 a=text.index(name);a=text.rfind('\n',0,a)+1;b=text.index('{',a)+1;depth=1
 while depth:depth+=(text[b]=='{')-(text[b]=='}');b+=1
 return text[a:b]
policy=fn((root/'gpu/shadps4/video_core/renderer_vulkan/vk_presenter.cpp').read_text(),'void Presenter::UpdateFrameGenLimit(').replace('std::chrono::steady_clock','FakeClock')
provider=fn((root/'gpu/shim/bbport_settings.cpp').read_text(),'int NativeProvider(')
count=fn((root/'gpu/shadps4/video_core/renderer_vulkan/vk_native_frame_generation.cpp').read_text(),'u32 FrameGenerator::WantedCount(')
text=r'''
#include "bbport_settings.h"
#include <cassert>
#include <chrono>
#include <atomic>
#include <algorithm>
#include <cstdint>
#include <cstdio>
using u32=uint32_t;
namespace BbSettings {Values values;Values& Get(){return values;} @PROVIDER@ }
struct FakeClock {using duration=std::chrono::nanoseconds;using time_point=std::chrono::time_point<FakeClock,duration>;static inline duration time=std::chrono::seconds(100);static time_point now(){return time_point(time);}};
u32 hz=120;u32 BbDisplayRefreshHz(){return hz;}int gpu_max=3;int DlssMaxCount(){return gpu_max;}
struct FrameGenerator{static constexpr u32 MaxGenerated=3;u32 WantedCount()const;};
@COUNT@
struct Presenter {
 std::atomic<double> game_frame_ms{1000.0/60};std::atomic<u32> frame_gen_limit{3};double present_busy=0;
 int frame_gen_hold_seconds=5;FakeClock::time_point frame_gen_hold_until{},limit_window=FakeClock::now();u32 limit_frames=0,limit_up_seconds=0;
 struct Swapchain {bool fifo=false;bool WaitsForDisplay()const{return fifo;}}swapchain;
 FrameGenerator generator;FrameGenerator* native_frame_generator=&generator;
 void UpdateFrameGenLimit(bool,double);
};
@POLICY@
void advance(int frames){FakeClock::time+=std::chrono::nanoseconds((1000000000ll/60)*frames);}
int main(){auto& s=BbSettings::Get();FrameGenerator gen;
 for(bool startup:{false,true}){s.startup_native_dlss=startup;
  s.frame_generation=BbSettings::FrameGenerationOff;assert(BbSettings::NativeProvider()==BbSettings::FrameGenOff);
  s.frame_generation=BbSettings::FrameGenerationNvidia;assert(BbSettings::NativeProvider()==BbSettings::FrameGenOff);
  s.frame_generation=BbSettings::FrameGenerationNativeFsr;assert(BbSettings::NativeProvider()==BbSettings::FrameGenFsr3 && gen.WantedCount()==1);
  s.frame_generation=BbSettings::FrameGenerationNativeDlss;assert(BbSettings::NativeProvider()==(startup?BbSettings::FrameGenDlss:BbSettings::FrameGenOff));
 }
 s.startup_native_dlss=true;s.frame_generation=BbSettings::FrameGenerationNativeDlss;s.frame_gen_multiplier=4;
 gpu_max=1;assert(gen.WantedCount()==1);gpu_max=3;assert(gen.WantedCount()==3);
 Presenter p;p.swapchain.fifo=true;p.UpdateFrameGenLimit(true,1);assert(s.frame_gen_flip_limit==30);
 gpu_max=1;p.UpdateFrameGenLimit(true,1);assert(s.frame_gen_flip_limit==60);
 p.swapchain.fifo=false;p.UpdateFrameGenLimit(true,1);assert(s.frame_gen_flip_limit==0);
 p.UpdateFrameGenLimit(false,1);assert(s.frame_gen_now==0 && s.frame_gen_flip_limit==0);
 s.frame_generation=BbSettings::FrameGenerationNativeFsr;s.frame_gen_fit_display=true;hz=60;
 for(unsigned i=0;i<180;++i){advance(1);p.UpdateFrameGenLimit(true,1);}assert(p.frame_gen_limit==0);
 s.frame_gen_fit_display=false;hz=120;p.UpdateFrameGenLimit(true,1);assert(p.frame_gen_limit==3);
 for(int i=0;i<100;++i){advance(1);p.UpdateFrameGenLimit(true,30);if(p.frame_gen_limit==0)break;}
 assert(p.frame_gen_limit==0);FakeClock::time=p.frame_gen_hold_until.time_since_epoch()+std::chrono::seconds(1);p.UpdateFrameGenLimit(true,1);assert(p.frame_gen_limit==3);
 std::puts("PASS production native FG simulation: isolated provider families, RTX 40/50 multiplier bounds, 120-Hz FIFO real caps 60/30, Mailbox, display-fit hysteresis, bounded overload pause and recovery.");
}
'''
with tempfile.TemporaryDirectory(prefix='native-fg-policy-') as d:
 d=Path(d);cpp=d/'test.cpp';cpp.write_text(text.replace('@PROVIDER@',provider).replace('@COUNT@',count).replace('@POLICY@',policy));exe=d/'test'
 subprocess.run(['g++','-std=c++20','-O1','-I'+str(root/'gpu/shim'),str(cpp),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True,timeout=30)
