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
# Instrument only the scratch copy to record the real controls' positions and IDs.
menu=menu.replace('ImGui::BeginCombo(', 'TrackedCombo(').replace('ImGui::Selectable(', 'TrackedSelectable(').replace('ImGui::Checkbox(', 'TrackedCheckbox(').replace('ImGui::SliderFloat(', 'TrackedSlider(')
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
#include "bbport_settings.h"
#include "imgui.h"
#include "imgui_internal.h"

std::atomic<bool> menu_open{true};
bool dirty=false;
float base_scale=1.0f, frame_ms_avg=16.666f;
int restart_calls=0;
extern "C" void runtime_restart() { ++restart_calls; }
ImRect language_rect, russian_rect, english_rect, window_rect, borderless_rect, windowed_rect, vsync_rect;
ImRect dlss_rect, preset_m_rect, preset_k_rect, osd_rect, osd_preset_rect, resolution_rect, background_rect, pause_rect, run_rect;
std::map<std::string,ImRect> controls;
std::map<std::string,ImGuiID> control_ids;
std::map<std::string,ImRect> selectables;
ImGuiID language_id=0;
bool saw_russian=false, saw_english=false;
bool TrackedCombo(const char* label,const char* preview) {
    bool result=ImGui::BeginCombo(label,preview);
    if (const char* key=std::strstr(label,"###")) {
        controls[key+3]=GImGui->LastItemData.Rect; control_ids[key+3]=GImGui->LastItemData.ID;
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
    if (key) { controls[key+3]=GImGui->LastItemData.Rect; control_ids[key+3]=GImGui->LastItemData.ID; }
    if (std::strstr(label,"###borderless_vsync")) vsync_rect=GImGui->LastItemData.Rect;
    if (std::strstr(label,"###show_fps")) osd_rect=GImGui->LastItemData.Rect;
    if (std::strstr(label,"###show_dlss_preset")) osd_preset_rect=GImGui->LastItemData.Rect;
    if (std::strstr(label,"###show_resolution")) resolution_rect=GImGui->LastItemData.Rect;
    return result;
}
bool TrackedSlider(const char* label,float* value,float lo,float hi,const char* format) {
    bool result=ImGui::SliderFloat(label,value,lo,hi,format);
    const char* key=std::strstr(label,"###");
    if (key) { controls[key+3]=GImGui->LastItemData.Rect; control_ids[key+3]=GImGui->LastItemData.ID; }
    return result;
}
'''
id_checks='\n'.join('    assert(ImHashStr('+a+') == ImHashStr('+b+'));' for a,b in pairs if '###' in decode(a))
main=r'''
void Frame(bool log=false) {
    ImGui::NewFrame();
    if (log) ImGui::LogToBuffer();
    Menu();
    FpsCounter();
    if (log) {
        const std::string content=GImGui->LogBuffer.c_str();
        assert(content.find("###")==std::string::npos);
        const bool ru=BbSettings::Get().menu_language==BbSettings::MenuRussian;
        assert(content.find(ru ? "Временной апскейлер" : "Temporal upscaler")!=std::string::npos);
        assert(content.find(ru ? "Хроматическая аберрация" : "Chromatic aberration")!=std::string::npos);
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
    auto* window=ImGui::FindWindowByName("###bbport_settings");
    assert(controls.contains(key));
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
    const float width=ImGui::FindWindowByName("###bbport_settings")->DC.ItemWidth;
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
void TestNavigation(ImGuiKey key) {
    auto& io=ImGui::GetIO();
    auto& s=BbSettings::Get();
    s.jitter=false;
    io.AddMousePosEvent(-100,-100);
    Reveal("jitter");
    auto* window=ImGui::FindWindowByName("###bbport_settings");
    auto rect=controls.at("jitter"); rect.Translate(ImVec2(-window->Pos.x,-window->Pos.y));
    ImGui::FocusWindow(window);
    ImGui::SetNavID(control_ids.at("jitter"),ImGuiNavLayer_Main,window->NavRootFocusScopeId,rect);
    ImGui::SetNavCursorVisibleAfterMove();
    Frame();
    io.AddKeyEvent(key,true); Frame();
    io.AddKeyEvent(key,false); Frame();
    assert(s.jitter);
}

int main(int argc,char** argv) {
    assert(argc==2);
    setenv("BB_CONFIG",argv[1],1);
    unsetenv("BB_RENDER_RES");
    const auto menu_path=std::filesystem::path{argv[1]}.replace_extension(".menu.ini");
    std::filesystem::remove(menu_path);
    auto& s=BbSettings::Get();
    assert(s.menu_language==BbSettings::MenuEnglish);
    s.cheat_supported=63u;
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
    const ImGuiID stable_language_id=language_id;
    // Drive the actual dropdown using ImGui input events in both directions.
    Click(language_rect.GetCenter());
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
    Click(language_rect.GetCenter());
    Frame(); Frame();
    Click(english_rect.GetCenter());
    Frame(true);
    assert(s.menu_language==BbSettings::MenuEnglish);
    assert(language_id==stable_language_id);
    // Select borderless and V-sync through the real controls without a restart.
    Click(window_rect.GetCenter()); Frame(); Frame();
    Click(borderless_rect.GetCenter()); Frame(true);
    assert(s.window_mode==BbSettings::Borderless);
    Click(vsync_rect.GetCenter()); Frame(true);
    assert(s.borderless_vsync);
    SetOpen(false); BbSettings::Load();
    assert(s.window_mode==BbSettings::Borderless && s.borderless_vsync);
    SetOpen(true); Frame();
    Click(window_rect.GetCenter()); Frame(); Frame();
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
    Click(dlss_rect.GetCenter()); Frame(); Frame();
    Click(preset_m_rect.GetCenter()); Frame(true);
    assert(s.dlss_preset==13 && s.preset==quality && s.output_res==output);
    auto osd=OsdFrame();
    assert(osd.find("DLSS (")==std::string::npos);
    OsdFrame();
    const float original_height=ImGui::FindWindowByName("##fps")->Size.y;
    const auto original_rows=std::count(osd.begin(),osd.end(),'\n');
    Frame(); Frame();
    Click(osd_preset_rect.GetCenter()); Frame(true);
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
    Click(osd_preset_rect.GetCenter()); Frame(true);
    assert(!s.show_dlss_preset && s.dlss_preset==13 && s.show_fps);
    assert(OsdFrame().find("DLSS (")==std::string::npos);
    Frame(); Frame();
    Click(osd_preset_rect.GetCenter()); Frame(true);
    assert(s.show_dlss_preset);
    Frame(); Frame();
    Click(osd_rect.GetCenter()); Frame(true);
    assert(!s.show_fps);
    assert(OsdFrame().empty());
    SetOpen(false); BbSettings::Load();
    assert(!s.show_fps && s.dlss_preset==13 && s.show_dlss_preset);
    SetOpen(true); Frame(); Frame();
    assert(ImGui::FindWindowByName("###bbport_settings")->Active);
    Click(osd_rect.GetCenter()); Frame(true);
    assert(s.show_fps && !OsdFrame().empty());
    Frame(); Frame();
    Click(dlss_rect.GetCenter()); Frame(); Frame();
    Click(preset_k_rect.GetCenter()); Frame(true);
    assert(s.dlss_preset==11 && s.preset==quality && s.output_res==output);
    SetOpen(false); BbSettings::Load();
    assert(s.show_fps && s.dlss_preset==11);
    SetOpen(true);
    // Real ImGui controls save the supervisor's policy immediately.
    Frame(); Frame();
    Click(background_rect.GetCenter()); Frame(); Frame();
    Click(pause_rect.GetCenter()); Frame();
    assert(s.background_mode==BbSettings::BackgroundPause);
    s.background_mode=BbSettings::BackgroundRun;
    BbSettings::Load();
    assert(s.background_mode==BbSettings::BackgroundPause);
    Click(background_rect.GetCenter()); Frame(); Frame();
    Click(run_rect.GetCenter()); Frame();
    assert(s.background_mode==BbSettings::BackgroundRun);
    Frame(); Frame();
    Click(resolution_rect.GetCenter()); Frame();
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
        TestBoolean("sharpen",s.sharpen);
        TestBoolean("jitter",s.jitter);
        TestBoolean("reactive",s.reactive);
        TestBoolean("object_motion",s.object_motion);
        TestBoolean("cheat_infinite_stamina",s.cheat_infinite_stamina);
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

    assert(restart_calls==0);
    ImGui::DestroyContext();
    std::puts("PASS: actual ImGui controls toggle basic/compact DLSS OSD; all seven active presets and pending changes stay on one row with the original window height; letters only in the OSD, full dropdown descriptions retained; shared settings survive saves; both languages/all upscalers tested; no restart from OSD choices.");
}
'''
# Check all constant widget label pairs against the actual Dear ImGui hash implementation.
main=main.replace('    IMGUI_CHECKVERSION();', id_checks+'\n    IMGUI_CHECKVERSION();')
(scratch / 'overlay_smoke.cpp').write_text(prefix+text_and_open+menu+fps+main)

command=shlex.split(args.compiler)+['-std=c++20','-O1','-pthread','-Igpu/shim','-Igpu/third_party/imgui',str(scratch/'overlay_smoke.cpp'),'gpu/shim/bbport_settings.cpp']+[str(p.relative_to(root)) for p in (root/'gpu/third_party/imgui').glob('imgui*.cpp') if p.name!='imgui_demo.cpp']+['-o',str(scratch/'overlay-test')]
subprocess.run(command,cwd=root,check=True)
subprocess.run([str(scratch/'overlay-test'),str(scratch/'config.ini')],cwd=root,check=True)
temporary.cleanup()
