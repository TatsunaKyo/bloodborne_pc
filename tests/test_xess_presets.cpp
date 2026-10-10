// SPDX-License-Identifier: GPL-2.0-or-later
// TatsunaKyo revision: exercise the shared preferences and actual scene-size helper.
#include <cassert>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include "bbport_settings.h"
#include "video_core/renderer_vulkan/scene_resolution.h"
namespace SceneResolution = Vulkan::SceneResolution;

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
        ("bbport-xess-" + std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
    std::filesystem::create_directory(directory);
    const auto config = directory / "settings.ini", menu = directory / "settings.menu.ini";
    Env("BB_CONFIG", config.string().c_str());
    for (const char* key : {"BB_UPSCALER", "BB_UPSCALE_PRESET", "BB_XESS_PRESET", "BB_RENDER_RES"}) Env(key, nullptr);
    auto& s = Get();
    for (int legacy = 0; legacy < PresetCount; ++legacy) {
        { std::ofstream f(config); f << "upscaler=xess\npreset=" << legacy << '\n'; }
        for (const char* invalid : {"", "xess_preset=-1\n", "xess_preset=7\n", "xess_preset=invalid\n", "xess_preset=1.5\n"}) {
            { std::ofstream f(menu); f << invalid; }
            Load();
            assert(s.xess_preset == LegacyXessPreset(legacy));
            assert(std::abs(RenderScale() - PresetScale(legacy)) < .00001f);
            assert(s.startup_xess_preset == s.xess_preset);
        }
    }
    // A malformed companion value cannot erase a valid primary value.
    { std::ofstream f(config); f << "upscaler=xess\npreset=1\nxess_preset=1\n"; }
    { std::ofstream f(menu); f << "xess_preset=broken\n"; }
    Load(); assert(s.xess_preset == XessUltraQualityPlus);
    Env("BB_XESS_PRESET", "5"); Load(); assert(s.xess_preset == XessPerformance);
    Env("BB_XESS_PRESET", "invalid"); Load(); assert(s.xess_preset == XessUltraQualityPlus);
    Env("BB_XESS_PRESET", nullptr);
    constexpr SceneResolution::Size expected[] = {
        {1920,1080}, {1476,830}, {1280,720}, {1130,636}, {960,540}, {834,470}, {640,360}};
    for (int selected = 0; selected < XessPresetCount; ++selected) {
        s.upscaler = UpscalerXess; s.preset = Balanced; s.xess_preset = selected;
        Save(); s.xess_preset = -1; Load();
        assert(s.xess_preset == selected && s.preset == Balanced);
        assert(SceneResolution::ForScale(RenderScale()) == expected[selected]);
        assert(!ResolutionNeedsRestart());
        Env("BB_RENDER_RES", "startup-size");
        assert(s.startup_xess_preset == selected && !ResolutionNeedsRestart());
        const float startup_scale = RenderScale();
        s.xess_preset = (selected + 1) % XessPresetCount;
        assert(RenderScale() == startup_scale && ResolutionNeedsRestart());
        s.xess_preset = selected;
        assert(!ResolutionNeedsRestart());
        s.upscaler = UpscalerDlss;
        assert(RenderScale() == startup_scale && ResolutionNeedsRestart());
        Env("BB_RENDER_RES", nullptr);
        assert(RenderScale() == PresetScale(Balanced) && !ResolutionNeedsRestart());
        s.upscaler = UpscalerXess;
        assert(RenderScale() == XessPresetScale(selected));
        s.upscaler = UpscalerTaa;
        assert(RenderScale() == 1.0f && s.xess_preset == selected && s.preset == Balanced);
        for (int output = 0; output < OutputCount; ++output) {
            const auto size = SceneResolution::ForScale(XessPresetScale(selected),
                {uint32_t(OutputWidths[output]), uint32_t(OutputHeights[output])});
            assert(size.width >= 2 && size.height >= 2 && size.width % 2 == 0 && size.height % 2 == 0);
        }
    }
    assert(SceneResolution::ForScale(NAN) == SceneResolution::Size{});
    assert(SceneResolution::ForScale(INFINITY) == SceneResolution::Size{});
    Env("BB_CONFIG", nullptr);
    std::filesystem::remove_all(directory);
    std::puts("PASS: seven XeSS modes, legacy/invalid preferences, primary/menu/environment precedence, native scene sizes, save round trips, independent DLSS/FSR quality and frozen startup resolution.");
}
