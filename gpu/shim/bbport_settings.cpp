// SPDX-License-Identifier: GPL-2.0-or-later
#include "bbport_settings.h"
#include "../bbcheats.h"

#include <algorithm>
#include <cctype>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <string>
#include <string_view>
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

namespace BbSettings {
unsigned EffectiveFrameLimit(unsigned foreground_limit) {
    const auto& s = Get();
    if (s.window_focused || s.background_mode == BackgroundRun) {
        // The ordinary limit counts real game flips. Only an explicitly enabled
        // display cap may reduce that rate to account for generated frames.
        const unsigned multiplier=unsigned(std::max(1,s.frame_generation==FrameGenerationNvidia ?
            s.frame_generation_cap_multiplier.load() : s.frame_generation_active.load()));
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

float Clamp(float v, float lo, float hi) {
    return std::clamp(v, lo, hi);
}

void Set(Values& v, const std::string& key, const std::string& value) {
    const float f = float(std::atof(value.c_str()));
    const int i = std::atoi(value.c_str());
    if (key == "upscaler") {
        for (int u = 0; u < UpscalerCount; ++u) {
            if (value == UpscalerName(u)) {
                v.upscaler = u;
            }
        }
    } else if (key == "preset") {
        v.preset = std::clamp(i, 0, PresetCount - 1);
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
    } else if (key == "reactive_scale") {
        v.reactive_scale = Clamp(f, 0.0f, 16.0f);
    } else if (key == "reactive_threshold") {
        v.reactive_threshold = Clamp(f, 0.0f, 1.0f);
    } else if (key == "reactive_max") {
        v.reactive_max = Clamp(f, 0.0f, 1.0f);
    } else if (key == "debug_view") {
        v.debug_view = std::clamp(i, 0, DebugViewCount - 1);
    } else if (key == "show_fps") {
        v.show_fps = i != 0;
    } else if (key == "fsr4_auto_exposure") {
        v.fsr4_auto_exposure = i != 0;
    } else if (key == "fsr4_invert_jitter") {
        v.fsr4_invert_jitter = i != 0;
    } else if (key == "model_lod") {
        v.model_lod = std::clamp(i, -2, 2);
    } else if (key == "live_resolution") {
        v.live_resolution = value == "auto" ? -1 : std::clamp(i, 0, 1);
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
    v.show_resolution = false;
    v.show_frame_generation = false;
    v.show_latency = false;
    v.background_mode = BackgroundRun;
    v.frame_generation = FrameGenerationOff;
    v.limit_generated_fps = false;
    v.generated_fps_limit = 144;
    v.reflex=0;v.nvidia_generated_frames=1;
    v.cheat_damage = v.cheat_incoming = v.cheat_echoes = v.cheat_movement = 0;
    v.cheat_infinite_stamina = v.cheat_no_consume = false;
    v.cheat_no_fall_damage=false;
    for (int e = 0; e < EffectCount; ++e) {
        v.effects[e] = Effects[e].default_on;
    }
    if (FILE* file = std::fopen(Path(), "r")) {
        char line[256];
        while (std::fgets(line, sizeof(line), file)) {
            std::string text{line};
            text.erase(text.find_last_not_of(" \t\r\n") + 1);
            const auto eq = text.find('=');
            if (text.empty() || text[0] == '#' || eq == std::string::npos) {
                continue;
            }
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
            } else if (key == "show_fps") {
                v.show_fps = value == "1";
            } else if (key == "show_dlss_preset") {
                v.show_dlss_preset = value == "1";
            } else if (key == "show_frame_generation") {
                v.show_frame_generation = value == "1";
            } else if (key == "show_latency") {
                v.show_latency = value == "1";
            } else if (key == "show_resolution") {
                v.show_resolution = value == "1";
            } else if (key == "background_mode") {
                v.background_mode = value == "pause" ? BackgroundPause
                    : value == "30" ? Background30 : value == "60" ? Background60 : BackgroundRun;
            } else if (key == "frame_generation") {
                v.frame_generation = value == "fsr" ? FrameGenerationFsr : value == "nvidia" ? FrameGenerationNvidia : FrameGenerationOff;
            } else if (key == "reflex") {
                v.reflex=value=="boost" ? 2 : value=="on" ? 1 : 0;
            } else if (key == "nvidia_generated_frames") {
                v.nvidia_generated_frames=std::clamp(std::atoi(value.c_str()),1,5);
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
    };
    for (const auto& [env, key] : env_keys) {
        if (const char* value = std::getenv(env)) {
            Set(v, key, value);
        }
    }
    v.startup_preset = v.preset;
    v.startup_upscaler = v.upscaler;
    v.startup_object_motion = v.object_motion;
    for (int e = 0; e < EffectCount; ++e) {
        v.startup_effects[e] = v.effects[e];
    }
    v.startup_model_lod = v.model_lod;
    v.startup_output_res = v.output_res;
    v.startup_live_resolution = v.live_resolution;
    UpdateCheatMask();
}

void ConfigureUpscalerSupport(bool fsr4, bool fsr411) {
    auto& v = Get();
    v.fsr4_supported = fsr4;
    v.fsr411_supported = fsr4 && fsr411;
    const int requested = v.upscaler;
    if ((requested == UpscalerFsr4 && !v.fsr4_supported) ||
        (requested == UpscalerFsr411 && !v.fsr411_supported)) {
        v.fsr4_problem = "GPU does not support the selected FSR 4 shaders; using FSR 3.1";
        std::printf("Upscaler: %s unsupported on this GPU; falling back to FSR 3.1 before the first frame\n",
                    UpscalerName(requested));
        v.upscaler = UpscalerFsr3;
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

bool ResolutionNeedsRestart() {
    const auto& v = Get();
    // TAA needs the live path (native guest targets): run.sh selects it on restart.
    return FixedRenderSession() &&
        (v.preset != v.startup_preset || v.output_res != v.startup_output_res ||
         (v.upscaler == UpscalerOff) != (v.startup_upscaler == UpscalerOff) ||
         (v.upscaler == UpscalerTaa) != (v.startup_upscaler == UpscalerTaa));
}

void Save() {
    UpdateCheatMask();
    const auto& v = Get();
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
        const char* background_modes[] = {"run", "pause", "30", "60"};
        std::fprintf(file, "show_resolution=%d\nbackground_mode=%s\n",
                     int(v.show_resolution.load()),
                     background_modes[std::clamp(v.background_mode.load(), 0, 3)]);
        std::fprintf(file,"frame_generation=%s\n",v.frame_generation==FrameGenerationFsr ? "fsr" : v.frame_generation==FrameGenerationNvidia ? "nvidia" : "off");
        std::fprintf(file,"reflex=%s\nnvidia_generated_frames=%d\n",v.reflex==2 ? "boost" : v.reflex==1 ? "on" : "off",v.nvidia_generated_frames.load());
        std::fprintf(file,"limit_generated_fps=%d\ngenerated_fps_limit=%d\n",
                     int(v.limit_generated_fps.load()),v.generated_fps_limit.load());
        std::fprintf(file,"show_frame_generation=%d\nshow_latency=%d\n",
                     int(v.show_frame_generation.load()),int(v.show_latency.load()));
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
    FILE* file = std::fopen(Path(), "w");
    if (!file) {
        std::printf("Settings: cannot write %s\n", Path());
        return;
    }
    std::fprintf(file,
                 "# bbport settings (in-game menu: Insert / L3+R3)\n"
                 "upscaler=%s\npreset=%d\nsharpen=%d\nsharpness=%.2f\njitter=%d\n"
                 "reactive=%d\nobject_motion=%d\nreactive_scale=%.2f\nreactive_threshold=%.2f\nreactive_max=%.2f\n"
                 "debug_view=%d\nshow_fps=%d\nfsr4_auto_exposure=%d\nfsr4_invert_jitter=%d\n",
                 UpscalerName(v.upscaler), v.preset.load(), int(v.sharpen.load()),
                 v.sharpness.load(), int(v.jitter.load()), int(v.reactive.load()),
                 int(v.object_motion.load()),
                 v.reactive_scale.load(), v.reactive_threshold.load(), v.reactive_max.load(),
                 v.debug_view.load(), int(v.show_fps.load()),
                 int(v.fsr4_auto_exposure.load()), int(v.fsr4_invert_jitter.load()));
    // Read by patches.py at start.
    for (int e = 0; e < EffectCount; ++e) {
        std::fprintf(file, "%s=%d\n", Effects[e].key, int(v.effects[e].load()));
    }
    std::fprintf(file, "model_lod=%d\noutput_res=%dx%d\n", v.model_lod.load(),
                 OutputWidths[v.output_res], OutputHeights[v.output_res]);
    // Read by run.sh at start.
    std::fprintf(file, "live_resolution=%s\n", v.live_resolution < 0 ? "auto"
                                                  : v.live_resolution ? "1" : "0");
    std::fclose(file);
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

const char* UpscalerName(int upscaler) {
    static constexpr const char* names[UpscalerCount] = {"off", "fsr3", "fsr4", "fsr411", "taa", "dlss", "xess"};
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
