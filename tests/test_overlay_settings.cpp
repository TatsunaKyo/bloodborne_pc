// SPDX-License-Identifier: GPL-2.0-or-later
// Overlay preferences must survive the original launcher rewriting bbport.ini.
#include <cassert>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include "bbport_settings.h"
#include "../gpu/bbcheats.h"

static void Env(const char* key, const char* value) {
#ifdef _WIN32
    assert(_putenv_s(key, value ? value : "") == 0);
#else
    assert((value ? setenv(key, value, 1) : unsetenv(key)) == 0);
#endif
}

int main() {
    using namespace BbSettings;
    const auto directory = std::filesystem::temp_directory_path() /
        ("bbport-overlay-" + std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
    std::filesystem::create_directory(directory);
    const auto config = directory / "bbport.ini", menu = directory / "bbport.menu.ini";
    Env("BB_CONFIG", config.string().c_str());
    Env("BB_WINDOW_MODE", nullptr);
    Env("BB_DLSS_PRESET", nullptr);
    Env("BB_RENDER_RES", nullptr);
    auto& cheat = Get();
    assert(cheat.cheat_damage==0 && cheat.cheat_movement==0 && !cheat.cheat_infinite_stamina);
    bbgpu_cheat_support(BB_CHEAT_ALL);
    for (int i=0;i<5;++i) {
        cheat.cheat_damage=i; cheat.cheat_incoming=i; cheat.cheat_echoes=i;
        for (int m=0;m<6;++m) {
            cheat.cheat_movement=m; cheat.cheat_infinite_stamina=i%2; cheat.cheat_no_consume=m%2;
            Save();
            { std::ofstream rewritten(config); rewritten << "upscaler=fsr3\npreset=0\n"; }
            Load();
            assert(cheat.cheat_damage==i && cheat.cheat_incoming==i && cheat.cheat_echoes==i);
            assert(cheat.cheat_movement==m && cheat.cheat_infinite_stamina==bool(i%2) && cheat.cheat_no_consume==bool(m%2));
            BbCheatOptions options; bbgpu_cheat_options(&options);
            assert(options.damage==unsigned(std::atoi(CheatMultiplierKeys[i])) && options.incoming==options.damage && options.echoes==options.damage);
            assert(options.movement==float(std::atof(MovementMultiplierKeys[m])));
        }
    }
    bbgpu_cheat_support(0); assert(cheat.cheat_active_mask==0);
    std::filesystem::remove(menu);
    Load();
    auto& settings = Get();
    Load();
    assert(settings.menu_language == MenuEnglish && settings.window_mode == WindowFromLauncher &&
           !settings.show_dlss_preset && !settings.show_resolution && settings.background_mode == BackgroundRun &&
           settings.frame_generation==FrameGenerationOff);
    for (int fg : {FrameGenerationOff,FrameGenerationFsr}) {
        settings.frame_generation=fg;
        Save();
        { std::ofstream file(config); file << "upscaler=dlss\npreset=2\n"; }
        settings.frame_generation=FrameGenerationOff;
        Load();
        assert(settings.frame_generation==fg);
    }
    { std::ofstream file(menu); file << "frame_generation=unknown\n"; }
    Load(); assert(settings.frame_generation==FrameGenerationOff);
    for (int mode : {BackgroundRun, BackgroundPause, Background30, Background60}) {
        for (bool show : {false, true}) {
            settings.background_mode = mode;
            settings.show_resolution = show;
            Save();
            { std::ofstream file(config); file << "upscaler=fsr3\npreset=0\n"; }
            settings.background_mode = BackgroundRun;
            settings.show_resolution = !show;
            Load();
            assert(settings.background_mode == mode && settings.show_resolution == show);
        }
    }
    { std::ofstream file(menu); file << "background_mode=invalid\nshow_resolution=invalid\n"; }
    Load();
    assert(settings.background_mode == BackgroundRun && !settings.show_resolution);
    for (unsigned foreground : {0u, 24u, 30u, 60u, 90u, 120u}) {
        for (int mode : {BackgroundRun, BackgroundPause, Background30, Background60}) {
            settings.background_mode = mode;
            settings.window_focused = true;
            assert(EffectiveFrameLimit(foreground) == foreground);
            settings.window_focused = false;
            const unsigned cap = mode == BackgroundRun ? 0u : mode == Background60 ? 60u : 30u;
            assert(EffectiveFrameLimit(foreground) == (cap ? (foreground ? std::min(foreground, cap) : cap) : foreground));
        }
    }
    settings.window_focused = true;
    for (int language : {MenuEnglish, MenuRussian}) {
        for (int mode : {WindowFromLauncher, Windowed, Borderless, Fullscreen}) {
            for (bool vsync : {false, true}) {
                settings.menu_language = language;
                settings.window_mode = mode;
                settings.borderless_vsync = vsync;
                Save();
                // The launcher writes only its cached main config, as it does after PLAY.
                { std::ofstream file(config); file << "upscaler=fsr3\npreset=0\n"; }
                settings.menu_language = MenuEnglish;
                settings.window_mode = WindowFromLauncher;
                settings.borderless_vsync = false;
                Load();
                assert(settings.menu_language == language && settings.window_mode == mode &&
                       settings.borderless_vsync == vsync);
            }
        }
    }
    { std::ofstream file(menu); file << "window_mode=invalid\nmenu_language=it\nborderless_vsync=bad\n"; }
    Load();
    assert(settings.menu_language == MenuEnglish && settings.window_mode == WindowFromLauncher &&
           !settings.borderless_vsync);
    { std::ofstream file(menu); file << "borderless_vsync=1\nwindow_mode=borderless\nmenu_language=ru\n"; }
    Load(); // Key order is not significant.
    assert(settings.menu_language == MenuRussian && settings.window_mode == Borderless && settings.borderless_vsync);
    Env("BB_WINDOW_MODE", "windowed");
    Load();
    assert(settings.window_mode == Windowed);
    Env("BB_WINDOW_MODE", "launcher");
    Load();
    assert(settings.window_mode == WindowFromLauncher);
    Env("BB_WINDOW_MODE", nullptr);
    for (int preset : DlssPresetValues) {
        for (bool show : {false, true}) {
            for (bool show_preset : {false, true}) {
                settings.dlss_preset = preset;
                settings.show_fps = show;
                settings.show_dlss_preset = show_preset;
                Save();
                { std::ofstream file(config); file << "upscaler=dlss\npreset=2\nshow_fps=" << !show << '\n'; }
                settings.dlss_preset = 0;
                settings.show_fps = !show;
                settings.show_dlss_preset = !show_preset;
                Load();
                assert(settings.dlss_preset == preset && settings.show_fps == show &&
                       settings.show_dlss_preset == show_preset);
                assert(settings.preset == Balanced);
                assert(ParseDlssPreset(DlssPresetKey(preset)) == preset);
                assert(ParseDlssPreset(std::to_string(preset)) == preset);
            }
        }
    }
    for (const char* invalid : {"a", "b", "d", "g", "i", "n", "1", "9", "14", "-1", "unknown", ""}) {
        assert(ParseDlssPreset(invalid) == 0);
        { std::ofstream file(menu); file << "dlss_preset=" << invalid << '\n'; }
        Load();
        assert(settings.dlss_preset == 0);
    }
    const char* short_names[] = {"Default", "E", "F", "J", "K", "M", "L"};
    for (int i = 0; i < DlssPresetCount; ++i) {
        assert(std::string(DlssPresetShortName(DlssPresetValues[i])) == short_names[i]);
    }
    assert(std::string(DlssPresetShortName(-1)) == "-");
    { std::ofstream file(menu); file << "show_dlss_preset=invalid\n"; }
    settings.show_dlss_preset = true;
    Load();
    assert(!settings.show_dlss_preset);
    for (const auto& [name, value] : {std::pair{"E", 5}, {"F", 6}, {"J", 10},
                                    {"K", 11}, {"L", 12}, {"M", 13}, {"DEFAULT", 0}}) {
        assert(ParseDlssPreset(name) == value);
    }
    std::filesystem::remove(menu);
    { std::ofstream file(config); file << "show_fps=0\n"; }
    Load();
    assert(!settings.show_fps);
    { std::ofstream file(menu); file << "show_fps=1\ndlss_preset=k\n"; }
    Load();
    assert(settings.show_fps && settings.dlss_preset == 11);
    Env("BB_RENDER_RES", "1280x720");
    settings.dlss_preset = 13;
    settings.show_fps = false;
    assert(!ResolutionNeedsRestart());
    Env("BB_RENDER_RES", nullptr);
    Env("BB_DLSS_PRESET", "M");
    Load();
    assert(settings.dlss_preset == 13);
    Env("BB_DLSS_PRESET", nullptr);
    Env("BB_CONFIG", nullptr);
    std::filesystem::remove_all(directory);
    std::puts("PASS: basic overlay by default, independent preset/OSD visibility persistence after launcher rewrites, all seven compact labels and preset IDs, language/window/V-sync round trips, invalid/reserved values, legacy FPS migration and environment overrides.");
}
