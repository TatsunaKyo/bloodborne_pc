// SPDX-License-Identifier: GPL-2.0-or-later
// bbport: user settings changed at run time from the in-game menu (bbport_overlay.h) and kept
// in bbport.ini (BB_CONFIG overrides the path). Environment variables override the file at
// start. Readers load the atomics every frame; writers are the menu and Load().

#pragma once

#include <atomic>
#include <string_view>

namespace BbSettings {

enum Upscaler : int { UpscalerOff = 0, UpscalerFsr3 = 1, UpscalerFsr4 = 2, UpscalerFsr411 = 3,
                      UpscalerTaa = 4, UpscalerDlss = 5, UpscalerCount };
/// FSR 4 v07 or FSR 4.1.1: the same inputs, settings and placement in the frame.
inline bool IsFsr4(int upscaler) {
    return upscaler == UpscalerFsr4 || upscaler == UpscalerFsr411;
}
enum Preset : int { NativeAA = 0, Quality, Balanced, Performance, UltraPerformance, PresetCount };
enum DebugView : int { DebugNone = 0, DebugReactive = 1, DebugMotion = 2, DebugViewCount };
enum MenuLanguage : int { MenuEnglish = 0, MenuRussian, MenuLanguageCount };
enum WindowMode : int { WindowFromLauncher = -1, Windowed = 0, Borderless, Fullscreen };
// NVIDIA NGX render-preset hints, separate from the upscaling quality/scene size.
// Removed and reserved presets are deliberately excluded.
inline constexpr int DlssPresetValues[] = {0, 5, 6, 10, 11, 13, 12};
inline constexpr int DlssPresetCount = 7;

/// Game effects switched by the community patches at start (patches.py EFFECTS): ini key,
/// Russian and English menu labels, default (the game's own behaviour).
struct Effect {
    const char* key;
    const char* label;
    const char* label_en;
    bool default_on;
};
inline constexpr Effect Effects[] = {
    {"effect_chromatic_aberration", "Хроматическая аберрация", "Chromatic aberration", true},
    {"effect_dof", "Глубина резкости (DoF)", "Depth of field (DoF)", true},
    {"effect_motion_blur", "Размытие в движении", "Motion blur", true},
    {"effect_ssao", "Затенение SSAO", "SSAO", true},
    {"effect_game_aa", "Собственное сглаживание игры", "Game's own anti-aliasing", true},
    {"effect_dynamic_shadows", "Тени от динамических источников", "Dynamic light shadows", true},
    {"effect_ssr", "Отражения SSR (не было в игре)", "SSR reflections (not in the original game)", false},
    {"skip_intro", "Пропуск заставок при запуске", "Skip startup intros", false},
    {"debug_camera", "Свободная камера (Cross + L3)", "Free camera (Cross + L3)", false},
    {"debug_menu", "Debug menu (нужны файлы шрифтов)", "Debug menu (requires font files)", false},
    {"cheat_no_death", "Чит: бессмертие (не ниже 1 HP)", "Cheat: never die (at least 1 HP)", false},
    {"cheat_stealth", "Чит: враги не замечают", "Cheat: enemies cannot see you", false},
    {"cheat_silent", "Чит: враги не слышат", "Cheat: enemies cannot hear you", false},
    {"cheat_rally_no_decay", "Чит: Rally не угасает", "Cheat: Rally never fades", false},
    {"cheat_enemy_control", "Чит: управление врагом (R3 / L3)", "Cheat: control an enemy (R3 / L3)", false},
    {"tweak_no_rally", "Без Rally (возврата HP)", "Disable Rally (HP recovery)", false},
    {"tweak_camera_distance", "Камера дальше", "Increase camera distance", false},
    {"tweak_no_camera_rotation", "Без автоповорота камеры", "Disable automatic camera rotation", false},
    {"tweak_easy_run", "Бег с меньшим наклоном стика", "Run with less stick tilt", false},
    {"tweak_ragdoll", "Физика тел как в Dark Souls", "Dark Souls-style ragdoll physics", false},
};
inline constexpr int EffectCount = int(sizeof(Effects) / sizeof(Effects[0]));
/// Live output resolutions: the upscaler's output and the UI host targets.
inline constexpr int OutputWidths[] = {1280, 1920, 2560, 3840};
inline constexpr int OutputHeights[] = {720, 1080, 1440, 2160};
inline constexpr int OutputCount = 4;
inline constexpr int OutputDefault = 1; ///< 1920x1080, the game's own size

struct Values {
    std::atomic<int> upscaler{UpscalerFsr3};
    std::atomic<int> preset{NativeAA};
    std::atomic<int> dlss_preset{0};
    // Preset requested by the current successfully created NGX feature, -1 before creation.
    // Driver/profile overrides may still determine the actual NVIDIA model.
    std::atomic<int> dlss_active_preset{-1};
    std::atomic<bool> sharpen{true};
    std::atomic<float> sharpness{0.3f};
    std::atomic<bool> jitter{true};
    std::atomic<bool> reactive{false};
    std::atomic<bool> object_motion{true};
    std::atomic<float> reactive_scale{1.0f};
    std::atomic<float> reactive_threshold{0.2f};
    std::atomic<float> reactive_max{0.9f};
    std::atomic<int> debug_view{DebugNone};
    std::atomic<bool> show_fps{false};
    /// The port's overlay language, kept separately in bbport.menu.ini beside bbport.ini.
    std::atomic<int> menu_language{MenuEnglish};
    /// -1 follows BB_FULLSCREEN; explicit choices survive launcher config rewrites.
    std::atomic<int> window_mode{WindowFromLauncher};
    std::atomic<bool> borderless_vsync{false};
    // FSR 4 checks (menu): the provider's auto exposure, the jitter sign it is given.
    std::atomic<bool> fsr4_auto_exposure{true};
    std::atomic<bool> fsr4_invert_jitter{false};
    std::atomic<int> active_render_width{1920}, active_render_height{1080};
    /// Applied at start (patches.py); the menu shows when a restart is needed.
    std::atomic<bool> effects[EffectCount]{};
    std::atomic<int> model_lod{0}; ///< -2 highest .. 2 lowest, 0 the game's
    std::atomic<int> output_res{OutputDefault}; ///< index into OutputWidths
    /// Live resolution and preset changes (run.sh): 0 off by default (startup patch, fastest
    /// on the Steam Deck and older GPUs), -1 auto (strong discrete GPUs), 1 on. On restart.
    std::atomic<int> live_resolution{0};
    /// Why FSR 4 cannot run (assets, device features), or null. Set by the renderer.
    std::atomic<const char*> fsr4_problem{nullptr};
    std::atomic<bool> fsr4_supported{false}, fsr411_supported{false};
    /// DLSS (bbport_dlss.dll, NVIDIA RTX) is ready, or why not (null before the device exists).
    std::atomic<bool> dlss_supported{false};
    std::atomic<const char*> dlss_problem{nullptr};

    /// Startup settings for the explicit BB_RENDER_RES compatibility patch only.
    int startup_preset = NativeAA;
    int startup_upscaler = UpscalerFsr3;
    bool startup_object_motion = true;
    bool startup_effects[EffectCount]{};
    int startup_model_lod = 0;
    int startup_output_res = OutputDefault;
    int startup_live_resolution = 0;
};

Values& Get();

/// Reads the file, then the environment overrides. Called once at start.
void Load();
/// Checks the loaded choice before the first frame; unsupported FSR 4 uses FSR 3.1.
void ConfigureUpscalerSupport(bool fsr4, bool fsr411);
/// After device creation: DLSS availability; a DLSS setting falls back to FSR 3.1 without it.
void ConfigureDlssSupport(bool available, const char* problem);
/// Startup-patched scene dimensions cannot change until run.sh prepares a new image.
bool FixedRenderSession();
int RenderPreset();
bool ResolutionNeedsRestart();
/// Writes the file (menu changes).
void Save();

/// Render resolution divisor of a preset (1.0 native, 1.5 quality, ...).
float PresetScale(int preset);
const char* PresetName(int preset);
int ParseDlssPreset(std::string_view value);
const char* DlssPresetKey(int preset);
const char* DlssPresetName(int preset);
const char* UpscalerName(int upscaler);

} // namespace BbSettings
