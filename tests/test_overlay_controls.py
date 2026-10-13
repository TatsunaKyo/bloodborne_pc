from pathlib import Path
import ast
import re
import argparse
import shlex
import subprocess
import tempfile
import os

parser=argparse.ArgumentParser()
parser.add_argument('--compiler', default=os.environ.get('CXX','clang++'))
parser.add_argument('--capture-dir', help='Export real ImGui draw data for menu previews')
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
source = (root / 'gpu/shim/bbport_overlay.cpp').read_text()
temporary=tempfile.TemporaryDirectory(prefix='bbport-controls-')
scratch=Path(temporary.name)

literal = r'"(?:[^"\\]|\\.)*"(?:\s*"(?:[^"\\]|\\.)*")*'
def decode(text):
    return ''.join(ast.literal_eval(part) for part in re.findall(r'"(?:[^"\\]|\\.)*"', text))
pairs = re.findall(r'Text\(('+literal+r'),\s*('+literal+r')\)',source)
assert len(pairs) >= 60
formats = re.compile(r'%(?:\d+\$)?[-+ #0]*(?:\d+|\*)?(?:\.(?:\d+|\*))?[hlLjzt]*[diuoxXfFeEgGaAcspn%]')
stable_ids=[]
for en, ru in pairs:
    en,ru=decode(en),decode(ru)
    assert not re.search('[А-Яа-яЁё]',en), en
    assert formats.findall(en)==formats.findall(ru),(en,ru)
    if '###' in en:
        assert en.split('###')[1]==ru.split('###')[1]
        stable_ids.append((en,ru))
print(f'Checked {len(pairs)} bilingual strings and their printf formats; {len(stable_ids)} stable widget IDs.')

text_and_open=source[source.index('const char* Text('):source.index('ImGuiKey KeyFromSdl')]
menu=source[source.index('// Marks the settings dirty'):source.index('// The game\'s text dialog', source.index('// Marks the settings dirty'))]
fps=source[source.index('void FpsCounter()'):source.index('} // namespace\n\nvoid SavePendingSettings')]
present=source[source.index('void RecordPresent('):source.index('void Render(vk::CommandBuffer',source.index('void RecordPresent('))]
focus=source[source.index('    case SDL_EVENT_WINDOW_FOCUS_GAINED:'):source.index('    case SDL_EVENT_KEY_DOWN:',source.index('bool HandleEvent('))]
# Instrument only the scratch copy to record the real controls' positions and IDs.
menu=menu.replace('ImGui::BeginCombo(', 'TrackedCombo(').replace('ImGui::Selectable(', 'TrackedSelectable(').replace('ImGui::Checkbox(', 'TrackedCheckbox(').replace('ImGui::SliderFloat(', 'TrackedSlider(').replace('ImGui::SliderInt(', 'TrackedSliderInt(')
menu=menu.replace('ImGui::BeginTabItem(', 'TrackedTab(').replace('ImGui::Button(', 'TrackedButton(')
menu=menu.replace('ImGui::DragInt(', 'TrackedDragInt(').replace('ImGui::InputInt(', 'TrackedInputInt(')
prefix=r'''#include <algorithm>
#include <atomic>
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <filesystem>
#include <string>
#include <vector>
#include <map>
#include <mutex>
#include "bbport_settings.h"
#include "bbport_frametime.h"
#include "bbcheats.h"
#include "imgui.h"
#include "imgui_internal.h"

std::atomic<bool> menu_open{true};
bool dirty=false;
float base_scale=1.0f, frame_ms_avg=16.666f;
BbFrameMetrics::RealFrameHistory real_frame_history;
std::mutex imgui_mutex;
bool initialized=true,l3_down=false,r3_down=false;
constexpr int SDL_EVENT_WINDOW_FOCUS_GAINED=1,SDL_EVENT_WINDOW_FOCUS_LOST=2;
int restart_calls=0;
extern "C" void runtime_restart() { ++restart_calls; }
ImRect language_rect, russian_rect, english_rect, window_rect, borderless_rect, windowed_rect, vsync_rect;
ImRect dlss_rect, preset_m_rect, preset_k_rect, osd_rect, osd_preset_rect, resolution_rect, background_rect, pause_rect, run_rect;
std::map<std::string,ImRect> controls, tabs, buttons;
std::string selected_tab;
std::map<std::string,std::string> setting_categories;
void TrackSetting(const char* key) {
    assert(!selected_tab.empty());
    const auto [it, inserted]=setting_categories.emplace(key,selected_tab);
    assert(inserted || it->second==selected_tab);
}
std::map<std::string,ImGuiWindow*> control_windows;
std::map<std::string,ImGuiID> control_ids;
std::map<std::string,ImRect> selectables;
ImGuiID language_id=0;
bool saw_russian=false, saw_english=false;
bool TrackedTab(const char* label) {
    bool result=ImGui::BeginTabItem(label);
    if (const char* key=std::strstr(label,"###")) {
        tabs[key+3]=GImGui->LastItemData.Rect;
        if (result) selected_tab=key+3;
    }
    return result;
}
bool TrackedButton(const char* label) {
    bool result=ImGui::Button(label);
    if (const char* key=std::strstr(label,"###")) buttons[key+3]=GImGui->LastItemData.Rect;
    return result;
}
bool TrackedCombo(const char* label,const char* preview) {
    bool result=ImGui::BeginCombo(label,preview);
    if (const char* key=std::strstr(label,"###")) {
        controls[key+3]=GImGui->LastItemData.Rect; control_windows[key+3]=GImGui->CurrentWindow; control_ids[key+3]=GImGui->LastItemData.ID; TrackSetting(key+3);
    }
    if (std::strstr(label,"###menu_language")) {
        language_rect=GImGui->LastItemData.Rect;
        language_id=GImGui->LastItemData.ID;
    }
    if (std::strstr(label,"###window_mode")) window_rect=GImGui->LastItemData.Rect;
    if (std::strstr(label,"###dlss_preset")) dlss_rect=GImGui->LastItemData.Rect;
    if (std::strstr(label,"###background_mode")) background_rect=GImGui->LastItemData.Rect;
    return result;
}
bool TrackedSelectable(const char* label,bool selected) {
    bool result=ImGui::Selectable(label,selected);
    selectables[label]=GImGui->LastItemData.Rect;
    if (std::strcmp(label,"Русский")==0) { russian_rect=GImGui->LastItemData.Rect; saw_russian=true; }
    if (std::strcmp(label,"English")==0) { english_rect=GImGui->LastItemData.Rect; saw_english=true; }
    if (std::strstr(label,"###window_borderless")) borderless_rect=GImGui->LastItemData.Rect;
    if (std::strstr(label,"###window_windowed")) windowed_rect=GImGui->LastItemData.Rect;
    if (std::strstr(label,"###background_pause")) pause_rect=GImGui->LastItemData.Rect;
    if (std::strstr(label,"###background_run")) run_rect=GImGui->LastItemData.Rect;
    if (std::strcmp(label,BbSettings::DlssPresetName(13))==0) preset_m_rect=GImGui->LastItemData.Rect;
    if (std::strcmp(label,BbSettings::DlssPresetName(11))==0) preset_k_rect=GImGui->LastItemData.Rect;
    return result;
}
bool TrackedCheckbox(const char* label,bool* value) {
    const bool result=ImGui::Checkbox(label,value);
    const char* key=std::strstr(label,"###");
    if (key) { controls[key+3]=GImGui->LastItemData.Rect; control_windows[key+3]=GImGui->CurrentWindow; control_ids[key+3]=GImGui->LastItemData.ID; TrackSetting(key+3); }
    if (std::strstr(label,"###borderless_vsync")) vsync_rect=GImGui->LastItemData.Rect;
    if (std::strstr(label,"###show_fps")) osd_rect=GImGui->LastItemData.Rect;
    if (std::strstr(label,"###show_dlss_preset")) osd_preset_rect=GImGui->LastItemData.Rect;
    if (std::strstr(label,"###show_resolution")) resolution_rect=GImGui->LastItemData.Rect;
    return result;
}
bool TrackedSlider(const char* label,float* value,float lo,float hi,const char* format) {
    bool result=ImGui::SliderFloat(label,value,lo,hi,format);
    const char* key=std::strstr(label,"###");
    if (key) { controls[key+3]=GImGui->LastItemData.Rect; control_windows[key+3]=GImGui->CurrentWindow; control_ids[key+3]=GImGui->LastItemData.ID; TrackSetting(key+3); }
    return result;
}
bool TrackedSliderInt(const char* label,int* value,int lo,int hi,const char* format) {
    bool result=ImGui::SliderInt(label,value,lo,hi,format);
    const char* key=std::strstr(label,"###");
    if (key) {controls[key+3]=GImGui->LastItemData.Rect; control_windows[key+3]=GImGui->CurrentWindow;control_ids[key+3]=GImGui->LastItemData.ID; TrackSetting(key+3);}
    return result;
}
bool TrackedDragInt(const char* label,int* value,float speed,int lo,int hi,const char* format,ImGuiSliderFlags flags) {
    const bool result=ImGui::DragInt(label,value,speed,lo,hi,format,flags);
    TrackSetting(std::strstr(label,"###")+3);
    controls[std::strstr(label,"###")+3]=GImGui->LastItemData.Rect; control_windows[std::strstr(label,"###")+3]=GImGui->CurrentWindow;
    return result;
}
bool TrackedInputInt(const char* label,int* value,int step,int fast,ImGuiInputTextFlags flags) {
    const bool result=ImGui::InputInt(label,value,step,fast,flags);
    TrackSetting(std::strstr(label,"###")+3);
    controls[std::strstr(label,"###")+3]=GImGui->LastItemData.Rect; control_windows[std::strstr(label,"###")+3]=GImGui->CurrentWindow;
    return result;
}
'''
id_checks='\n'.join('    assert(ImHashStr('+a+') == ImHashStr('+b+'));' for a,b in pairs if '###' in decode(a))
main=r'''
void Frame(bool log=false) {
    controls.clear(); control_windows.clear(); buttons.clear(); tabs.clear();
    ImGui::NewFrame();
    if (log) ImGui::LogToBuffer();
    Menu();
    FpsCounter();
    if (log) {
        const std::string content=GImGui->LogBuffer.c_str();
        assert(content.find("###")==std::string::npos);
        const bool ru=BbSettings::Get().menu_language==BbSettings::MenuRussian;
        assert(content.find(ru ? "Картинка" : "Image")!=std::string::npos);
        assert(content.find(ru ? "Эффекты" : "Effects")!=std::string::npos);
        ImGui::LogFinish();
    }
    ImGui::Render();
    assert(ImGui::GetDrawData()->Valid);
    if (GImGui->FrameCount>1) assert(ImGui::GetDrawData()->TotalVtxCount>0);
}
void Click(ImVec2 pos) {
    auto& io=ImGui::GetIO();
    io.AddMousePosEvent(pos.x,pos.y);
    Frame();
    io.AddMouseButtonEvent(0,true);
    Frame();
    io.AddMouseButtonEvent(0,false);
    Frame();
}
std::string OsdFrame() {
    ImGui::NewFrame();
    ImGui::LogToBuffer();
    FpsCounter();
    const std::string result=GImGui->LogBuffer.c_str();
    ImGui::LogFinish();
    ImGui::Render();
    return result;
}

void Reveal(const char* key) {
    Frame(); Frame();
    if (!controls.contains(key)) {
        for (const char* tab : {"image","frames","window","overlay","cheats","effects","advanced"}) {
            assert(tabs.contains(tab)); Click(tabs.at(tab).GetCenter()); Frame(); Frame();
            if (controls.contains(key)) break;
        }
    }
    assert(controls.contains(key));
    auto* window=control_windows.at(key);
    const auto rect=controls.at(key);
    ImGui::SetScrollFromPosY(window,rect.GetCenter().y-window->Pos.y,0.5f);
    Frame(); Frame();
}
void TestBoolean(const char* key,std::atomic<bool>& value) {
    for (bool desired : {true,false}) {
        value=!desired;
        Reveal(key);
        Click(controls.at(key).GetCenter());
        assert(value==desired && dirty);
        SetOpen(false); value=!desired; BbSettings::Load();
        assert(value==desired);
        SetOpen(true);
    }
}
void TestSlider(const char* key,std::atomic<float>& value,float lo,float hi) {
    value=lo;
    Reveal(key);
    auto rect=controls.at(key);
    // The slider itself is its first item-width pixels, before the label.
    const float width=control_windows.at(key)->DC.ItemWidth;
    Click({rect.Min.x+width*0.80f,rect.GetCenter().y});
    assert(value>lo+(hi-lo)*0.60f && value<hi);
    const float selected=value;
    SetOpen(false); value=lo; BbSettings::Load();
    assert(std::abs(value-selected)<0.015f);
    SetOpen(true);
}
void TestMultiplier(const char* key,std::atomic<int>& value,bool movement=false) {
    const int count=movement ? 6 : 5;
    const char* const* labels=movement ? BbSettings::MovementMultipliers : BbSettings::CheatMultipliers;
    for (int i=1;i<=count;++i) {
        const int selected=i%count;
        Reveal(key);
        selectables.clear(); Click(controls.at(key).GetCenter()); Frame(); Frame();
        const char* label=selected ? labels[selected] : Text("Off","Выключено");
        assert(selectables.contains(label)); Click(selectables.at(label).GetCenter());
        assert(value==selected && dirty);
        SetOpen(false); value=(selected+1)%count; BbSettings::Load();
        assert(value==selected); SetOpen(true);
    }
}
void TestFrameGeneration() {
    auto& s=BbSettings::Get();
    for (int u=0;u<BbSettings::UpscalerCount;++u) {
        s.upscaler=u; s.frame_generation=BbSettings::FrameGenerationOff;
        Reveal("frame_generation");
        selectables.clear(); Click(controls.at("frame_generation").GetCenter()); Frame(); Frame();
        assert(selectables.contains("FSR Frame Generation (2x)"));
        Click(selectables.at("FSR Frame Generation (2x)").GetCenter());
        if (u==BbSettings::UpscalerOff) {
            assert(s.frame_generation==BbSettings::FrameGenerationOff);
            auto& io=ImGui::GetIO();
            io.AddKeyEvent(ImGuiKey_Escape,true); Frame(); io.AddKeyEvent(ImGuiKey_Escape,false); Frame();
        } else {
            assert(s.frame_generation==BbSettings::FrameGenerationFsr);
            SetOpen(false); s.frame_generation=BbSettings::FrameGenerationOff; BbSettings::Load();
            assert(s.frame_generation==BbSettings::FrameGenerationFsr); SetOpen(true);
            Reveal("frame_generation");
            selectables.clear(); Click(controls.at("frame_generation").GetCenter()); Frame(); Frame();
            const char* off=Text("Off###fg_off","Выключено###fg_off");
            assert(selectables.contains(off)); Click(selectables.at(off).GetCenter());
            assert(s.frame_generation==BbSettings::FrameGenerationOff);
        }
    }
}
void TestXessQuality() {
    auto& s=BbSettings::Get();
    s.upscaler=BbSettings::UpscalerXess;s.preset=BbSettings::Balanced;s.xess_preset=0;
    s.output_res=1;
    for (int i=1;i<=BbSettings::XessPresetCount;++i) {
        const int selected=i%BbSettings::XessPresetCount;
        controls.clear();Reveal("xess_preset");
        assert(!controls.contains("preset") && !controls.contains("dlss_preset"));
        selectables.clear();Click(controls.at("xess_preset").GetCenter());Frame();Frame();
        char label[96];
        const float scale=BbSettings::XessPresetScale(selected);
        std::snprintf(label,sizeof(label),Text("%s (x%.1f, render %dx%d)###xess_preset_%d",
                                             "%s (x%.1f, рендер %dx%d)###xess_preset_%d"),
            BbSettings::XessPresetName(selected),scale,
            int(std::lround(1920/scale/2)*2),int(std::lround(1080/scale/2)*2),selected);
        assert(selectables.contains(label));Click(selectables.at(label).GetCenter());
        assert(s.xess_preset==selected && s.preset==BbSettings::Balanced);
        SetOpen(false);s.xess_preset=-1;BbSettings::Load();
        assert(s.xess_preset==selected && s.preset==BbSettings::Balanced);SetOpen(true);
    }
    s.upscaler=BbSettings::UpscalerDlss;
    controls.clear();Reveal("preset");
    assert(!controls.contains("xess_preset") && controls.contains("dlss_preset"));
}
void TestNvidiaControls() {
    auto& s=BbSettings::Get();
    s.reflex_supported=true;s.nvidia_fg_supported=true;s.nvidia_max_generated=5;
    for (int u : {BbSettings::UpscalerOff,BbSettings::UpscalerTaa,BbSettings::UpscalerFsr3,BbSettings::UpscalerDlss}) {
        s.upscaler=u;s.frame_generation=BbSettings::FrameGenerationOff;
        for (int i=1;i<=3;++i) {
            const int selected=i%3;
            Reveal("reflex");selectables.clear();Click(controls.at("reflex").GetCenter());Frame();Frame();
            const char* label=selected==2 ? "On + Boost" : selected==1 ? Text("On","Включено") : Text("Off","Выключено");
            assert(selectables.contains(label));Click(selectables.at(label).GetCenter());
            assert(s.reflex==selected && s.frame_generation==BbSettings::FrameGenerationOff);
            SetOpen(false);s.reflex=(selected+1)%3;BbSettings::Load();
            assert(s.reflex==selected);SetOpen(true);
        }
    }
    s.upscaler=BbSettings::UpscalerTaa;
    Reveal("frame_generation");selectables.clear();Click(controls.at("frame_generation").GetCenter());Frame();Frame();
    Click(selectables.at("NVIDIA DLSS Frame Generation / MFG").GetCenter());
    assert(s.frame_generation==BbSettings::FrameGenerationNvidia);
    for (int i=1;i<=5;++i) {
        Reveal("nvidia_generated_frames");selectables.clear();Click(controls.at("nvidia_generated_frames").GetCenter());Frame();Frame();
        Click(selectables.at(std::to_string(i+1)+"x").GetCenter());
        assert(s.nvidia_generated_frames==i);
        SetOpen(false);s.nvidia_generated_frames=1;BbSettings::Load();
        assert(s.nvidia_generated_frames==i);SetOpen(true);
    }
    TestBoolean("limit_generated_fps",s.limit_generated_fps);
    TestBoolean("show_frame_generation",s.show_frame_generation);
    TestBoolean("show_latency",s.show_latency);
    s.limit_generated_fps=true;s.generated_fps_limit=130;
    Reveal("generated_fps_limit");auto rect=controls.at("generated_fps_limit");
    // Clicking anywhere in the drag field must keep the value, rather than jump.
    Click({rect.Min.x+rect.GetWidth()*0.80f,rect.GetCenter().y});
    assert(s.generated_fps_limit==130);
    Reveal("generated_fps_entry");rect=controls.at("generated_fps_entry");
    const auto drag_rect=controls.at("generated_fps_limit");
    assert(rect.Min.x>=drag_rect.Max.x && rect.Max.x<=control_windows.at("generated_fps_entry")->WorkRect.Max.x+1);
    Click({rect.Min.x+15,rect.GetCenter().y});
    auto& io=ImGui::GetIO();
    io.AddKeyEvent(ImGuiMod_Ctrl,true);io.AddKeyEvent(ImGuiKey_A,true);Frame();
    io.AddKeyEvent(ImGuiKey_A,false);io.AddKeyEvent(ImGuiMod_Ctrl,false);Frame();
    io.AddInputCharactersUTF8("137");Frame();Frame();
    io.AddKeyEvent(ImGuiKey_Enter,true);Frame();io.AddKeyEvent(ImGuiKey_Enter,false);Frame();
    const int selected=s.generated_fps_limit;
    assert(selected==137);
    SetOpen(false);s.generated_fps_limit=30;BbSettings::Load();assert(s.generated_fps_limit==selected);SetOpen(true);
    s.limit_generated_fps=false;s.frame_generation=BbSettings::FrameGenerationOff;s.reflex=0;
}
void TestRealFpsAndAntiLag() {
    auto& s=BbSettings::Get();s.variable_frame_time=true;
    s.real_fps_limit=-1;
    for (int mode : {1,2,0}) {
        Reveal("real_fps_mode");selectables.clear();Click(controls.at("real_fps_mode").GetCenter());Frame();Frame();
        auto it=std::find_if(selectables.begin(),selectables.end(),[&](const auto& item) {
            return item.first.ends_with("###real_fps_mode_"+std::to_string(mode));
        });
        assert(it!=selectables.end());Click(it->second.GetCenter());
        assert(s.real_fps_limit==(mode==1 ? 75 : mode==2 ? 0 : -1));
    }
    s.real_fps_limit=75;
    Reveal("real_fps_limit");const auto drag=controls.at("real_fps_limit");
    Click({drag.Min.x+drag.GetWidth()*0.8f,drag.GetCenter().y});assert(s.real_fps_limit==75);
    Reveal("real_fps_entry");auto rect=controls.at("real_fps_entry");
    assert(rect.Min.x>=controls.at("real_fps_limit").Max.x);
    Click({rect.Min.x+15,rect.GetCenter().y});
    auto& io=ImGui::GetIO();io.AddKeyEvent(ImGuiMod_Ctrl,true);io.AddKeyEvent(ImGuiKey_A,true);Frame();
    io.AddKeyEvent(ImGuiKey_A,false);io.AddKeyEvent(ImGuiMod_Ctrl,false);Frame();
    io.AddInputCharactersUTF8("93");Frame();Frame();
    io.AddKeyEvent(ImGuiKey_Enter,true);Frame();io.AddKeyEvent(ImGuiKey_Enter,false);Frame();
    assert(s.real_fps_limit==93);
    SetOpen(false);s.real_fps_limit=-1;BbSettings::Load();assert(s.real_fps_limit==93);SetOpen(true);
    s.variable_frame_time=false;s.real_fps_limit=75;Reveal("real_fps_mode");selectables.clear();
    Click(controls.at("real_fps_mode").GetCenter());Frame();assert(selectables.empty() && s.real_fps_limit==75);
    s.variable_frame_time=true;
    s.amd_antilag_supported=false;s.amd_antilag=false;Reveal("amd_antilag");
    Click(controls.at("amd_antilag").GetCenter());assert(!s.amd_antilag);
    s.amd_antilag_supported=true;TestBoolean("amd_antilag",s.amd_antilag);
    s.real_fps_limit=-1;
}
void TestNavigation(ImGuiKey key) {
    auto& io=ImGui::GetIO();
    auto& s=BbSettings::Get();
    s.jitter=false;
    io.AddMousePosEvent(-100,-100);
    Reveal("jitter");
    auto* window=control_windows.at("jitter");
    auto rect=controls.at("jitter"); rect.Translate(ImVec2(-window->Pos.x,-window->Pos.y));
    ImGui::FocusWindow(window);
    ImGui::SetNavID(control_ids.at("jitter"),ImGuiNavLayer_Main,window->NavRootFocusScopeId,rect);
    ImGui::SetNavCursorVisibleAfterMove();
    Frame();
    io.AddKeyEvent(key,true); Frame();
    io.AddKeyEvent(key,false); Frame();
    assert(s.jitter);
}

void ChooseTab(const char* key) {
    Frame(); Frame();
    assert(tabs.contains(key));
    if (selected_tab!=key) Click(tabs.at(key).GetCenter());
    Frame(); Frame();
    assert(selected_tab==key);
}
void CaptureMenu(const std::filesystem::path& directory,const char* name) {
    auto* data=ImGui::GetDrawData();
    assert(data && data->Valid);
    unsigned char* atlas; int width,height;
    ImGui::GetIO().Fonts->GetTexDataAsRGBA32(&atlas,&width,&height);
    {
        std::ofstream raw(directory/(std::string(name)+".atlas"),std::ios::binary);
        raw.write(reinterpret_cast<const char*>(atlas),width*height*4);
    }
    auto* window=ImGui::FindWindowByName(std::strncmp(name,"frametime",9)==0 ? "##fps" : "###bbport_settings");
    std::ofstream out(directory/(std::string(name)+".json"));
    out<<"{\"display\":["<<data->DisplaySize.x<<","<<data->DisplaySize.y<<"],\"atlas\":["<<width<<","<<height
       <<"],\"window\":["<<window->Pos.x<<","<<window->Pos.y<<","<<window->Size.x<<","<<window->Size.y<<"],\"lists\":[";
    bool first=true;
    for (const ImDrawList* list : data->CmdLists) {
        if (!first) out<<","; first=false;
        out<<"{\"vertices\":[";
        for (int i=0;i<list->VtxBuffer.Size;++i) {
            const auto& v=list->VtxBuffer[i]; if(i)out<<",";
            out<<"["<<v.pos.x<<","<<v.pos.y<<","<<v.uv.x<<","<<v.uv.y<<","<<v.col<<"]";
        }
        out<<"],\"indices\":[";
        for (int i=0;i<list->IdxBuffer.Size;++i) {if(i)out<<",";out<<list->IdxBuffer[i];}
        out<<"],\"commands\":[";
        for (int i=0;i<list->CmdBuffer.Size;++i) {
            const auto& cmd=list->CmdBuffer[i]; if(i)out<<",";
            assert(!cmd.UserCallback && cmd.GetTexID()==1);
            out<<"{\"clip\":["<<cmd.ClipRect.x<<","<<cmd.ClipRect.y<<","<<cmd.ClipRect.z<<","<<cmd.ClipRect.w
               <<"],\"offset\":"<<cmd.IdxOffset<<",\"count\":"<<cmd.ElemCount<<",\"base\":"<<cmd.VtxOffset<<"}";
        }
        out<<"]}";
    }
    out<<"]}\n";
}
void CheckMenuLayout() {
    auto& s=BbSettings::Get();auto& io=ImGui::GetIO();int cases=0;
    s.fsr4_problem=s.dlss_problem=s.xess_problem=s.frame_generation_problem=nullptr;
    s.fsr4_supported=s.fsr411_supported=s.dlss_supported=s.xess_supported=true;
    s.nvidia_fg_supported=s.reflex_supported=s.amd_antilag_supported=true;
    s.nvidia_max_generated=5;s.limit_generated_fps=true;s.real_fps_limit=75;
    for (int language : {BbSettings::MenuEnglish,BbSettings::MenuRussian})
    for (float scale : {1.0f,1.25f,1.5f,1.75f,2.0f})
    for (ImVec2 size : {ImVec2(960,540),ImVec2(1280,720),ImVec2(1920,1080),ImVec2(3840,2160)})
    for (int upscaler=0;upscaler<BbSettings::UpscalerCount;++upscaler) {
        base_scale=scale;ImGui::GetStyle().FontScaleMain=scale;io.DisplaySize=size;
        s.menu_language=language;s.upscaler=upscaler;
        s.frame_generation=upscaler%3;
        for (const char* tab : {"image","frames","window","overlay","cheats","effects","advanced"}) {
            ChooseTab(tab);
            auto* window=ImGui::FindWindowByName("###bbport_settings");
            assert(window && window->Active && window->ScrollMax.y<=1);
            assert(window->Pos.x>=0 && window->Pos.y>=0);
            assert(window->Pos.x+window->Size.x<=size.x+1 && window->Pos.y+window->Size.y<=size.y+1);
            assert(tabs.size()==7);
            for (const auto& [key,rect] : tabs) {
                assert(rect.Min.x>=window->WorkRect.Min.x-1 && rect.Max.x<=window->WorkRect.Max.x+1);
            }
            assert(buttons.contains("close"));
            for (const auto& [key,rect] : buttons) {
                assert(rect.Min.y>=window->InnerRect.Min.y && rect.Max.y<=window->InnerRect.Max.y+1);
            }
            for (const auto& [key,rect] : controls) {
                auto* child=control_windows.at(key);
                if (rect.Max.x>child->WorkRect.Max.x+1) {
                    std::fprintf(stderr,"Clipped %s on %s lang %d scale %.2f size %.0fx%.0f: %.1f > %.1f\n",
                        key.c_str(),tab,language,scale,size.x,size.y,rect.Max.x,child->WorkRect.Max.x);
                    assert(false);
                }
            }
            ++cases;
        }
    }
    std::printf("PASS: %d tab layouts, both languages, 100/125/150/175/200%%, 540p/720p/1080p/2160p; "
                "seven visible tabs, contained controls, no parent scrolling and pinned footer.\n",cases);
    base_scale=1;ImGui::GetStyle().FontScaleMain=1;io.DisplaySize={1280,720};
    s.menu_language=BbSettings::MenuEnglish;s.upscaler=BbSettings::UpscalerDlss;
    s.frame_generation=BbSettings::FrameGenerationNvidia;s.nvidia_generated_frames=1;
    s.frame_generation_active=0;s.nvidia_real_fps=s.nvidia_output_fps=-1;
    s.fsr4_problem=s.dlss_problem=s.xess_problem=s.frame_generation_problem=nullptr;
    s.dlss_preset=s.dlss_active_preset=12;s.preset=BbSettings::Performance;s.output_res=3;
    s.active_render_width=1920;s.active_render_height=1080;
    s.active_output_width=3840;s.active_output_height=2160;
    s.real_fps_limit=75;s.generated_fps_limit=130;s.live_resolution=1;
    s.sharpness=0.25f;s.reactive_scale=1;s.reactive_threshold=0.2f;s.reactive_max=0.9f;
    s.startup_object_motion=s.object_motion;s.startup_model_lod=s.model_lod;s.startup_live_resolution=s.live_resolution;
    for(int e=0;e<BbSettings::EffectCount;++e)s.startup_effects[e]=s.effects[e].load();
    if (const char* path=std::getenv("BB_MENU_CAPTURE_DIR")) {
        std::filesystem::path directory(path);std::filesystem::create_directories(directory);
        for (const char* tab : {"image","frames","window","overlay","cheats","effects","advanced"}) {
            ChooseTab(tab);
            auto* child=control_windows.begin()->second;
            ImGui::SetScrollY(child,0);Frame();Frame();
            CaptureMenu(directory,tab);
        }
    }
    ChooseTab("effects");
    auto* parent=ImGui::FindWindowByName("###bbport_settings");
    // Resizing must preserve the selected tab and keep the close button on screen.
    ImGui::SetWindowSize(parent,{580,400});Frame();Frame();
    assert(selected_tab=="effects" && parent->Size.x==580 && parent->Size.y==400 && parent->ScrollMax.y<=1);
    assert(buttons.at("close").Max.y<=parent->InnerRect.Max.y+1);
    // The footer remains reachable after scrolling the active child all the way down.
    auto* child=control_windows.begin()->second;
    ImGui::SetScrollY(child,child->ScrollMax.y);Frame();Frame();
    const ImRect close=buttons.at("close");Click(close.GetCenter());
    assert(!menu_open && !dirty);
    SetOpen(true);
}

int main(int argc,char** argv) {
    assert(argc==2);
    setenv("BB_CONFIG",argv[1],1);
    unsetenv("BB_RENDER_RES");
    const auto menu_path=std::filesystem::path{argv[1]}.replace_extension(".menu.ini");
    std::filesystem::remove(menu_path);
    auto& s=BbSettings::Get();
    assert(s.menu_language==BbSettings::MenuEnglish);
    s.cheat_supported=BB_CHEAT_ALL;
    // Existing files, valid codes, and unknown values must load deterministically.
    for (const char* config : {"upscaler=dlss\npreset=2\noutput_res=2560x1440\n",
                              "menu_language=en\n", "menu_language=ru\n",
                              "menu_language=it\n", "menu_language=\n"}) {
        { std::ofstream file(menu_path); file<<config; }
        s.menu_language=BbSettings::MenuRussian;
        BbSettings::Load();
        assert(s.menu_language==(std::strstr(config,"menu_language=ru") ? BbSettings::MenuRussian : BbSettings::MenuEnglish));
    }
    for (int language : {BbSettings::MenuEnglish,BbSettings::MenuRussian}) {
        s.menu_language=language;
        s.upscaler=BbSettings::UpscalerDlss;
        s.preset=BbSettings::Balanced;
        s.effects[0]=false;
        BbSettings::Save();
        s.menu_language=BbSettings::MenuEnglish;
        s.upscaler=BbSettings::UpscalerOff;
        BbSettings::Load();
        assert(s.menu_language==language);
        assert(s.upscaler==BbSettings::UpscalerDlss && s.preset==BbSettings::Balanced && !s.effects[0]);
    }
    // Simulate the original launcher rewriting its cached main configuration.
    { std::ofstream file(argv[1]); file << "upscaler=fsr3\npreset=0\n"; }
    s.menu_language=BbSettings::MenuEnglish;
    BbSettings::Load();
    assert(s.menu_language==BbSettings::MenuRussian);
    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    auto& io=ImGui::GetIO();
    WorkshopTheme(ImGui::GetStyle());
    io.IniFilename=nullptr;
    io.ConfigFlags|=ImGuiConfigFlags_NavEnableKeyboard|ImGuiConfigFlags_NavEnableGamepad;
    io.BackendFlags|=ImGuiBackendFlags_HasGamepad;
    io.DisplaySize={1920,1080};
    io.DeltaTime=1.0f/60;
    io.Fonts->AddFontFromFileTTF("gpu/third_party/fonts/DejaVuSans.ttf",18.0f,nullptr,io.Fonts->GetGlyphRangesCyrillic());
    unsigned char* pixels; int width,height;
    io.Fonts->GetTexDataAsRGBA32(&pixels,&width,&height);
    io.Fonts->SetTexID(1);
    s.menu_language=BbSettings::MenuEnglish;
    s.upscaler=BbSettings::UpscalerFsr3;
    Frame(); Frame(true);
    ImGuiWindow* window=ImGui::FindWindowByName("###bbport_settings");
    assert(window);
    Reveal("menu_language");
    const ImGuiID stable_language_id=language_id;
    // Drive the actual dropdown using ImGui input events in both directions.
    Reveal("menu_language"); Click(language_rect.GetCenter());
    Frame(); Frame();
    assert(saw_russian && saw_english);
    Frame(); Frame();
    Click(russian_rect.GetCenter());
    Frame(true);
    assert(s.menu_language==BbSettings::MenuRussian && dirty);
    assert(ImGui::FindWindowByName("###bbport_settings")==window);
    assert(language_id==stable_language_id);
    SetOpen(false);
    assert(!dirty && !menu_open);
    s.menu_language=BbSettings::MenuEnglish;
    BbSettings::Load();
    assert(s.menu_language==BbSettings::MenuRussian);
    SetOpen(true);
    Frame();
    Reveal("menu_language"); Click(language_rect.GetCenter());
    Frame(); Frame();
    Click(english_rect.GetCenter());
    Frame(true);
    assert(s.menu_language==BbSettings::MenuEnglish);
    assert(language_id==stable_language_id);
    // Select borderless and V-sync through the real controls without a restart.
    Reveal("window_mode"); Click(window_rect.GetCenter()); Frame(); Frame();
    Click(borderless_rect.GetCenter()); Frame(true);
    assert(s.window_mode==BbSettings::Borderless);
    Reveal("borderless_vsync"); Click(vsync_rect.GetCenter()); Frame(true);
    assert(s.borderless_vsync);
    SetOpen(false); BbSettings::Load();
    assert(s.window_mode==BbSettings::Borderless && s.borderless_vsync);
    SetOpen(true); Frame();
    Reveal("window_mode"); Click(window_rect.GetCenter()); Frame(); Frame();
    Click(windowed_rect.GetCenter()); Frame(true);
    assert(s.window_mode==BbSettings::Windowed);
    // Select the actual DLSS preset controls without changing quality or resolution.
    s.upscaler=BbSettings::UpscalerDlss;
    s.dlss_supported=true;
    s.dlss_preset=0;
    s.dlss_active_preset=-1;
    s.show_fps=true;
    s.show_dlss_preset=false;
    const int quality=s.preset, output=s.output_res;
    Frame(); Frame();
    Reveal("dlss_preset"); Click(dlss_rect.GetCenter()); Frame(); Frame();
    Click(preset_m_rect.GetCenter()); Frame(true);
    assert(s.dlss_preset==13 && s.preset==quality && s.output_res==output);
    auto osd=OsdFrame();
    assert(osd.find("DLSS (")==std::string::npos);
    OsdFrame();
    const float original_height=ImGui::FindWindowByName("##fps")->Size.y;
    const auto original_rows=std::count(osd.begin(),osd.end(),'\n');
    Frame(); Frame();
    Reveal("show_dlss_preset"); Click(osd_preset_rect.GetCenter()); Frame(true);
    assert(s.show_dlss_preset && s.show_fps && s.dlss_preset==13);
    osd=OsdFrame(); OsdFrame();
    assert(osd.find("DLSS (->M)")!=std::string::npos);
    assert(std::count(osd.begin(),osd.end(),'\n')==original_rows);
    assert(ImGui::FindWindowByName("##fps")->Size.y==original_height);
    s.dlss_active_preset=11;
    osd=OsdFrame();
    assert(osd.find("DLSS (K>M)")!=std::string::npos);
    assert(std::count(osd.begin(),osd.end(),'\n')==original_rows);
    s.dlss_active_preset=13;
    osd=OsdFrame();
    assert(osd.find("DLSS (M)")!=std::string::npos);
    assert(osd.find("Transformer")==std::string::npos && osd.find("legacy")==std::string::npos);
    for (int value : BbSettings::DlssPresetValues) {
        s.dlss_preset=s.dlss_active_preset=value;
        osd=OsdFrame(); OsdFrame();
        assert(osd.find(std::string("DLSS (")+BbSettings::DlssPresetShortName(value)+")")!=std::string::npos);
        assert(std::count(osd.begin(),osd.end(),'\n')==original_rows);
        assert(ImGui::FindWindowByName("##fps")->Size.y==original_height);
    }
    s.dlss_preset=s.dlss_active_preset=13;
    Frame(); Frame();
    Reveal("show_dlss_preset"); Click(osd_preset_rect.GetCenter()); Frame(true);
    assert(!s.show_dlss_preset && s.dlss_preset==13 && s.show_fps);
    assert(OsdFrame().find("DLSS (")==std::string::npos);
    Frame(); Frame();
    Reveal("show_dlss_preset"); Click(osd_preset_rect.GetCenter()); Frame(true);
    assert(s.show_dlss_preset);
    Frame(); Frame();
    Reveal("show_fps"); Click(osd_rect.GetCenter()); Frame(true);
    assert(!s.show_fps);
    assert(OsdFrame().empty());
    SetOpen(false); BbSettings::Load();
    assert(!s.show_fps && s.dlss_preset==13 && s.show_dlss_preset);
    SetOpen(true); Frame(); Frame();
    assert(ImGui::FindWindowByName("###bbport_settings")->Active);
    Reveal("show_fps"); Click(osd_rect.GetCenter()); Frame(true);
    assert(s.show_fps && !OsdFrame().empty());
    Frame(); Frame();
    Reveal("dlss_preset"); Click(dlss_rect.GetCenter()); Frame(); Frame();
    Click(preset_k_rect.GetCenter()); Frame(true);
    assert(s.dlss_preset==11 && s.preset==quality && s.output_res==output);
    SetOpen(false); BbSettings::Load();
    assert(s.show_fps && s.dlss_preset==11);
    SetOpen(true);
    // Real ImGui controls save the supervisor's policy immediately.
    Frame(); Frame();
    Reveal("background_mode"); Click(background_rect.GetCenter()); Frame(); Frame();
    Click(pause_rect.GetCenter()); Frame();
    assert(s.background_mode==BbSettings::BackgroundPause);
    s.background_mode=BbSettings::BackgroundRun;
    BbSettings::Load();
    assert(s.background_mode==BbSettings::BackgroundPause);
    Reveal("background_mode"); Click(background_rect.GetCenter()); Frame(); Frame();
    Click(run_rect.GetCenter()); Frame();
    assert(s.background_mode==BbSettings::BackgroundRun);
    Frame(); Frame();
    Reveal("show_resolution"); Click(resolution_rect.GetCenter()); Frame();
    assert(s.show_resolution);
    SetOpen(false); BbSettings::Load();
    assert(s.show_resolution);
    // The displayed dimensions are observed values, not the requested quality preset.
    for (float scale : {1.0f,1.5f,2.0f}) {
        base_scale=scale;
        for (ImVec2 size : {ImVec2(1280,720),ImVec2(1920,1080),ImVec2(3840,2160)}) {
            io.DisplaySize=size;
            for (int u=0;u<BbSettings::UpscalerCount;++u) {
                s.upscaler=u;
                for (bool show_preset : {false,true}) {
                    s.show_dlss_preset=show_preset;
                    s.active_render_width=854; s.active_render_height=480;
                    s.active_output_width=3840; s.active_output_height=2160;
                    osd=OsdFrame(); OsdFrame(); OsdFrame();
                    assert(osd.find("854x480>3840x2160")!=std::string::npos);
                    assert(std::count(osd.begin(),osd.end(),'\n')==original_rows);
                    auto* counter=ImGui::FindWindowByName("##fps");
                    assert(counter->Size.x<=420.0f*scale+1);
                    assert(counter->Size.y<=original_height+1);
                    assert(counter->FontWindowScale==1.0f);
                }
            }
        }
    }
    base_scale=1.0f;
    io.DisplaySize={1920,1080};
    s.show_resolution=false;
    s.upscaler=BbSettings::UpscalerDlss;s.frame_generation=BbSettings::FrameGenerationNvidia;
    s.frame_generation_active=2;s.nvidia_output_fps=130;s.nvidia_real_fps=65;s.pc_latency_ms=22.3f;
    s.show_frame_generation=s.show_latency=s.show_resolution=true;
    osd=OsdFrame();OsdFrame();OsdFrame();
    assert(osd.find("130fps")!=std::string::npos && osd.find("FG:NV2x")!=std::string::npos && osd.find("PC:22.3ms")!=std::string::npos);
    assert(std::count(osd.begin(),osd.end(),'\n')==original_rows);
    if(ImGui::FindWindowByName("##fps")->Size.x>521) std::fprintf(stderr,"Expanded OSD width %.1f, font %.1f, text: %s\n",ImGui::FindWindowByName("##fps")->Size.x,ImGui::GetFontSize(),osd.c_str());
    assert(ImGui::FindWindowByName("##fps")->Size.x<=521);
    s.nvidia_output_fps=150;s.frame_generation_active=1;
    osd=OsdFrame();assert(osd.find("150fps")==std::string::npos); // Requested FG is never reported as active.
    s.pc_latency_ms=-1;osd=OsdFrame();assert(osd.find("PC:N/A")!=std::string::npos);
    s.show_frame_generation=s.show_latency=s.show_resolution=false;
    s.frame_generation=BbSettings::FrameGenerationOff;s.frame_generation_active=0;
    // Toggle the production graph widget, save/reload it, and bound its OSD size.
    SetOpen(true);Frame();Frame();
    TestBoolean("show_frametime_graph",s.show_frametime_graph);
    // Execute the production present filter and focus branch, including a pause
    // too short to reach the history's long-gap reset.
    real_frame_history.Reset();
    s.window_focused=true;
    RecordPresent(true,true);RecordPresent(true,true);
    assert(real_frame_history.Size()==1);
    RecordPresent(false,true);assert(real_frame_history.Size()==1);
    FocusEvent(SDL_EVENT_WINDOW_FOCUS_LOST);assert(!real_frame_history.Size());
    FocusEvent(SDL_EVENT_WINDOW_FOCUS_GAINED);
    RecordPresent(true,true);assert(!real_frame_history.Size());
    RecordPresent(true,true);assert(real_frame_history.Size()==1);
    RecordPresent(true,false);assert(!real_frame_history.Size());
    RecordPresent(true,true);RecordPresent(true,true);
    s.window_focused=false;RecordPresent(true,true);assert(!real_frame_history.Size());
    s.window_focused=true;
    auto now=BbFrameMetrics::RealFrameHistory::Clock::time_point{};
    real_frame_history.Reset();real_frame_history.Present(now);
    for(int i=0;i<240;++i) {
        now+=std::chrono::microseconds(i==100 ? 55000 : 16667);
        real_frame_history.Present(now);
    }
    int graph_layouts=0;
    for(int language : {BbSettings::MenuEnglish,BbSettings::MenuRussian})
    for(float scale : {0.75f,1.0f,1.25f,1.5f,2.0f})
    for(bool extra : {false,true}) {
        s.menu_language=language;base_scale=scale;
        ImGui::GetStyle().FontScaleMain=scale;
        io.DisplaySize={1280*scale,720*scale};
        s.show_frame_generation=s.show_latency=s.show_resolution=extra;
        s.frame_generation=extra ? BbSettings::FrameGenerationNvidia : BbSettings::FrameGenerationOff;
        s.frame_generation_active=extra ? 2 : 0;s.nvidia_output_fps=extra ? 120.0f : -1.0f;
        s.nvidia_real_fps=extra ? 60.0f : -1.0f;
        s.show_frametime_graph=false;OsdFrame();OsdFrame();
        auto* window=ImGui::FindWindowByName("##fps");
        const float normal_height=window->Size.y;
        s.show_frametime_graph=true;
        const auto graph_text=OsdFrame();OsdFrame();
        assert(window->Size.y<=normal_height+50*scale+8);
        assert(window->Size.x<=521*scale);
        assert(window->Pos.x>=0 && window->Pos.x+window->Size.x<=io.DisplaySize.x+1);
        assert(real_frame_history.Peak()==55.0f); // the hitch survives plotting.
        if(scale==1.0f) if(const char* path=std::getenv("BB_MENU_CAPTURE_DIR")) {
            const std::string name=std::string("frametime-")+(extra ? "full-" : "")+
                (language==BbSettings::MenuEnglish ? "en" : "ru");
            CaptureMenu(std::filesystem::path(path),name.c_str());
        }
        s.show_fps=false;assert(OsdFrame().empty());s.show_fps=true;
        s.show_frametime_graph=false;OsdFrame();OsdFrame();
        assert(window->Size.y==normal_height);
        ++graph_layouts;
    }
    std::printf("PASS: %d compact frametime OSD layouts, both languages, 75-200%%; graph toggle/save, raw hitch and unchanged height when off.\n",graph_layouts);
    base_scale=1;ImGui::GetStyle().FontScaleMain=1;io.DisplaySize={1920,1080};
    s.show_frametime_graph=s.show_frame_generation=s.show_latency=s.show_resolution=false;
    s.frame_generation=BbSettings::FrameGenerationOff;s.frame_generation_active=0;
    s.nvidia_output_fps=s.nvidia_real_fps=-1;
    SetOpen(true);
    // Exercise the menu's conditional layouts across all upscalers and resolutions.
    for (int language : {BbSettings::MenuEnglish,BbSettings::MenuRussian}) {
        s.menu_language=language;
        for (int u=0;u<BbSettings::UpscalerCount;++u) {
            s.upscaler=u;
            for (bool show_preset : {false,true}) {
                s.show_dlss_preset=show_preset;
                osd=OsdFrame(); OsdFrame();
                assert(std::count(osd.begin(),osd.end(),'\n')==original_rows);
                assert(ImGui::FindWindowByName("##fps")->Size.y==original_height);
                if (u!=BbSettings::UpscalerDlss || !show_preset) {
                    assert(osd.find("DLSS (")==std::string::npos);
                }
            }
            s.fsr4_problem="Test asset warning";
            s.dlss_problem="Test DLSS warning";
            for (ImVec2 size : {ImVec2(1280,720),ImVec2(1920,1080),ImVec2(3840,2160)}) {
                io.DisplaySize=size;
                Frame(); Frame(true);
            }
        }
    }
    for (int language : {BbSettings::MenuEnglish,BbSettings::MenuRussian}) {
        s.menu_language=language;
        for (int mode : {BbSettings::WindowFromLauncher,BbSettings::Windowed,BbSettings::Borderless,BbSettings::Fullscreen}) {
            s.window_mode=mode;
            for (bool vsync : {false,true}) {
                s.borderless_vsync=vsync;
                Frame(); Frame(true);
            }
        }
    }

    base_scale=1.0f; io.DisplaySize={1920,1080};
    for (int language : {BbSettings::MenuEnglish,BbSettings::MenuRussian}) {
        s.menu_language=language; s.upscaler=BbSettings::UpscalerFsr3;
        s.fsr4_supported=true; s.fsr411_supported=true;
        TestFrameGeneration();
        TestNvidiaControls();
        TestRealFpsAndAntiLag();
        TestXessQuality();
        s.upscaler=BbSettings::UpscalerFsr3;
        TestBoolean("sharpen",s.sharpen);
        TestBoolean("jitter",s.jitter);
        TestBoolean("reactive",s.reactive);
        TestBoolean("object_motion",s.object_motion);
        TestBoolean("cheat_infinite_stamina",s.cheat_infinite_stamina);
        s.cheat_supported=BB_CHEAT_FALL;
        TestBoolean("cheat_no_fall_damage",s.cheat_no_fall_damage);
        s.cheat_supported=BB_CHEAT_ALL;
        TestBoolean("cheat_no_consume",s.cheat_no_consume);
        TestMultiplier("cheat_damage",s.cheat_damage);
        TestMultiplier("cheat_incoming",s.cheat_incoming);
        TestMultiplier("cheat_echoes",s.cheat_echoes);
        TestMultiplier("cheat_movement",s.cheat_movement,true);
        for (int e=0;e<BbSettings::EffectCount;++e) TestBoolean(BbSettings::Effects[e].key,s.effects[e]);
        s.upscaler=BbSettings::UpscalerFsr4;
        TestBoolean("fsr4_auto_exposure",s.fsr4_auto_exposure);
        TestBoolean("fsr4_invert_jitter",s.fsr4_invert_jitter);
        s.upscaler=BbSettings::UpscalerFsr3; s.sharpen=true; s.reactive=true;
        TestSlider("sharpness",s.sharpness,0,2);
        TestSlider("reactive_scale",s.reactive_scale,0,4);
        TestSlider("reactive_threshold",s.reactive_threshold,0,1);
        TestSlider("reactive_max",s.reactive_max,0,1);
        TestNavigation(ImGuiKey_Space);
        TestNavigation(ImGuiKey_GamepadFaceDown);
    }

    CheckMenuLayout();
    assert(restart_calls==0);
    if (const char* path=std::getenv("BB_MENU_CAPTURE_DIR")) {
        std::ofstream out(std::filesystem::path(path)/"settings-categories.json");
        out<<"{"; bool first=true;
        for(const auto& [key,tab] : setting_categories) {
            if(!first) out<<","; first=false;
            out<<"\""<<key<<"\":\""<<tab<<"\"";
        }
        out<<"}\n";
    }
    ImGui::DestroyContext();
    std::puts("PASS: actual ImGui real-FPS mode/drag/exact entry/save, fixed-timing restriction and supported/unsupported Anti-Lag controls; all seven XeSS quality modes independently of DLSS/FSR; conditional quality controls; basic/compact DLSS OSD; all seven active DLSS model hints and pending changes stay on one row with the original window height; shared settings survive saves; both languages/all upscalers tested; no restart from OSD choices.");
}
'''
# Check all constant widget label pairs against the actual Dear ImGui hash implementation.
main=main.replace('    IMGUI_CHECKVERSION();', id_checks+'\n    IMGUI_CHECKVERSION();')
(scratch / 'overlay_smoke.cpp').write_text(prefix+text_and_open+menu+fps+present+
    'bool FocusEvent(int type) { auto& io=ImGui::GetIO(); struct { int type; } event{type}; switch(type) {\n'+focus+'default:return false;} }\n'+main)

command=shlex.split(args.compiler)+['-std=c++20','-O1','-pthread','-Igpu','-Igpu/shim','-Igpu/third_party/imgui',str(scratch/'overlay_smoke.cpp'),'gpu/shim/bbport_settings.cpp']+[str(p.relative_to(root)) for p in (root/'gpu/third_party/imgui').glob('imgui*.cpp') if p.name!='imgui_demo.cpp']+['-o',str(scratch/'overlay-test')]
subprocess.run(command,cwd=root,check=True)
env=dict(os.environ)
if args.capture_dir:
    capture_dir=Path(args.capture_dir).resolve()
    capture_dir.mkdir(parents=True,exist_ok=True)
    env['BB_MENU_CAPTURE_DIR']=str(capture_dir)
subprocess.run([str(scratch/'overlay-test'),str(scratch/'config.ini')],cwd=root,env=env,check=True)
if args.capture_dir:
    import json
    for name in ('image','frames','window','overlay','cheats','effects','advanced',
                 'frametime-en','frametime-ru','frametime-full-en','frametime-full-ru'):
        data=json.loads((capture_dir/(name+'.json')).read_text())
        assert len((capture_dir/(name+'.atlas')).read_bytes())==data['atlas'][0]*data['atlas'][1]*4
        assert data['lists'] and data['window'][2]>0 and data['window'][3]>0
    print('PASS: all seven menu and four frametime captures contain complete draw data and font atlases.')
temporary.cleanup()
