"""Draw the production system readouts/graph in real ImGui with recorded metrics."""
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'gpu/shim/bbport_overlay.cpp').read_text()
def function(signature):
    a=source.index(signature);b=source.index('{',a)+1;depth=1
    while depth:depth+=(source[b]=='{')-(source[b]=='}');b+=1
    return source[a:b]
functions='\n'.join(function(name) for name in ('bool PlainCounter(', 'ImVec4 PaceColor(',
    'ImVec4 LoadColor(', 'ImVec4 VramColor(', 'void Label(', 'void FrameTimeGraph(',
    'void SystemCounter(', 'bool ReadoutsOn('))
prefix=r'''
#include <algorithm>
#include <array>
#include <atomic>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <string>
#include "bbport_settings.h"
#include "imgui.h"
#include "imgui_internal.h"
using u64=uint64_t;
constexpr ImVec4 PlainValue{.8f,.8f,.8f,1.f};
float base_scale=1,frame_ms_avg=16.667f,counter_bottom=36;
constexpr size_t FrameHistorySize=240;
std::array<float,FrameHistorySize>frame_history{};
size_t frame_history_count=FrameHistorySize,frame_history_next=0;
std::atomic<u64> vram_used{5ull<<30},vram_limit{10ull<<30},vram_pressure{8ull<<30},vram_critical{9ull<<30},vram_card_free{6ull<<30};
std::string gpu_name="Recorded GPU";
struct Metrics {std::atomic<float> gpu{69},cpu{30};std::atomic<u64> ram{4ull<<30},ram_free{12ull<<30};};
Metrics& Load(){static Metrics m;return m;}
const std::string& CpuName(){static std::string name="Recorded CPU";return name;}
'''
main=r'''
int main(){
 ImGui::CreateContext();auto& io=ImGui::GetIO();io.IniFilename=nullptr;io.DisplaySize={1920,1080};io.DeltaTime=1.f/60;
 unsigned char* data;int w,h;io.Fonts->GetTexDataAsRGBA32(&data,&w,&h);
 frame_history.fill(16.667f);frame_history[110]=69.f;const auto original=frame_history;
 auto& s=BbSettings::Get();s.latency_ms=12;s.latency_mode=2;
 unsigned cases=0;
 for(bool master:{false,true})for(unsigned mask=0;mask<128;++mask){
  s.show_fps=master;s.show_frame_times=mask&1;s.show_render_latency=mask&2;s.show_vram=mask&4;
  s.show_gpu=mask&8;s.show_cpu=mask&16;s.show_ram=mask&32;s.show_fps_graph=mask&64;
  assert(ReadoutsOn()==master);
  for(unsigned repeat=0;repeat<3;++repeat){
   ImGui::NewFrame();SystemCounter();ImGui::Render();
   auto* window=ImGui::FindWindowByName("##system_readouts");
   assert(bool(window && window->Active)==(master && mask));
   if(window && window->Active){
    assert(std::isfinite(window->Size.x) && std::isfinite(window->Size.y));
    assert(window->Pos.x>=0 && window->Pos.y>=0);
    assert(window->Pos.x+window->Size.x<=io.DisplaySize.x+1);
    assert(window->Pos.y+window->Size.y<=io.DisplaySize.y+1);
   }
  }
  assert(frame_history==original);++cases;
 }
 ImGui::DestroyContext();std::printf("PASS: %u actual system-overlay combinations; the master switch hides every readout, layout stays bounded and graph samples remain unchanged.\n",cases);
}
'''
with tempfile.TemporaryDirectory(prefix='system-overlay-') as temporary:
    folder=Path(temporary);cpp=folder/'test.cpp';cpp.write_text(prefix+functions+main);binary=folder/'test'
    subprocess.run(['g++','-std=c++23','-O1','-pthread','-I'+str(ROOT/'gpu/shim'),
                    '-I'+str(ROOT/'gpu/third_party/imgui'),str(cpp),str(ROOT/'gpu/shim/bbport_settings.cpp'),
                    *(str(p) for p in (ROOT/'gpu/third_party/imgui').glob('imgui*.cpp') if p.name!='imgui_demo.cpp'),
                    '-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True,timeout=30)
