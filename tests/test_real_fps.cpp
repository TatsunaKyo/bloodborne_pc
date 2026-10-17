// SPDX-License-Identifier: GPL-2.0-or-later
#include "bbport_settings.h"
#include <cassert>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>

int main() {
    using namespace BbSettings;
    auto& s=Get();
    s.variable_frame_time=true;s.window_focused=true;s.background_mode=BackgroundRun;
    s.frame_generation=FrameGenerationFsr;s.frame_generation_active=2;s.limit_generated_fps=false;
    for (int cap : {30,60,75,90,120,144}) {
        s.real_fps_limit=cap;
        assert(EffectiveFrameLimit(120)==unsigned(cap)); // FG never consumes the real-frame limit.
    }
    s.real_fps_limit=-1;assert(EffectiveFrameLimit(120)==120);
    s.real_fps_limit=0;assert(EffectiveFrameLimit(120)==0);
    s.real_fps_limit=75;s.limit_generated_fps=true;s.generated_fps_limit=130;
    assert(EffectiveFrameLimit(120)==65); // Explicit total cap reduces the input rate.
    s.frame_generation=FrameGenerationNvidia;s.frame_generation_cap_multiplier=3;
    assert(EffectiveFrameLimit(120)==43);
    s.frame_generation_cap_multiplier=0;assert(EffectiveFrameLimit(120)==75);
    s.window_focused=false;s.background_mode=Background30;assert(EffectiveFrameLimit(120)==30);
    s.background_mode=Background60;assert(EffectiveFrameLimit(120)==60);
    s.real_fps_limit=30;assert(EffectiveFrameLimit(120)==30);
    s.variable_frame_time=false;s.window_focused=true;s.real_fps_limit=120;
    assert(EffectiveFrameLimit(60)==60); // A live setting cannot override a fixed game-timing patch.
    s.limit_generated_fps=false;

    s.variable_frame_time=true;s.window_focused=true;s.real_fps_limit=75;
    s.frame_generation=FrameGenerationNativeFsr;s.frame_generation_active=2;
    s.frame_gen_flip_limit=60;s.limit_generated_fps=true;s.generated_fps_limit=144;
    assert(EffectiveFrameLimit(120)==60); // FIFO and total cap both constrain the game.
    s.generated_fps_limit=90;assert(EffectiveFrameLimit(120)==45);
    s.frame_generation=FrameGenerationOff;assert(EffectiveFrameLimit(120)==75);
    s.frame_generation=FrameGenerationNativeDlss;s.startup_native_dlss=false;assert(EffectiveFrameLimit(120)==75);
    s.frame_gen_flip_limit=0;s.limit_generated_fps=false;

    const auto dir=std::filesystem::temp_directory_path()/
        ("bb-fps-test-"+std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
    std::filesystem::create_directory(dir);
    const auto config=dir/"bbport.ini",menu=dir/"bbport.menu.ini";
#ifdef _WIN32
    _putenv_s("BB_CONFIG",config.string().c_str());_putenv_s("BB_FPS","uncap");
#else
    setenv("BB_CONFIG",config.string().c_str(),1);setenv("BB_FPS","uncap",1);
#endif
    for (const auto text : {"-1","0","30","75","120","144","1000"}) {
        std::ofstream(menu)<<"real_fps_limit="<<text<<"\namd_antilag=1\n";
        Load();assert(s.real_fps_limit==std::atoi(text) && s.amd_antilag && s.variable_frame_time);
        Save();s.real_fps_limit=-1;s.amd_antilag=false;Load();
        assert(s.real_fps_limit==std::atoi(text) && s.amd_antilag);
    }
    for (const auto mode : {FrameGenerationNativeFsr,FrameGenerationNativeDlss}) {
        std::ofstream(config)<<"upscaler=dlss\nframe_gen_multiplier=4\nframe_gen_fit_display=1\n";
        std::ofstream(menu)<<"frame_generation="<<(mode==FrameGenerationNativeDlss ? "native_dlss" : "native_fsr")<<"\n";
        Load();assert(s.frame_generation==mode && s.frame_gen_multiplier==4 && s.frame_gen_fit_display);
        assert(s.startup_native_dlss==(mode==FrameGenerationNativeDlss));
        Save();s.frame_generation=FrameGenerationOff;s.frame_gen_multiplier=2;s.frame_gen_fit_display=false;Load();
        assert(s.frame_generation==mode && s.frame_gen_multiplier==4 && s.frame_gen_fit_display);
    }
    std::filesystem::remove(menu);std::ofstream(config)<<"frame_gen=dlss\n";Load();
    assert(s.frame_generation==FrameGenerationNativeDlss && s.startup_native_dlss);
    std::ofstream(menu)<<"frame_generation=nvidia\n";Load();
    assert(s.frame_generation==FrameGenerationNvidia && !s.startup_native_dlss);
    std::ofstream(config)<<"upscaler=fsr3\n";
    for (const auto text : {"","75x","-2","1","29","1001","nan","75.5"}) {
        std::ofstream(menu)<<"real_fps_limit="<<text<<"\n";
        Load();assert(s.real_fps_limit==-1 && !s.amd_antilag);
    }
#ifdef _WIN32
    _putenv_s("BB_FPS","60");
#else
    setenv("BB_FPS","60",1);
#endif
    Load();assert(!s.variable_frame_time);
    std::filesystem::remove_all(dir);
    std::puts("Real FPS: PASS (live caps, auto, uncapped, independent FG cap, background, fixed timing, strict preferences, persistence)");
}
