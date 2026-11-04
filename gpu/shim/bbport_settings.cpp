// SPDX-License-Identifier: GPL-2.0-or-later
#include "bbport_settings.h"
#include "../bbcheats.h"

#include <algorithm>
#include <cctype>
#include <charconv>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <unordered_set>
#include <string>
#include <string_view>
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

namespace BbSettings {
const char* FrameGenName(int mode) {
    static constexpr const char* names[FrameGenCount] = {"off", "fsr3", "dlss", "fsr401", "fsr402"};
    return names[std::clamp(mode, 0, FrameGenCount - 1)];
}
int NativeForRoute(int route) {
    switch (route) {
    case FrameGenerationNativeFsr: return FrameGenFsr3;
    case FrameGenerationNativeDlss: return FrameGenDlss;
    case FrameGenerationNativeFsr401: return FrameGenFsr401;
    case FrameGenerationNativeFsr402: return FrameGenFsr402;
    default: return FrameGenOff;
    }
}
int RouteForNative(int provider) {
    switch (provider) {
    case FrameGenFsr3: return FrameGenerationNativeFsr;
    case FrameGenDlss: return FrameGenerationNativeDlss;
    case FrameGenFsr401: return FrameGenerationNativeFsr401;
    case FrameGenFsr402: return FrameGenerationNativeFsr402;
    default: return FrameGenerationOff;
    }
}
const char* FrameGenerationKey(int route) {
    static constexpr const char* keys[] = {"off", "fsr", "nvidia", "native_fsr", "native_dlss", "native_fsr401", "native_fsr402"};
    return keys[std::clamp(route, 0, 6)];
}
int NativeProvider() {
    return Get().ActiveFrameGen();
}

unsigned EffectiveFrameLimit(unsigned foreground_limit) {
    const auto& s = Get();
    const int requested = s.real_fps_limit;
    if (s.variable_frame_time && requested >= 0)
        foreground_limit = unsigned(requested);
    if (s.window_focused || s.background_mode == BackgroundRun) {
        // The ordinary limit counts real game flips. Only an explicitly enabled
        // display cap may reduce that rate to account for generated frames.
        if (s.frame_gen_flip_limit > 0 && NativeProvider()!=FrameGenOff) {
            const unsigned cap=unsigned(s.frame_gen_flip_limit.load());
            foreground_limit=foreground_limit ? std::min(foreground_limit,cap) : cap;
        }
        const bool native_mode=s.frame_generation>=FrameGenerationNativeFsr;
        const unsigned multiplier=s.frame_generation==FrameGenerationOff || (native_mode && NativeProvider()==FrameGenOff) ? 1u :
            unsigned(std::max(1,s.frame_generation==FrameGenerationNvidia ?
                s.frame_generation_cap_multiplier.load() : native_mode ? s.frame_gen_now.load() + 1 : s.frame_generation_active.load()));
        if (s.limit_generated_fps && multiplier>1) {
            const unsigned real_cap=unsigned(std::clamp(s.generated_fps_limit.load(),30,1000))/multiplier;
            return foreground_limit ? std::min(foreground_limit,real_cap) : real_cap;
        }
        return foreground_limit;
    }
    const int mode = s.background_mode;
    const unsigned cap = mode == Background60 ? 60u :
                         (mode == Background30 || mode == BackgroundPause) ? 30u : 0u;
    return cap ? (foreground_limit ? std::min(foreground_limit, cap) : cap) : foreground_limit;
}

namespace {

const char* Path() {
    const char* env = std::getenv("BB_CONFIG");
    return env && env[0] ? env : "bbport.ini";
}

std::string MenuPath() {
    // Shared launcher/overlay preferences survive cached bbport.ini rewrites.
    return std::filesystem::path{Path()}.replace_extension(".menu.ini").string();
}

// Keep settings introduced by other launcher revisions. A failed append leaves
// the original file intact; the caller replaces it only after a complete close.
bool PreserveUnknownSettings(const char* original, const std::string& temporary) {
    std::unordered_set<std::string> written;
    auto key = [](const std::string& line) {
        const auto start = line.find_first_not_of(" \t\r");
        const auto equal = line.find('=');
        if (start == std::string::npos || line[start] == '#' || equal == std::string::npos)
            return std::string{};
        const auto end = line.find_last_not_of(" \t", equal - 1);
        return end < start ? std::string{} : line.substr(start, end - start + 1);
    };
    std::ifstream generated(temporary);
    if (!generated) return false;
    std::string line;
    while (std::getline(generated, line)) written.insert(key(line));
    if (generated.bad()) return false;
    generated.close();
    std::ifstream previous(original);
    if (!previous) return !std::filesystem::exists(original);
    std::ofstream append(temporary, std::ios::app);
    if (!append) return false;
    while (std::getline(previous, line)) {
        const auto name = key(line);
        if (!name.empty() && !written.contains(name)) append << line << '\n';
    }
    const bool read = !previous.bad();
    append.close();
    return read && bool(append);
}

float Clamp(float v, float lo, float hi) {
    return std::isfinite(v) ? std::clamp(v, lo, hi) : lo;
}

/// The FPS overlay's readouts: key=0|1 each, in the order the menu lists them.
struct Readout {
    const char* key;
    std::atomic<bool> Values::*member;
};
constexpr Readout Readouts[] = {
    {"show_fps", &Values::show_fps},
    {"show_frame_times", &Values::show_frame_times},
    {"show_render_latency", &Values::show_render_latency},
    {"show_vram", &Values::show_vram},
    {"show_gpu", &Values::show_gpu},
    {"show_cpu", &Values::show_cpu},
    {"show_ram", &Values::show_ram},
    {"show_fps_graph", &Values::show_fps_graph},
    {"counter_colors", &Values::counter_colors},
};

void Set(Values& v, const std::string& key, const std::string& value) {
    const float f = float(std::atof(value.c_str()));
    const int i = std::atoi(value.c_str());
    for (const Readout& readout : Readouts) {
        if (key == readout.key) {
            v.*readout.member = value != "0";
            return;
        }
    }
    if (key == "upscaler") {
        for (int u = 0; u < UpscalerCount; ++u) {
            if (value == UpscalerName(u)) {
                v.upscaler = u;
            }
        }
    } else if (key == "frame_gen") {
        for (int g = 0; g < FrameGenCount; ++g) {
            if (value == FrameGenName(g)) {
                v.frame_gen = g;
            }
        }
    } else if (key == "frame_gen_multiplier") {
        v.frame_gen_multiplier = std::clamp(i, 2, 4);
    } else if (key == "frame_gen_fit_display") {
        v.frame_gen_fit_display = i != 0;
    } else if (key == "preset") {
        v.preset = std::clamp(i, 0, PresetCount - 1);
    } else if (key == "xess_preset") {
        if (value.size() == 1 && value[0] >= '0' && value[0] < '0' + XessPresetCount)
            v.xess_preset = value[0] - '0';
    } else if (key == "sharpen") {
        v.sharpen = i != 0;
    } else if (key == "sharpness") {
        v.sharpness = Clamp(f, 0.0f, 2.0f);
    } else if (key == "jitter") {
        v.jitter = i != 0;
    } else if (key == "reactive") {
        v.reactive = i != 0;
    } else if (key == "object_motion") {
        v.object_motion = i != 0;
    } else if (key == "fsr411_backend") {
        v.fsr411_backend = value == "dx12" ? Fsr411Dx12 : Fsr411Vulkan;
    } else if (key == "fsr41_version") {
        v.fsr41_version = value == "fsr411" ? UpscalerFsr411 : UpscalerFsr412;
    } else if (key == "object_motion_cache") {
        v.object_motion_cache = value == "1";
    } else if (key == "fsr_compatibility_options") {
        v.fsr_compatibility_options = value == "1";
    } else if (key == "reactive_scale") {
        v.reactive_scale = Clamp(f, 0.0f, 16.0f);
    } else if (key == "reactive_threshold") {
        v.reactive_threshold = Clamp(f, 0.0f, 1.0f);
    } else if (key == "reactive_max") {
        v.reactive_max = Clamp(f, 0.0f, 1.0f);
    } else if (key == "debug_view") {
        v.debug_view = std::clamp(i, 0, DebugViewCount - 1);
    } else if (key == "mute_unfocused") {
        v.mute_unfocused = i != 0;
    } else if (key == "button_prompts") {
        v.button_prompts = value == "playstation" ? PromptsPlayStation
                         : value == "keyboard"    ? PromptsKeyboard
                         : value == "xbox"        ? PromptsXbox
                         : value == "switch"      ? PromptsSwitch
                                                  : PromptsAuto;
    } else if (key == "fsr4_auto_exposure") {
        v.fsr4_auto_exposure = i != 0;
    } else if (key == "fsr4_invert_jitter") {
        v.fsr4_invert_jitter = i != 0;
    } else if (key == "model_lod") {
        v.model_lod = std::clamp(i, -2, 2);
    } else if (key == "live_resolution") {
        v.live_resolution = value == "auto" ? -1 : std::clamp(i, 0, 1);
    } else if (key == "hud_position") {
        v.hud_position = std::clamp(i, 0, 100);
    } else if (key == "sharp_ui") {
        v.sharp_ui = i != 0;
    } else if (key == "fov") {
        v.fov = std::clamp(i, FovMin, FovMax);
    } else if (key == "fps_mode") {
        for (int m = 0; m < FpsModeCount; ++m) {
            if (value == FpsModeNames[m]) v.fps_mode = m;
        }
    } else if (key == "frame_cap") {
        v.frame_cap = value.empty() ? FrameCapAuto : std::max(i, 0);
    } else if (key == "output_res") {
        for (int r = 0; r < OutputCount; ++r) {
            if (value == std::to_string(OutputWidths[r]) + "x" + std::to_string(OutputHeights[r])) {
                v.output_res = r;
            }
        }
    } else {
        for (int e = 0; e < EffectCount; ++e) {
            if (key == Effects[e].key) {
                v.effects[e] = i != 0;
            }
        }
    }
}

} // namespace

Values& Get() {
    static Values values;
    return values;
}

void UpdateCheatMask() {
    auto& v = Get();
    const uint32_t mask = (v.cheat_damage ? uint32_t(BB_CHEAT_DAMAGE) : 0u) |
        (v.cheat_incoming ? uint32_t(BB_CHEAT_INCOMING) : 0u) |
        (v.cheat_echoes ? uint32_t(BB_CHEAT_ECHOES) : 0u) |
        (v.cheat_movement ? uint32_t(BB_CHEAT_MOVEMENT) : 0u) |
        (v.cheat_infinite_stamina ? uint32_t(BB_CHEAT_STAMINA) : 0u) |
        (v.cheat_no_consume ? uint32_t(BB_CHEAT_CONSUMABLES) : 0u) |
        (v.cheat_no_fall_damage ? uint32_t(BB_CHEAT_FALL) : 0u);
    v.cheat_active_mask.store(mask & v.cheat_supported.load(), std::memory_order_release);
}

void Load() {
    auto& v = Get();
    // Existing installations and unknown language codes use the English overlay.
    v.menu_language = MenuEnglish;
    v.window_mode = WindowFromLauncher;
    v.borderless_vsync = false;
    v.dlss_preset = 0;
    v.show_fps = false;
    v.show_dlss_preset = false;
    v.show_fg_preset = false;
    v.show_resolution = false;
    v.show_frame_generation = false;
    v.show_latency = false;
    v.show_frametime_graph = false;
    v.background_mode = BackgroundRun;
    v.frame_generation = FrameGenerationOff;
    v.frame_gen=FrameGenOff;v.frame_gen_multiplier=2;v.frame_gen_fit_display=false;
    bool explicit_frame_generation=false;
    bool root_frame_cap=false;
    v.limit_generated_fps = false;
    v.generated_fps_limit = 144;
    v.reflex=0;v.nvidia_generated_frames=1;
    v.nvidia_fg_preset=0;
    v.nvidia_fg_mod=false;v.nvidia_fg_mod_status=nullptr;
    v.amd_antilag = false;
    v.real_fps_limit = -1;
    v.frame_cap = FrameCapAuto;
    v.fps_mode = FpsUncap;
    const char* fps = std::getenv("BB_FPS");
    v.variable_frame_time = !fps || std::strcmp(fps,"uncap") == 0 || std::strcmp(fps,"75") == 0;
    v.cheat_damage = v.cheat_incoming = v.cheat_echoes = v.cheat_movement = 0;
    v.cheat_infinite_stamina = v.cheat_no_consume = false;
    v.cheat_no_fall_damage=false;
    v.xess_preset = -1;
    v.fg401_fallback = -1;
    v.fg401_fallback_source = -1;
    v.frame_gen_hdr = false;
    v.frame_gen_problem = nullptr;
    v.fg401_problem = nullptr;
    v.fg402_problem = nullptr;
    v.fsr411_backend = Fsr411Vulkan;
    v.fsr41_version = UpscalerFsr412;
    v.fsr4_method_problem = nullptr;
    v.object_motion_cache = true;
    v.fsr_compatibility_options = false;
    for (int e = 0; e < EffectCount; ++e) {
        v.effects[e] = Effects[e].default_on;
    }
    // Before the file: what the launcher started the game with (older bbport.ini files have no
    // fps_mode / frame_cap yet).
    if (const char* fps = std::getenv("BB_FPS")) Set(v, "fps_mode", fps);
    if (const char* cap = std::getenv("BB_FPS_LIMIT")) Set(v, "frame_cap", cap);
    if (FILE* file = std::fopen(Path(), "r")) {
        char line[256];
        while (std::fgets(line, sizeof(line), file)) {
            std::string text{line};
            text.erase(text.find_last_not_of(" \t\r\n") + 1);
            const auto eq = text.find('=');
            if (text.empty() || text[0] == '#' || eq == std::string::npos) {
                continue;
            }
            if (text.substr(0, eq) == "frame_cap") root_frame_cap = true;
            Set(v, text.substr(0, eq), text.substr(eq + 1));
        }
        std::fclose(file);
        std::printf("Settings: %s\n", Path());
    }
    if (FILE* file = std::fopen(MenuPath().c_str(), "r")) {
        char line[256];
        while (std::fgets(line, sizeof(line), file)) {
            std::string text{line};
            text.erase(text.find_last_not_of(" \t\r\n") + 1);
            const auto eq = text.find('=');
            if (eq == std::string::npos) continue;
            const auto key = text.substr(0, eq), value = text.substr(eq + 1);
            if (key == "menu_language") {
                v.menu_language = value == "ru" ? MenuRussian : MenuEnglish;
            } else if (key == "window_mode") {
                if (value == "windowed") v.window_mode = Windowed;
                else if (value == "borderless") v.window_mode = Borderless;
                else if (value == "fullscreen") v.window_mode = Fullscreen;
            } else if (key == "borderless_vsync") {
                v.borderless_vsync = value == "1";
            } else if (key == "dlss_preset") {
                v.dlss_preset = ParseDlssPreset(value);
            } else if (key == "xess_preset") {
                Set(v, key, value);
            } else if (key == "show_fps") {
                v.show_fps = value == "1";
            } else if (key == "show_dlss_preset") {
                v.show_dlss_preset = value == "1";
            } else if (key == "show_fg_preset") {
                v.show_fg_preset = value == "1";
            } else if (key == "show_frame_generation") {
                v.show_frame_generation = value == "1";
            } else if (key == "show_latency") {
                v.show_latency = value == "1";
            } else if (key == "show_frametime_graph") {
                v.show_frametime_graph = value == "1";
            } else if (key == "show_resolution") {
                v.show_resolution = value == "1";
            } else if (key == "background_mode") {
                v.background_mode = value == "pause" ? BackgroundPause
                    : value == "30" ? Background30 : value == "60" ? Background60 : BackgroundRun;
            } else if (key == "frame_generation") {
                explicit_frame_generation=true;
                v.frame_generation = FrameGenerationOff;
                for (int route = 0; route <= FrameGenerationNativeFsr402; ++route)
                    if (value == FrameGenerationKey(route)) v.frame_generation = route;
            } else if (key == "reflex") {
                v.reflex=value=="boost" ? 2 : value=="on" ? 1 : 0;
            } else if (key == "amd_antilag") {
                v.amd_antilag = value == "1";
            } else if (key == "real_fps_limit") {
                int limit = -1;
                const auto [end, error] = std::from_chars(value.data(), value.data()+value.size(), limit);
                if (error == std::errc{} && end == value.data()+value.size() &&
                    (limit == -1 || limit == 0 || (limit >= 30 && limit <= 1000)))
                    v.real_fps_limit = limit;
            } else if (key == "nvidia_generated_frames") {
                v.nvidia_generated_frames=std::clamp(std::atoi(value.c_str()),1,5);
            } else if (key == "nvidia_fg_preset") {
                v.nvidia_fg_preset=ParseNvidiaFgPreset(value);
            } else if (key == "nvidia_fg_mod") {
                v.nvidia_fg_mod = value == "1";
            } else if (key == "limit_generated_fps") {
                v.limit_generated_fps = value == "1";
            } else if (key == "generated_fps_limit") {
                v.generated_fps_limit = std::clamp(std::atoi(value.c_str()),30,1000);
            } else if (key == "cheat_damage" || key == "cheat_incoming" || key == "cheat_echoes") {
                int index = 0;
                for (int i = 0; i < 5; ++i) if (value == CheatMultiplierKeys[i]) index = i;
                if (key == "cheat_damage") v.cheat_damage = index;
                if (key == "cheat_incoming") v.cheat_incoming = index;
                if (key == "cheat_echoes") v.cheat_echoes = index;
            } else if (key == "cheat_movement") {
                int index = 0;
                for (int i = 0; i < 6; ++i) if (value == MovementMultiplierKeys[i]) index = i;
                v.cheat_movement = index;
            } else if (key == "cheat_infinite_stamina") {
                v.cheat_infinite_stamina = value == "1";
            } else if (key == "cheat_no_fall_damage") {
                v.cheat_no_fall_damage=value=="1";
            } else if (key == "cheat_no_consume") {
                v.cheat_no_consume = value == "1";
            }
        }
        std::fclose(file);
    }
    // Environment overrides (scripts, A/B tests).
    if (const char* env = std::getenv("BB_DLSS_PRESET")) {
        v.dlss_preset = ParseDlssPreset(env);
    }
    if (const char* env = std::getenv("BB_WINDOW_MODE")) {
        if (std::strcmp(env, "windowed") == 0) v.window_mode = Windowed;
        else if (std::strcmp(env, "borderless") == 0) v.window_mode = Borderless;
        else if (std::strcmp(env, "fullscreen") == 0) v.window_mode = Fullscreen;
        else if (std::strcmp(env, "launcher") == 0) v.window_mode = WindowFromLauncher;
    }
    if (const char* env = std::getenv("BB_UPSCALER")) {
        v.upscaler = UpscalerOff;
        for (int u = 0; u < UpscalerCount; ++u) {
            if (std::strcmp(env, UpscalerName(u)) == 0) v.upscaler = u;
        }
    }
    const std::pair<const char*, const char*> env_keys[] = {
        {"BB_FSR_SHARPNESS", "sharpness"},        {"BB_JITTER", "jitter"},
        {"BB_REACTIVE", "reactive"},              {"BB_REACTIVE_SCALE", "reactive_scale"},
        {"BB_REACTIVE_THRESHOLD", "reactive_threshold"}, {"BB_REACTIVE_MAX", "reactive_max"},
        {"BB_UPSCALE_PRESET", "preset"},            {"BB_OBJECT_MOTION", "object_motion"},
        {"BB_XESS_PRESET", "xess_preset"},
    };
    for (const auto& [env, key] : env_keys) {
        if (const char* value = std::getenv(env)) {
            Set(v, key, value);
        }
    }
    if (v.xess_preset < 0) v.xess_preset = LegacyXessPreset(v.preset);
    v.startup_preset = v.preset;
    v.startup_xess_preset = v.xess_preset;
    // Direct engine launches retain the explicit A/B overrides. Launcher starts refresh
    // their derived environment from this file in run.py, including after an overlay restart.
    const char* shared = std::getenv("BB_SHARED_GRAPHICS_CONFIG");
    if (!shared || std::strcmp(shared, "1") != 0) {
        if (const char* native = std::getenv("BB_FSR411_NATIVE")) {
            v.fsr411_backend = native[0] == '1' ? Fsr411Dx12 : Fsr411Vulkan;
        }
        if (const char* backend = std::getenv("BB_FSR411_BACKEND")) {
            Set(v, "fsr411_backend", backend);
        }
        if (const char* cache = std::getenv("BB_OBJECT_MOTION_CACHE")) {
            Set(v, "object_motion_cache", cache);
        }
    }
    if (v.upscaler == UpscalerFsr411 || v.upscaler == UpscalerFsr412) v.fsr41_version = v.upscaler.load();
    v.startup_upscaler = v.upscaler;
    v.startup_object_motion = v.object_motion;
    v.startup_fsr411_backend = v.fsr411_backend;
    v.active_fsr411_backend = v.fsr411_backend.load();
    v.startup_object_motion_cache = v.object_motion_cache;
    for (int e = 0; e < EffectCount; ++e) {
        v.startup_effects[e] = v.effects[e];
    }
    v.startup_model_lod = v.model_lod;
    v.startup_output_res = v.output_res;
    v.startup_hud_position = v.hud_position;
    v.startup_fov = v.fov;
    v.startup_fps_mode = v.fps_mode;
    // Root settings own the modern cap; consume the old menu only on migration.
    if (!root_frame_cap && !std::getenv("BB_FPS_LIMIT")) v.frame_cap = v.real_fps_limit.load();
    v.real_fps_limit = v.frame_cap.load();
    v.startup_frame_cap = v.frame_cap;
    v.startup_live_resolution = v.live_resolution;
    v.startup_nvidia_fg_preset = v.nvidia_fg_preset;
    v.startup_nvidia_fg_mod = v.nvidia_fg_mod;
    UpdateCheatMask();
    if (!explicit_frame_generation && v.frame_gen!=FrameGenOff)
        v.frame_generation=RouteForNative(v.frame_gen);
    v.frame_gen = NativeForRoute(v.frame_generation);
    v.startup_native_dlss = v.frame_generation == FrameGenerationNativeDlss;
    v.startup_workshop_nvidia = v.frame_generation == FrameGenerationNvidia;
    v.startup_reflex = v.reflex;
    v.startup_amd_antilag = v.amd_antilag;
}

void ConfigureUpscalerSupport(bool fsr4, bool fsr411, const char* fsr411_problem) {
    auto& v = Get();
    v.fsr4_supported = fsr4;
    v.fsr411_supported = fsr411;
    static std::string method_problem;
    method_problem = fsr411 ? "" : fsr411_problem ? fsr411_problem :
        "GPU/driver does not support the selected FSR 4.1.1 method";
    v.fsr411_problem = method_problem.empty() ? nullptr : method_problem.c_str();
    const int requested = v.upscaler;
    if ((requested == UpscalerFsr4 && !v.fsr4_supported) ||
        (requested == UpscalerFsr411 && !v.fsr411_supported)) {
        static std::string kept;
        kept = requested == UpscalerFsr411 && fsr411_problem ? fsr411_problem :
            "GPU/driver does not support the selected FSR 4 shaders";
        std::printf("Upscaler: %s unavailable: %s; falling back to FSR 3.1 before the first frame\n",
                    UpscalerName(requested), kept.c_str());
        kept += "; using FSR 3.1";
        v.fsr4_problem = kept.c_str();
        v.upscaler = UpscalerFsr3;
    }
}

void ConfigureFg401Support(bool available, const char* problem, int provider) {
    auto& v = Get();
    auto& supported = provider == FrameGenFsr402 ? v.fg402_supported : v.fg401_supported;
    auto& message = provider == FrameGenFsr402 ? v.fg402_problem : v.fg401_problem;
    supported = available;
    static std::string kept[2];
    auto& text = kept[provider == FrameGenFsr402];
    text = problem ? problem : "";
    message = available || text.empty() ? nullptr : text.c_str();
}

void SelectFrameGen(int provider) {
    auto& v = Get();
    v.frame_gen = std::clamp(provider, 0, FrameGenCount - 1);
    v.frame_generation = RouteForNative(v.frame_gen);
    v.fg401_fallback = -1;
    v.fg401_fallback_source = -1;
    v.frame_gen_problem = nullptr;
}

void FrameGenFailure(int provider, const char* problem) {
    auto& v = Get();
    if (IsMlFrameGen(provider)) {
        ConfigureFg401Support(false, problem, provider);
        v.fg401_fallback_source = provider;
        v.fg401_fallback = FrameGenFsr3;
        v.frame_gen_problem = "ML-FG failed; FSR 3.1 FG active.";
    } else if (IsMlFrameGen(v.frame_gen)) {
        v.fg401_fallback_source = v.frame_gen.load();
        v.fg401_fallback = FrameGenOff;
        v.frame_gen_problem = "Frame generation unavailable; FG off.";
    } else {
        // Existing DLSS / FSR 3.1 fallback policy.
        static std::string kept;
        kept = problem ? problem : "Frame generation failed.";
        v.frame_gen_problem = kept.c_str();
        v.frame_gen = provider == FrameGenDlss ? FrameGenFsr3 : FrameGenOff;
    }
}

void ConfigureDlssSupport(bool available, const char* problem) {
    auto& v = Get();
    v.dlss_supported = available;
    static std::string kept;
    kept = problem ? problem : "";
    v.dlss_problem = available || kept.empty() ? nullptr : kept.c_str();
    if (v.upscaler == UpscalerDlss && !available) {
        std::printf("Upscaler: DLSS unavailable (%s); falling back to FSR 3.1\n",
                    kept.empty() ? "bbport_dlss.dll or nvngx_dlss.dll missing" : kept.c_str());
        v.upscaler = UpscalerFsr3;
    }
}

bool FixedRenderSession() {
    const char* size = std::getenv("BB_RENDER_RES");
    return size && size[0];
}

int RenderPreset() {
    const auto& v = Get();
    return FixedRenderSession() ? v.startup_preset :
        v.upscaler == UpscalerTaa ? NativeAA : v.preset.load();
}

float RenderScale() {
    const auto& v = Get();
    const bool fixed = FixedRenderSession();
    const int provider = fixed ? v.startup_upscaler : v.upscaler.load();
    if (provider == UpscalerTaa) return 1.0f;
    if (provider == UpscalerXess) {
        const int preset = fixed ? v.startup_xess_preset : v.xess_preset.load();
        return XessPresetScale(preset < 0 ? LegacyXessPreset(v.preset) : preset);
    }
    return PresetScale(RenderPreset());
}

bool ResolutionNeedsRestart() {
    const auto& v = Get();
    // TAA needs the live path (native guest targets): run.sh selects it on restart. Ultrawide
    // outputs patch the camera and HUD at startup.
    if (v.output_res != v.startup_output_res &&
        (Ultrawide(v.output_res) || Ultrawide(v.startup_output_res))) return true;
    if (Ultrawide(v.output_res) && v.hud_position != v.startup_hud_position) return true;
    return FixedRenderSession() &&
        ((v.upscaler == UpscalerXess ? v.xess_preset != v.startup_xess_preset
                                    : v.preset != v.startup_preset) ||
         (v.upscaler == UpscalerXess) != (v.startup_upscaler == UpscalerXess) ||
         v.output_res != v.startup_output_res ||
         (v.upscaler == UpscalerOff) != (v.startup_upscaler == UpscalerOff) ||
         (v.upscaler == UpscalerTaa) != (v.startup_upscaler == UpscalerTaa));
}

bool FsrSettingsNeedRestart() {
    const auto& v = Get();
    const bool fsr_now = v.upscaler == UpscalerFsr3 || IsFsr4(v.upscaler);
    const bool fsr_start = v.startup_upscaler == UpscalerFsr3 || IsFsr4(v.startup_upscaler);
    return v.object_motion_cache != v.startup_object_motion_cache ||
        (v.object_motion_cache &&
         (fsr_now && v.object_motion) != (fsr_start && v.startup_object_motion));
}

void Save() {
    UpdateCheatMask();
    auto& v = Get();
    v.frame_gen = NativeForRoute(v.frame_generation);
    const std::string menu_path = MenuPath();
    const std::string temporary = menu_path + ".tmp";
    if (FILE* file = std::fopen(temporary.c_str(), "w")) {
        std::fprintf(file,"cheat_no_fall_damage=%d\n",int(v.cheat_no_fall_damage.load()));
        std::fprintf(file, "menu_language=%s\n", v.menu_language == MenuRussian ? "ru" : "en");
        const char* modes[] = {"launcher", "windowed", "borderless", "fullscreen"};
        std::fprintf(file, "window_mode=%s\nborderless_vsync=%d\n",
                     modes[std::clamp(v.window_mode.load(), -1, 2) + 1],
                     int(v.borderless_vsync.load()));
        std::fprintf(file, "dlss_preset=%s\nshow_fps=%d\nshow_dlss_preset=%d\n",
                     DlssPresetKey(v.dlss_preset), int(v.show_fps.load()),
                     int(v.show_dlss_preset.load()));
        std::fprintf(file, "xess_preset=%d\n", v.xess_preset < 0 ?
                     LegacyXessPreset(v.preset) : v.xess_preset.load());
        const char* background_modes[] = {"run", "pause", "30", "60"};
        std::fprintf(file, "show_resolution=%d\nbackground_mode=%s\n",
                     int(v.show_resolution.load()),
                     background_modes[std::clamp(v.background_mode.load(), 0, 3)]);
        std::fprintf(file,"frame_generation=%s\n",FrameGenerationKey(v.frame_generation));
        std::fprintf(file,"reflex=%s\nnvidia_generated_frames=%d\n",v.reflex==2 ? "boost" : v.reflex==1 ? "on" : "off",v.nvidia_generated_frames.load());
        std::fprintf(file,"nvidia_fg_preset=%s\n",NvidiaFgPresetKey(v.nvidia_fg_preset));
        std::fprintf(file,"nvidia_fg_mod=%d\n",int(v.nvidia_fg_mod.load()));
        std::fprintf(file,"amd_antilag=%d\nreal_fps_limit=%d\n",int(v.amd_antilag.load()),v.real_fps_limit.load());
        std::fprintf(file,"limit_generated_fps=%d\ngenerated_fps_limit=%d\n",
                     int(v.limit_generated_fps.load()),v.generated_fps_limit.load());
        std::fprintf(file,"show_frame_generation=%d\nshow_latency=%d\n",
                     int(v.show_frame_generation.load()),int(v.show_latency.load()));
        std::fprintf(file,"show_fg_preset=%d\n",int(v.show_fg_preset.load()));
        std::fprintf(file,"show_frametime_graph=%d\n",int(v.show_frametime_graph.load()));
        std::fprintf(file, "cheat_damage=%s\ncheat_incoming=%s\ncheat_echoes=%s\ncheat_movement=%s\n"
                          "cheat_infinite_stamina=%d\ncheat_no_consume=%d\n",
                     CheatMultiplierKeys[std::clamp(v.cheat_damage.load(), 0, 4)],
                     CheatMultiplierKeys[std::clamp(v.cheat_incoming.load(), 0, 4)],
                     CheatMultiplierKeys[std::clamp(v.cheat_echoes.load(), 0, 4)],
                     MovementMultiplierKeys[std::clamp(v.cheat_movement.load(), 0, 5)],
                     int(v.cheat_infinite_stamina.load()), int(v.cheat_no_consume.load()));
        const bool complete = !std::ferror(file);
        const bool closed = std::fclose(file) == 0;
        // The focus supervisor must see a complete policy, even when the game saves
        // while it is reading the file. Windows rename does not replace by default.
#ifdef _WIN32
        if (!complete || !closed || !MoveFileExA(temporary.c_str(), menu_path.c_str(), MOVEFILE_REPLACE_EXISTING))
#else
        if (!complete || !closed || std::rename(temporary.c_str(), menu_path.c_str()) != 0)
#endif
            std::printf("Settings: cannot replace %s\n", menu_path.c_str());
    } else {
        std::printf("Settings: cannot write %s\n", menu_path.c_str());
    }
    const std::string root_temporary = std::string(Path()) + ".tmp";
    FILE* file = std::fopen(root_temporary.c_str(), "w");
    if (!file) {
        std::printf("Settings: cannot write %s\n", Path());
        return;
    }
    std::fprintf(file,
                 "# bbport settings (in-game menu: Insert / L3+R3)\n"
                 "upscaler=%s\npreset=%d\nsharpen=%d\nsharpness=%.2f\njitter=%d\n"
                 "reactive=%d\nobject_motion=%d\nreactive_scale=%.2f\nreactive_threshold=%.2f\nreactive_max=%.2f\n"
                 "debug_view=%d\nfsr4_auto_exposure=%d\nfsr4_invert_jitter=%d\n",
                 UpscalerName(v.upscaler), v.preset.load(), int(v.sharpen.load()),
                 v.sharpness.load(), int(v.jitter.load()), int(v.reactive.load()),
                 int(v.object_motion.load()),
                 v.reactive_scale.load(), v.reactive_threshold.load(), v.reactive_max.load(),
                 v.debug_view.load(), int(v.fsr4_auto_exposure.load()),
                 int(v.fsr4_invert_jitter.load()));
    for (const Readout& readout : Readouts) {
        std::fprintf(file, "%s=%d\n", readout.key, int((v.*readout.member).load()));
    }
    std::fprintf(file, "xess_preset=%d\n", v.xess_preset.load());
    std::fprintf(file, "fsr411_backend=%s\nobject_motion_cache=%d\n",
                 v.fsr411_backend == Fsr411Dx12 ? "dx12" : "vk",
                 int(v.object_motion_cache.load()));
    std::fprintf(file, "fsr_compatibility_options=%d\n", int(v.fsr_compatibility_options.load()));
    std::fprintf(file, "fsr41_version=%s\n", v.fsr41_version == UpscalerFsr411 ? "fsr411" : "fsr412");
    // Read by patches.py at start.
    for (int e = 0; e < EffectCount; ++e) {
        std::fprintf(file, "%s=%d\n", Effects[e].key, int(v.effects[e].load()));
    }
    std::fprintf(file, "frame_gen=%s\nframe_gen_multiplier=%d\nframe_gen_fit_display=%d\n",
                 FrameGenName(NativeForRoute(v.frame_generation)), v.frame_gen_multiplier.load(),
                 int(v.frame_gen_fit_display.load()));
    std::fprintf(file, "model_lod=%d\noutput_res=%dx%d\n", v.model_lod.load(),
                 OutputWidths[v.output_res], OutputHeights[v.output_res]);
    std::fprintf(file, "mute_unfocused=%d\n", int(v.mute_unfocused.load()));
    static constexpr const char* prompts[PromptsCount] = {"auto", "playstation", "keyboard", "xbox", "switch"};
    std::fprintf(file, "button_prompts=%s\n", prompts[std::clamp(v.button_prompts.load(), 0, PromptsCount - 1)]);
    // Read by run.py at start (hud_layout.py).
    std::fprintf(file, "hud_position=%d\n", v.hud_position.load());
    // Read by run.py and patches.py at start (ui_viewport).
    std::fprintf(file, "sharp_ui=%d\n", int(v.sharp_ui.load()));
    // Read by run.py at start (fov.py).
    std::fprintf(file, "fov=%d\n", v.fov.load());
    // Read by run.py at start (patches.py FPS preset, BB_FPS_LIMIT); the launcher shares them.
    std::fprintf(file, "fps_mode=%s\n", FpsModeNames[std::clamp(v.fps_mode.load(), 0, FpsModeCount - 1)]);
    if (v.frame_cap < 0) {
        std::fprintf(file, "frame_cap=\n");
    } else {
        std::fprintf(file, "frame_cap=%d\n", v.frame_cap.load());
    }
    // Read by run.sh at start.
    std::fprintf(file, "live_resolution=%s\n", v.live_resolution < 0 ? "auto"
                                                  : v.live_resolution ? "1" : "0");
    const bool complete = !std::ferror(file);
    const bool closed = std::fclose(file) == 0;
#ifdef _WIN32
    const bool replaced = complete && closed && PreserveUnknownSettings(Path(), root_temporary) && MoveFileExA(root_temporary.c_str(), Path(), MOVEFILE_REPLACE_EXISTING);
#else
    const bool replaced = complete && closed && PreserveUnknownSettings(Path(), root_temporary) && std::rename(root_temporary.c_str(), Path()) == 0;
#endif
    if (!replaced) {
        std::remove(root_temporary.c_str());
        std::printf("Settings: cannot replace %s\n", Path());
    }
}

int ParseNvidiaFgPreset(std::string_view value) {
    if (value=="a" || value=="A") return 1;
    if (value=="b" || value=="B") return 2;
    if (value=="c" || value=="C") return 3;
    return 0;
}
const char* NvidiaFgPresetKey(int preset) {
    constexpr const char* keys[]={"default","a","b","c"};
    return keys[std::clamp(preset,0,3)];
}
const char* NvidiaFgPresetName(int preset) {
    constexpr const char* names[]={"Default (NVIDIA settings)","A","B","C (Performance / beta)"};
    return names[std::clamp(preset,0,3)];
}

int ParseDlssPreset(std::string_view value) {
    std::string key{value};
    std::ranges::transform(key, key.begin(), [](unsigned char c) { return char(std::tolower(c)); });
    for (int preset : DlssPresetValues) {
        if (key == DlssPresetKey(preset) || key == std::to_string(preset)) return preset;
    }
    return 0;
}

const char* DlssPresetKey(int preset) {
    static constexpr const char* keys[] = {"default", "e", "f", "j", "k", "m", "l"};
    for (int i = 0; i < DlssPresetCount; ++i) {
        if (preset == DlssPresetValues[i]) return keys[i];
    }
    return keys[0];
}

const char* DlssPresetName(int preset) {
    static constexpr const char* names[] = {"Default (driver)", "E (CNN / legacy)", "F (CNN / legacy)",
                                          "J (Transformer 1st gen)", "K (Transformer 1st gen)",
                                          "M (Transformer 2nd gen)", "L (Transformer 2nd gen)"};
    for (int i = 0; i < DlssPresetCount; ++i) {
        if (preset == DlssPresetValues[i]) return names[i];
    }
    return names[0];
}

const char* DlssPresetShortName(int preset) {
    static constexpr const char* names[] = {"Default", "E", "F", "J", "K", "M", "L"};
    for (int i = 0; i < DlssPresetCount; ++i) {
        if (preset == DlssPresetValues[i]) return names[i];
    }
    return "-";
}

float PresetScale(int preset) {
    static constexpr float scales[PresetCount] = {1.0f, 1.5f, 1.7f, 2.0f, 3.0f};
    return scales[std::clamp(preset, 0, PresetCount - 1)];
}

const char* PresetName(int preset) {
    static constexpr const char* names[PresetCount] = {"Native AA", "Quality", "Balanced",
                                                       "Performance", "Ultra Performance"};
    return names[std::clamp(preset, 0, PresetCount - 1)];
}

int LegacyXessPreset(int preset) {
    static constexpr int modes[PresetCount] = {
        XessNativeAA, XessUltraQuality, XessQuality, XessBalanced, XessUltraPerformance};
    return modes[std::clamp(preset, 0, PresetCount - 1)];
}

float XessPresetScale(int preset) {
    static constexpr float scales[XessPresetCount] = {1.0f, 1.3f, 1.5f, 1.7f, 2.0f, 2.3f, 3.0f};
    return scales[std::clamp(preset, 0, XessPresetCount - 1)];
}

const char* XessPresetName(int preset) {
    static constexpr const char* names[XessPresetCount] = {
        "Native AA", "Ultra Quality Plus", "Ultra Quality", "Quality", "Balanced",
        "Performance", "Ultra Performance"};
    return names[std::clamp(preset, 0, XessPresetCount - 1)];
}

const char* UpscalerName(int upscaler) {
    static constexpr const char* names[UpscalerCount] = {"off", "fsr3", "fsr4", "fsr411", "taa", "dlss", "xess", "fsr412"};
    return names[std::clamp(upscaler, 0, UpscalerCount - 1)];
}

} // namespace BbSettings

extern "C" const void* bbgpu_cheat_mask_address() {
    static_assert(std::atomic<uint32_t>::is_always_lock_free);
    static_assert(sizeof(std::atomic<uint32_t>) == sizeof(uint32_t));
    return &BbSettings::Get().cheat_active_mask;
}

extern "C" void bbgpu_cheat_options(BbCheatOptions* options) {
    const auto& v = BbSettings::Get();
    static constexpr unsigned multipliers[] = {1, 2, 4, 8, 16};
    static constexpr float movement[] = {1.0f, 1.5f, 2.0f, 4.0f, 8.0f, 16.0f};
    *options = {multipliers[std::clamp(v.cheat_damage.load(), 0, 4)],
                multipliers[std::clamp(v.cheat_incoming.load(), 0, 4)],
                multipliers[std::clamp(v.cheat_echoes.load(), 0, 4)],
                movement[std::clamp(v.cheat_movement.load(), 0, 5)],
                int(v.cheat_infinite_stamina.load()), int(v.cheat_no_consume.load()),int(v.cheat_no_fall_damage.load())};
}

extern "C" void bbgpu_cheat_support(uint32_t mask) {
    BbSettings::Get().cheat_supported = mask;
    BbSettings::UpdateCheatMask();
}
