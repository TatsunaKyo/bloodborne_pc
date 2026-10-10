// SPDX-License-Identifier: GPL-2.0-or-later
#include "bbport_overlay.h"

#include <atomic>
#include <cfloat>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <mutex>
#include <string>

#include <SDL3/SDL.h>
#include "bbport_settings.h"
#include "imgui.h"
#include "imgui_impl_vulkan.h"
#include "video_core/renderer_vulkan/vk_instance.h"
#include "video_core/renderer_vulkan/vk_scheduler.h"

// DejaVu Sans (Cyrillic), embedded (third_party/fonts, Bitstream Vera license).
#ifdef _WIN32
asm(".section .rdata,\"dr\"\n"
    ".balign 16\n"
    ".global bb_font_ttf\n"
    "bb_font_ttf:\n"
    ".incbin \"" BB_FONT_PATH "\"\n"
    ".global bb_font_ttf_end\n"
    "bb_font_ttf_end:\n"
    ".text\n");
#else
asm(".section .rodata\n"
    ".balign 16\n"
    ".hidden bb_font_ttf\n"
    ".global bb_font_ttf\n"
    "bb_font_ttf:\n"
    ".incbin \"" BB_FONT_PATH "\"\n"
    ".hidden bb_font_ttf_end\n"
    ".global bb_font_ttf_end\n"
    "bb_font_ttf_end:\n"
    ".previous\n");
#endif
extern "C" const unsigned char bb_font_ttf[];
extern "C" const unsigned char bb_font_ttf_end[];

extern "C" void runtime_restart(void); // bb-probe (probe.c)

namespace BbOverlay {

namespace {

std::mutex imgui_mutex; // the ImGui context: window thread (input) and present thread
bool initialized = false;
std::atomic<bool> menu_open{false};
bool l3_down = false, r3_down = false;
bool dirty = false; // settings changed while open: saved on close
// The game's text dialog (SetTextEntry), guarded by imgui_mutex.
bool text_entry_active = false;
std::string text_entry_prompt, text_entry_text;
float base_scale = 1.0f;

// Present rate for the FPS counter.
std::chrono::steady_clock::time_point last_present{};
float frame_ms_avg = 0.0f;

const char* Text(const char* english, const char* russian) {
    return BbSettings::Get().menu_language == BbSettings::MenuRussian ? russian : english;
}

void SetOpen(bool value) {
    if (menu_open.exchange(value) == value) {
        return;
    }
    ImGui::GetIO().MouseDrawCursor = value;
    if (!value && dirty) {
        dirty = false;
        BbSettings::Save();
    }
}

ImGuiKey KeyFromSdl(SDL_Keycode key) {
    switch (key) {
    case SDLK_TAB: return ImGuiKey_Tab;
    case SDLK_LEFT: return ImGuiKey_LeftArrow;
    case SDLK_RIGHT: return ImGuiKey_RightArrow;
    case SDLK_UP: return ImGuiKey_UpArrow;
    case SDLK_DOWN: return ImGuiKey_DownArrow;
    case SDLK_PAGEUP: return ImGuiKey_PageUp;
    case SDLK_PAGEDOWN: return ImGuiKey_PageDown;
    case SDLK_HOME: return ImGuiKey_Home;
    case SDLK_END: return ImGuiKey_End;
    case SDLK_DELETE: return ImGuiKey_Delete;
    case SDLK_BACKSPACE: return ImGuiKey_Backspace;
    case SDLK_SPACE: return ImGuiKey_Space;
    case SDLK_RETURN: return ImGuiKey_Enter;
    case SDLK_KP_ENTER: return ImGuiKey_KeypadEnter;
    case SDLK_ESCAPE: return ImGuiKey_Escape;
    case SDLK_LCTRL: return ImGuiKey_LeftCtrl;
    case SDLK_RCTRL: return ImGuiKey_RightCtrl;
    case SDLK_LSHIFT: return ImGuiKey_LeftShift;
    case SDLK_RSHIFT: return ImGuiKey_RightShift;
    case SDLK_LALT: return ImGuiKey_LeftAlt;
    case SDLK_RALT: return ImGuiKey_RightAlt;
    default: return ImGuiKey_None;
    }
}

ImGuiKey KeyFromGamepad(u8 button) {
    switch (button) {
    case SDL_GAMEPAD_BUTTON_SOUTH: return ImGuiKey_GamepadFaceDown;
    case SDL_GAMEPAD_BUTTON_EAST: return ImGuiKey_GamepadFaceRight;
    case SDL_GAMEPAD_BUTTON_WEST: return ImGuiKey_GamepadFaceLeft;
    case SDL_GAMEPAD_BUTTON_NORTH: return ImGuiKey_GamepadFaceUp;
    case SDL_GAMEPAD_BUTTON_DPAD_UP: return ImGuiKey_GamepadDpadUp;
    case SDL_GAMEPAD_BUTTON_DPAD_DOWN: return ImGuiKey_GamepadDpadDown;
    case SDL_GAMEPAD_BUTTON_DPAD_LEFT: return ImGuiKey_GamepadDpadLeft;
    case SDL_GAMEPAD_BUTTON_DPAD_RIGHT: return ImGuiKey_GamepadDpadRight;
    case SDL_GAMEPAD_BUTTON_LEFT_SHOULDER: return ImGuiKey_GamepadL1;
    case SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER: return ImGuiKey_GamepadR1;
    case SDL_GAMEPAD_BUTTON_START: return ImGuiKey_GamepadStart;
    case SDL_GAMEPAD_BUTTON_BACK: return ImGuiKey_GamepadBack;
    default: return ImGuiKey_None;
    }
}

float PixelDensity(SDL_WindowID id) {
    SDL_Window* window = SDL_GetWindowFromID(id);
    const float density = window ? SDL_GetWindowPixelDensity(window) : 1.0f;
    return density > 0.0f ? density : 1.0f;
}

// Marks the settings dirty when a widget changed them.
template <typename T>
void Store(std::atomic<T>& target, T value, bool changed) {
    if (changed) {
        target = value;
        BbSettings::UpdateCheatMask();
        dirty = true;
    }
}

void Checkbox(const char* label, std::atomic<bool>& value) {
    bool v = value;
    const bool changed = ImGui::Checkbox(label, &v);
    Store(value, v, changed);
}

void Slider(const char* label, std::atomic<float>& value, float lo, float hi) {
    float v = value;
    const bool changed = ImGui::SliderFloat(label, &v, lo, hi, "%.2f");
    Store(value, v, changed);
}

void Hint(const char* text) {
    ImGui::SameLine();
    ImGui::TextDisabled("(?)");
    if (ImGui::BeginItemTooltip()) {
        ImGui::PushTextWrapPos(ImGui::GetFontSize() * 30.0f);
        ImGui::TextUnformatted(text);
        ImGui::PopTextWrapPos();
        ImGui::EndTooltip();
    }
}

void Menu() {
    auto& s = BbSettings::Get();
    const ImGuiViewport* viewport = ImGui::GetMainViewport();
    ImGui::SetNextWindowPos(ImVec2(viewport->WorkPos.x + 40.0f * base_scale,
                                   viewport->WorkPos.y + 40.0f * base_scale),
                            ImGuiCond_Appearing);
    ImGui::SetNextWindowSize(ImVec2(620.0f * base_scale, 0.0f), ImGuiCond_Appearing);
    bool keep_open = true;
    // Keep window and widget IDs independent of the displayed language (### suffixes).
    if (!ImGui::Begin(Text("Bloodborne — settings  (Insert / L3+R3)###bbport_settings",
                           "Bloodborne — настройки  (Insert / L3+R3)###bbport_settings"), &keep_open,
                      ImGuiWindowFlags_NoCollapse)) {
        ImGui::End();
        return;
    }
    ImGui::Text(Text("%.0f FPS  (%.1f ms)", "%.0f FPS  (%.1f мс)"),
                frame_ms_avg > 0.0f ? 1000.0f / frame_ms_avg : 0.0f, frame_ms_avg);

    static const char* languages[] = {"English", "Русский"};
    int language = s.menu_language;
    if (ImGui::BeginCombo(Text("Menu language###menu_language", "Язык меню###menu_language"),
                          languages[language])) {
        for (int i = 0; i < BbSettings::MenuLanguageCount; ++i) {
            if (ImGui::Selectable(languages[i], i == language)) {
                Store(s.menu_language, i, true);
            }
        }
        ImGui::EndCombo();
    }

    Checkbox(Text("Show performance overlay###show_fps", "Показывать статистику###show_fps"), s.show_fps);
    Hint(Text("FPS, frame time and upscaler in the top-right corner. "
              "Hide it without disabling this settings menu.",
              "FPS, время кадра и апскейлер в правом верхнем углу. "
              "Отключение не скрывает это меню настроек."));
    Checkbox(Text("Show DLSS preset in overlay###show_dlss_preset",
                  "Показывать пресет DLSS в статистике###show_dlss_preset"), s.show_dlss_preset);
    Hint(Text("Add the preset letter on the same line. K>M means K is active and M is pending. "
              "Turn this off to keep the original overlay.",
              "Буква пресета в той же строке. K>M: K активен, M ожидает применения. "
              "Выключите для исходной статистики."));
    Checkbox(Text("Show input/output resolution in overlay###show_resolution",
                  "Показывать разрешение входа/выхода###show_resolution"), s.show_resolution);
    Hint(Text("Add the current render and output sizes on the same OSD line.",
              "Текущее разрешение рендера и вывода в той же строке статистики."));
    const char* background_modes[] = {
        Text("Keep running###background_run", "Продолжать работу###background_run"),
        Text("Pause game and rendering###background_pause", "Приостановить игру и рендер###background_pause"),
        "30 FPS", "60 FPS",
    };
    int background = s.background_mode;
    if (ImGui::BeginCombo(Text("When in background###background_mode", "В фоне###background_mode"),
                          background_modes[background])) {
        for (int i = 0; i < 4; ++i) {
            if (ImGui::Selectable(background_modes[i], i == background)) {
                Store(s.background_mode, i, true);
                // Save before focus can be lost, rather than waiting for menu close.
                BbSettings::Save();
                dirty = false;
            }
        }
        ImGui::EndCombo();
    }
    Hint(Text("When the window loses focus: keep running, pause the entire game on Windows, "
              "or cap background rendering. Your foreground frame cap is kept.",
              "При потере фокуса: продолжать, приостановить всю игру в Windows "
              "или ограничить FPS в фоне. Основной лимит FPS сохраняется."));

    const char* window_modes[] = {
        Text("Launcher setting###window_launcher", "Настройка лаунчера###window_launcher"),
        Text("Windowed###window_windowed", "Оконный###window_windowed"),
        Text("Borderless fullscreen (low latency)###window_borderless",
             "Без рамки на весь экран (низкая задержка)###window_borderless"),
        Text("Fullscreen (driver default)###window_fullscreen",
             "Полный экран (настройка драйвера)###window_fullscreen"),
    };
    int window_mode = s.window_mode.load() + 1;
    if (ImGui::BeginCombo(Text("Window mode###window_mode", "Режим окна###window_mode"),
                          window_modes[window_mode])) {
        for (int i = 0; i < 4; ++i) {
            if (ImGui::Selectable(window_modes[i], i == window_mode)) {
                Store(s.window_mode, i - 1, true);
            }
        }
        ImGui::EndCombo();
    }
    if (s.window_mode == BbSettings::Borderless) {
        Checkbox(Text("V-sync in borderless###borderless_vsync",
                      "V-sync без рамки###borderless_vsync"), s.borderless_vsync);
        Hint(Text("Off: Immediate presentation for minimum queueing; tearing is possible. "
                  "On: Mailbox if supported, otherwise FIFO. Driver and Windows settings affect latency.",
                  "Выкл: Immediate с минимальной очередью; возможны разрывы. "
                  "Вкл: Mailbox, если поддерживается, иначе FIFO. Задержка зависит от Windows и драйвера."));
    }

    ImGui::SeparatorText(Text("Temporal upscaler", "Временной апскейлер"));
    const char* upscalers[] = {
        Text("Off###upscaler_off", "Выкл###upscaler_off"),
        "FSR 3.1", "FSR 4 (INT8)", "FSR 4.1.1 (INT8)",
        Text("TAA (native anti-aliasing)###upscaler_taa",
             "TAA (нативное сглаживание)###upscaler_taa"),
        "DLSS (NVIDIA RTX)",
    };
    static const char* later[] = {"XeSS"};
    int upscaler = s.upscaler;
    if (ImGui::BeginCombo(Text("Upscaler###upscaler", "Апскейлер###upscaler"), upscalers[upscaler])) {
        for (int i = 0; i < BbSettings::UpscalerCount; ++i) {
            const bool supported = i == BbSettings::UpscalerFsr4 ? s.fsr4_supported.load()
                : i == BbSettings::UpscalerFsr411 ? s.fsr411_supported.load()
                : i == BbSettings::UpscalerDlss   ? s.dlss_supported.load() : true;
            ImGui::BeginDisabled(!supported);
            if (ImGui::Selectable(upscalers[i], i == upscaler)) {
                Store(s.upscaler, i, true);
            }
            ImGui::EndDisabled();
            if (!supported) {
                ImGui::SameLine();
                ImGui::TextDisabled("%s", Text("— not supported by this GPU",
                                         "— не поддерживается видеокартой"));
            }
        }
        for (const char* name : later) {
            ImGui::BeginDisabled();
            ImGui::Selectable(name, false);
            ImGui::EndDisabled();
            ImGui::SameLine();
            ImGui::TextDisabled("%s", Text("— in development", "— в работе"));
        }
        ImGui::EndCombo();
    }
    if (const char* problem = s.dlss_problem.load(); problem && upscaler == BbSettings::UpscalerDlss) {
        ImGui::TextColored(ImVec4(1.0f, 0.5f, 0.3f, 1.0f), "DLSS: %s", problem);
    }
    if (const char* problem = s.fsr4_problem.load()) {
        ImGui::PushTextWrapPos();
        ImGui::TextColored(ImVec4(1.0f, 0.5f, 0.3f, 1.0f), Text("FSR 4 unavailable: %s",
                                                                "FSR 4 недоступен: %s"), problem);
        if (!BbSettings::IsFsr4(s.upscaler))
            ImGui::TextUnformatted(Text("The mode selected above is active. You can select FSR 4 "
                                        "again.",
                                        "Активен режим, выбранный выше. FSR 4 можно выбрать "
                                        "снова."));
        ImGui::PopTextWrapPos();
    }
    if (BbSettings::IsFsr4(s.upscaler)) {
        if (s.upscaler == BbSettings::UpscalerFsr411) {
            Hint(Text("FSR 4.1.1 in INT8 mode: the model from the AMD 4.1.1 DLL, reproduced in "
                      "Vulkan (the output matches the DLL). One model for Native through "
                      "Performance, and a separate model for Ultra Performance. Assets: "
                      "tools/fsr4cap/build_assets.sh (requires the DLL and Proton).",
                      "FSR 4.1.1 в режиме INT8: модель из DLL AMD 4.1.1, воспроизведённая в "
                      "Vulkan (результат совпадает с DLL). Одна модель для Native..Performance и "
                      "отдельная для Ultra Performance. Ассеты: tools/fsr4cap/build_assets.sh "
                      "(нужны DLL и Proton)."));
        } else {
            Hint(Text("FSR 4 in INT8 mode (v07 model from the AMD FidelityFX SDK sources). Higher"
                      " quality than FSR 3.1, but the pass is more expensive. Changing the preset"
                      " rebuilds the model (a brief pause). Assets: tools/fetch_fsr4_assets.sh.",
                      "FSR 4 в режиме INT8 (модель v07 из исходников AMD FidelityFX SDK). "
                      "Качество выше, чем у FSR 3.1, но проход тяжелее. Смена пресета "
                      "пересобирает модель (короткая пауза). Ассеты: tools/fetch_fsr4_assets.sh."));
        }
        Checkbox(Text("FSR 4: auto exposure###fsr4_auto_exposure",
                      "FSR 4: авто-экспозиция###fsr4_auto_exposure"), s.fsr4_auto_exposure);
        Checkbox(Text("FSR 4: invert jitter sign###fsr4_invert_jitter",
                      "FSR 4: обратный знак jitter###fsr4_invert_jitter"), s.fsr4_invert_jitter);
        Hint(Text("Ghosting diagnostics: FSR 4 normalizes color using exposure and uses it to "
                  "decide when to reject previous frames. Changes take effect immediately, "
                  "without restarting.",
                  "Проверка при гостинге: сеть FSR 4 нормирует цвет по экспозиции и по ней "
                  "решает, когда отбросить прошлые кадры. Меняются сразу, без перезапуска."));
    }
    const bool upscaler_on = s.upscaler != BbSettings::UpscalerOff;
    const char* frame_generators[]={Text("Off###fg_off","Выключено###fg_off"),"FSR Frame Generation (2x)","NVIDIA DLSS Frame Generation / MFG"};
    const int fg=std::clamp(s.frame_generation.load(),0,2);
    if (ImGui::BeginCombo(Text("Frame Generation###frame_generation","Генерация кадров###frame_generation"),frame_generators[fg])) {
        for (int i=0;i<3;++i) {
            ImGui::BeginDisabled(i!=0 && (!upscaler_on || (i==2 && !s.nvidia_fg_supported)));
            if (ImGui::Selectable(frame_generators[i],fg==i)) Store(s.frame_generation,i,true);
            ImGui::EndDisabled();
        }
        ImGui::EndCombo();
    }
    if (s.frame_generation==BbSettings::FrameGenerationNvidia) {
        const int selected=s.nvidia_generated_frames;
        const std::string preview=std::to_string(selected+1)+"x";
        if (ImGui::BeginCombo(Text("NVIDIA FG multiplier###nvidia_generated_frames","Множитель NVIDIA FG###nvidia_generated_frames"),preview.c_str())) {
            for (int i=1;i<=5;++i) {
                ImGui::BeginDisabled(i>s.nvidia_max_generated);
                const std::string name=std::to_string(i+1)+"x";
                if (ImGui::Selectable(name.c_str(),i==selected)) Store(s.nvidia_generated_frames,i,true);
                ImGui::EndDisabled();
            }
            ImGui::EndCombo();
        }
        if (const char* problem=s.frame_generation_problem.load()) ImGui::TextWrapped("%s",problem);
        else if (s.frame_generation_active>1) ImGui::Text(Text("NVIDIA FG active: %dx","NVIDIA FG активна: %dx"),s.frame_generation_active.load());
        else ImGui::TextUnformatted(Text("NVIDIA FG: waiting for valid scene frames","NVIDIA FG: ожидание кадров сцены"));
    }
    const char* reflex_modes[]={Text("Off","Выключено"),Text("On","Включено"),"On + Boost"};
    const int reflex=std::clamp(s.reflex.load(),0,2);
    ImGui::BeginDisabled(!s.reflex_supported);
    if (ImGui::BeginCombo("NVIDIA Reflex###reflex",reflex_modes[reflex])) {
        for(int i=0;i<3;++i) if(ImGui::Selectable(reflex_modes[i],i==reflex)) Store(s.reflex,i,true);
        ImGui::EndCombo();
    }
    ImGui::EndDisabled();
    Hint(Text("Reflex works independently of NVIDIA FG. NVIDIA FG enables Reflex automatically; Boost is optional. Unsupported choices are disabled.",
              "Reflex работает независимо от NVIDIA FG. Генерация NVIDIA включает Reflex автоматически; Boost необязателен. Неподдерживаемые настройки недоступны."));
    Hint(Text("FSR FG adds one interpolated frame between real frames, in SDR or HDR10. The normal FPS limit counts real frames: 75 can produce 150 with FG 2x. Background FPS caps disable generation.",
              "FSR FG добавляет промежуточный кадр в SDR или HDR10. Обычный лимит относится к реальным кадрам: 75 даёт до 150 с FG 2x. При лимите FPS в фоне генерация отключается."));
    Checkbox(Text("Limit total FPS with Frame Generation###limit_generated_fps",
                  "Лимит общих FPS с генерацией кадров###limit_generated_fps"),s.limit_generated_fps);
    ImGui::BeginDisabled(!s.limit_generated_fps);
    int generated_limit=s.generated_fps_limit;
    if (ImGui::SliderInt(Text("Total FPS cap###generated_fps_limit","Общий лимит FPS###generated_fps_limit"),
                         &generated_limit,30,1000,"%d FPS")) Store(s.generated_fps_limit,generated_limit,true);
    ImGui::EndDisabled();
    Hint(Text("Optional. This cap includes generated frames and can reduce the real frame rate. Generated frames do not advance game logic or physics.",
              "Этот необязательный лимит включает промежуточные кадры и может снизить реальные FPS. Генерация не меняет физику и логику игры."));
    if (s.frame_generation==BbSettings::FrameGenerationFsr) {
        if (const char* problem=s.frame_generation_problem.load()) ImGui::TextWrapped("%s",problem);
        else ImGui::TextUnformatted(s.frame_generation_active==2 ? Text("FSR FG active: 2x","FSR FG активна: 2x") :
                                  Text("FSR FG: waiting for valid scene frames","FSR FG: ожидание кадров сцены"));
    }
    const bool taa = s.upscaler == BbSettings::UpscalerTaa;
    if (s.upscaler == BbSettings::UpscalerDlss) {
        const int selected = s.dlss_preset.load();
        if (ImGui::BeginCombo(Text("DLSS render preset###dlss_preset", "Пресет модели DLSS###dlss_preset"),
                              BbSettings::DlssPresetName(selected))) {
            for (int value : BbSettings::DlssPresetValues) {
                if (ImGui::Selectable(BbSettings::DlssPresetName(value), value == selected)) {
                    Store(s.dlss_preset, value, true);
                }
            }
            ImGui::EndCombo();
        }
        Hint(Text("DLSS model hint, separate from Quality/Balanced/Performance render scaling. "
                  "Changes recreate the DLSS feature on the next frame, without restarting. "
                  "E/F are legacy. Driver/profile overrides may supersede the requested hint.",
                  "Модель DLSS, отдельно от масштаба Quality/Balanced/Performance. "
                  "Применяется на следующем кадре, без перезапуска. E/F — устаревшие. "
                  "Драйвер или профиль может переопределить запрос."));
    }
    ImGui::BeginDisabled(!upscaler_on);
    ImGui::BeginDisabled(taa);
    int preset = taa ? BbSettings::NativeAA : s.preset.load();
    char preset_label[64];
    std::snprintf(preset_label, sizeof(preset_label), "%s (x%.1f)", BbSettings::PresetName(preset),
                  BbSettings::PresetScale(preset));
    if (ImGui::BeginCombo(Text("Quality preset###preset", "Пресет качества###preset"), preset_label)) {
        for (int i = 0; i < BbSettings::PresetCount; ++i) {
            char label[96];
            const float scale = BbSettings::PresetScale(i);
            const int output = s.output_res;
            std::snprintf(label, sizeof(label), Text("%s (x%.1f, render %dx%d)###preset_%d",
                                                   "%s (x%.1f, рендер %dx%d)###preset_%d"),
                          BbSettings::PresetName(i), scale,
                          int(std::lround(BbSettings::OutputWidths[output] / scale / 2) * 2),
                          int(std::lround(BbSettings::OutputHeights[output] / scale / 2) * 2), i);
            if (ImGui::Selectable(label, i == preset)) {
                Store(s.preset, i, true);
            }
        }
        ImGui::EndCombo();
    }
    ImGui::EndDisabled();
    if (taa) {
        ImGui::TextWrapped("%s", Text("TAA applies anti-aliasing at the output resolution, without an "
                                "FSR model or upscaling. Your saved FSR preset is restored when "
                                "you select FSR.",
                                "TAA сглаживает сцену в разрешении вывода, без модели FSR и "
                                "апскейлинга. Сохранённый пресет FSR восстановится при выборе "
                                "FSR."));
    }
    ImGui::Text(Text("Active scene render resolution: %d x %d", "Активный рендер сцены: %d x %d"), s.active_render_width.load(),
                s.active_render_height.load());
    ImGui::Text(Text("Active output resolution: %d x %d", "Активное разрешение вывода: %d x %d"),
                s.active_output_width.load(), s.active_output_height.load());
    if (BbSettings::FixedRenderSession()) {
        ImGui::Text(Text("Startup preset: %s", "Пресет при запуске: %s"), BbSettings::PresetName(s.startup_preset));
        if (const char* automatic = std::getenv("BB_AUTO_RENDER_RES");
            automatic && automatic[0] == '1') {
            Hint(Text("At output resolutions other than 1080p, the entire game renders at the "
                      "preset resolution (a startup patch): this is the fastest mode on Steam "
                      "Deck and less powerful GPUs. Preset or output resolution changes require a"
                      " restart. The Live resolution changes option below allows changes without "
                      "restarting (post-processing then stays at 1080p, which is slower).",
                      "При выводе не 1080p вся игра рисуется в разрешении пресета (патч при "
                      "запуске): это быстрее всего на Steam Deck и слабых GPU. Смена пресета или "
                      "разрешения вывода — после перезапуска. Пункт «Смена разрешения на лету» "
                      "ниже включает смену без перезапуска (постобработка тогда остаётся в 1080p,"
                      " медленнее)."));
        } else {
            Hint(Text("BB_RENDER_RES fixes the scene size at startup. Remove this explicit "
                      "environment variable to change the resolution and presets without "
                      "restarting the game.",
                      "BB_RENDER_RES фиксирует размер сцены при запуске. Уберите эту явную "
                      "переменную для смены разрешения и пресетов без перезапуска игры."));
        }
    } else {
        Hint(Text("Native AA: FSR acts as anti-aliasing. Other presets reduce the scene render "
                  "resolution relative to the output. The UI renders at the output resolution. "
                  "The preset takes effect on the next frame without restarting the game.",
                  "Native AA: FSR работает как сглаживание. Остальные пресеты уменьшают "
                  "разрешение отрисовки сцены относительно вывода. Интерфейс рисуется в "
                  "разрешении вывода. Пресет применяется со следующего кадра без перезапуска "
                  "игры."));
    }
    Checkbox(Text("Sharpening (RCAS)###sharpen", "Резкость (RCAS)###sharpen"), s.sharpen);
    ImGui::BeginDisabled(!s.sharpen);
    Slider(Text("Sharpness###sharpness", "Сила резкости###sharpness"), s.sharpness, 0.0f, 2.0f);
    Hint(Text("Up to 1: the upscaler's own sharpening (RCAS). Above 1: adds another RCAS pass. "
              "Ctrl+click the slider to enter an exact value.",
              "До 1 — резкость самого апскейлера (RCAS). Выше 1 добавляется ещё один проход RCAS."
              " Ctrl+клик по ползунку — ввести точное значение."));
    ImGui::EndDisabled();
    Checkbox(Text("Subpixel jitter###jitter", "Субпиксельный сдвиг (jitter)###jitter"), s.jitter);
    Hint(Text("Each frame shifts the scene by a fraction of a pixel, letting the upscaler combine"
              " several frames to recover more detail. Without jitter, only history-based "
              "smoothing remains.",
              "Каждый кадр сцена сдвигается на долю пикселя, и апскейлер собирает из нескольких "
              "кадров больше деталей. Без него получается только сглаживание по истории."));

    ImGui::SeparatorText(Text("Reactive mask", "Маска реактивности"));
    ImGui::BeginDisabled(taa);
    Checkbox(Text("Enable mask###reactive", "Включить маску###reactive"), s.reactive);
    Hint(Text("Marks transparent effects (particles, haze) so the upscaler relies less on "
              "previous frames. Reduces trails behind effects, but brings back shimmering beneath"
              " them.",
              "Помечает прозрачные эффекты (частицы, дымку), чтобы апскейлер меньше опирался на "
              "прошлые кадры. Меньше шлейфов за эффектами, но под ними возвращается дрожание."));
    ImGui::BeginDisabled(!s.reactive);
    Slider(Text("Scale###reactive_scale", "Масштаб###reactive_scale"), s.reactive_scale, 0.0f, 4.0f);
    Slider(Text("Threshold###reactive_threshold", "Порог###reactive_threshold"), s.reactive_threshold, 0.0f, 1.0f);
    Slider(Text("Maximum###reactive_max", "Максимум###reactive_max"), s.reactive_max, 0.0f, 1.0f);
    bool show_mask = s.debug_view == BbSettings::DebugReactive;
    if (ImGui::Checkbox(Text("Show mask (debug)###show_reactive",
                             "Показать маску (отладка)###show_reactive"), &show_mask)) {
        s.debug_view = show_mask ? BbSettings::DebugReactive : BbSettings::DebugNone;
    }
    ImGui::EndDisabled();
    ImGui::EndDisabled();
    Checkbox(Text("Character motion vectors###object_motion",
                  "Векторы движения персонажей###object_motion"), s.object_motion);
    Hint(Text("Accurate vectors for animated objects: clothing and weapons break up less during "
              "motion. Static scenes do not receive an extra pass. Changes take effect after "
              "restarting the game.",
              "Точные векторы для анимированных объектов: одежда и оружие меньше рассыпаются при "
              "движении. Статичная сцена не получает дополнительный проход. Изменение применяется"
              " после перезапуска игры."));
    bool show_motion = s.debug_view == BbSettings::DebugMotion;
    if (ImGui::Checkbox(Text("Show motion vectors (debug)###show_motion",
                             "Показать векторы движения (отладка)###show_motion"), &show_motion)) {
        s.debug_view = show_motion ? BbSettings::DebugMotion : BbSettings::DebugNone;
    }
    Hint(Text("Red/green: horizontal/vertical motion (8 pixels = full brightness). Blue: the "
              "pixel has an accurate object vector, rather than only camera motion. A moving "
              "object with no blue and no red/green is treated as stationary by the upscaler, "
              "causing trails.",
              "Красный/зелёный: движение по горизонтали/вертикали (8 пикселей = полная яркость). "
              "Синий: пиксель получил точный вектор объекта, а не только движение камеры. "
              "Движущийся предмет без синего и без красного/зелёного апскейлер считает "
              "неподвижным, отсюда шлейф."));
    ImGui::EndDisabled(); // upscaler off

    ImGui::SeparatorText(Text("Output resolution", "Разрешение вывода"));
    static const char* outputs[] = {"1280 x 720", "1920 x 1080", "2560 x 1440", "3840 x 2160"};
    int output = s.output_res;
    if (ImGui::BeginCombo(Text("Output resolution###output_res", "Разрешение вывода###output_res"), outputs[output])) {
        for (int i = 0; i < BbSettings::OutputCount; ++i) {
            if (ImGui::Selectable(outputs[i], i == output)) {
                Store(s.output_res, i, true);
            }
        }
        ImGui::EndCombo();
    }
    if (BbSettings::FixedRenderSession()) {
        Hint(Text("Final frame and UI size. The preset sets the scene size relative to the "
                  "output: 4K Performance = 1920x1080. Changes take effect after restarting the "
                  "game.",
                  "Размер готового кадра и интерфейса. Пресет задаёт размер сцены относительно "
                  "вывода: 4K Performance = 1920x1080. Применяется после перезапуска игры."));
    } else {
        Hint(Text("The final frame and UI size change at the next frame boundary. The preset sets"
                  " the scene size relative to the output: 4K Performance = 1920x1080. Resizing "
                  "resets FSR history and may cause a brief pause.",
                  "Размер готового кадра и интерфейса меняется на границе следующего кадра. "
                  "Пресет задаёт размер сцены относительно вывода: 4K Performance = 1920x1080. "
                  "Смена размера сбрасывает историю FSR и может вызвать короткую паузу."));
    }
    const char* live_modes[] = {
        Text("Auto (based on GPU)###live_auto", "Авто (по видеокарте)###live_auto"),
        Text("Off (faster)###live_off", "Выключена (быстрее)###live_off"),
        Text("On###live_on", "Включена###live_on"),
    };
    int live = s.live_resolution + 1;
    if (ImGui::BeginCombo(Text("Live resolution changes###live_resolution",
                               "Смена разрешения на лету###live_resolution"), live_modes[live])) {
        for (int i = 0; i < 3; ++i) {
            if (ImGui::Selectable(live_modes[i], i == live)) {
                Store(s.live_resolution, i - 1, true);
            }
        }
        ImGui::EndCombo();
    }
    Hint(Text("On: the output resolution and preset change without restarting, but game "
              "post-processing stays at 1080p, which is noticeably slower on Steam Deck and older"
              " GPUs. Off: everything renders at the preset resolution, and changes require a "
              "restart. Auto enables this on powerful discrete GPUs. Changes take effect after "
              "restarting the game.",
              "Включена: разрешение вывода и пресет меняются без перезапуска, но постобработка "
              "игры остаётся в 1080p — на Steam Deck и старых видеокартах это заметно медленнее. "
              "Выключена: всё рисуется в разрешении пресета, смена — через перезапуск. Авто "
              "включает её на мощных дискретных видеокартах. Применяется после перезапуска игры."));
    ImGui::SeparatorText(Text("Cheats", "Читы"));
    const auto multiplier = [&](const char* label, std::atomic<int>& target,
                                uint32_t feature, bool motion = false) {
        const char* const* labels = motion ? BbSettings::MovementMultipliers : BbSettings::CheatMultipliers;
        const int count = motion ? 6 : 5;
        const int current = std::clamp(target.load(), 0, count - 1);
        ImGui::BeginDisabled(!(s.cheat_supported.load() & feature));
        if (ImGui::BeginCombo(label, current ? labels[current] : Text("Off", "Выключено"))) {
            for (int i = 0; i < count; ++i) {
                if (ImGui::Selectable(i ? labels[i] : Text("Off", "Выключено"), current == i))
                    Store(target, i, true);
            }
            ImGui::EndCombo();
        }
        ImGui::EndDisabled();
    };
    multiplier(Text("Player damage###cheat_damage", "Урон игрока###cheat_damage"), s.cheat_damage, 1u);
    multiplier(Text("Reduce enemy damage###cheat_incoming", "Снизить урон врагов###cheat_incoming"), s.cheat_incoming, 2u);
    Hint(Text("x2 halves damage received from an enemy; x16 divides it by 16. Defense stats stay the same.",
              "x2 делит полученный от врага урон на 2; x16 — на 16. Характеристики защиты не меняются."));
    multiplier(Text("Blood Echoes gained###cheat_echoes", "Полученные эхо крови###cheat_echoes"), s.cheat_echoes, 4u);
    multiplier(Text("Movement speed###cheat_movement", "Скорость движения###cheat_movement"), s.cheat_movement, 8u, true);
    ImGui::BeginDisabled(!(s.cheat_supported.load() & 16u));
    Checkbox(Text("Infinite stamina###cheat_infinite_stamina", "Бесконечная выносливость###cheat_infinite_stamina"), s.cheat_infinite_stamina);
    ImGui::EndDisabled();
    ImGui::BeginDisabled(!(s.cheat_supported.load() & 32u));
    Checkbox(Text("Consumables are not reduced on use###cheat_no_consume",
                  "Расходники не тратятся при использовании###cheat_no_consume"), s.cheat_no_consume);
    ImGui::EndDisabled();
    Hint(Text("Includes ammunition. You still need to own the item; selling, dropping and buying keep their normal behavior.",
              "Включая боеприпасы. Предмет должен быть в инвентаре; продажа, выбрасывание и покупка работают как обычно."));
    if (s.cheat_supported.load() != 63u)
        ImGui::TextWrapped("%s", Text("Some live cheats are unavailable for this executable or conflict with a patch. See last_run.log.",
                                     "Часть читов недоступна для этого исполняемого файла или конфликтует с патчем. См. last_run.log."));
    for (int e=0;e<BbSettings::EffectCount;++e) {
        const auto& effect=BbSettings::Effects[e];
        if (std::string_view(effect.key).starts_with("cheat_")) {
            const std::string label=std::string(Text(effect.label_en,effect.label))+
                Text(" (restart required)###"," (после перезапуска)###")+effect.key;
            Checkbox(label.c_str(),s.effects[e]);
        }
    }
    ImGui::SeparatorText(Text("Game effects (restart required)", "Эффекты игры (после перезапуска)"));
    const char* lods[] = {
        Text("Highest (-2)###lod_highest", "Максимальная (-2)###lod_highest"),
        Text("Game default###lod_default", "Как в игре###lod_default"),
        Text("Lower (1)###lod_lower", "Ниже (1)###lod_lower"),
        Text("Lowest (2)###lod_lowest", "Минимальная (2)###lod_lowest"),
    };
    static constexpr int lod_values[] = {-2, 0, 1, 2};
    int lod_index = 1;
    for (int i = 0; i < 4; ++i) {
        if (lod_values[i] == s.model_lod) lod_index = i;
    }
    if (ImGui::BeginCombo(Text("Model detail###model_lod", "Детализация моделей###model_lod"), lods[lod_index])) {
        for (int i = 0; i < 4; ++i) {
            if (ImGui::Selectable(lods[i], i == lod_index)) {
                Store(s.model_lod, lod_values[i], true);
            }
        }
        ImGui::EndCombo();
    }
    for (int e = 0; e < BbSettings::EffectCount; ++e) {
        const auto& effect = BbSettings::Effects[e];
        if (std::string_view(effect.key).starts_with("cheat_")) continue;
        const std::string label = std::string(Text(effect.label_en, effect.label)) + "###" + effect.key;
        Checkbox(label.c_str(), s.effects[e]);
    }
    Hint(Text("Effects are enabled and disabled by game patches at startup "
              "(patches/Bloodborne.xml). Motion blur and dynamic light shadows have a noticeable "
              "GPU cost.",
              "Эффекты включаются и выключаются патчами игры при запуске "
              "(patches/Bloodborne.xml). Размытие в движении и тени от динамических источников "
              "заметно нагружают GPU."));
    Hint(Text("Free camera: hold Cross and press L3 (keyboard: Space + Z). Debug menu: left "
              "touchpad / Tab. Requires DbgFont14h.ccm and DbgFont14h.tpf in dvdroot_ps4/font "
              "from Nexus mod #253. Right touchpad: Backspace.",
              "Свободная камера: удерживайте Cross и нажимайте L3 (клавиатура: Space + Z). Debug "
              "menu: левый touchpad / Tab. Нужны DbgFont14h.ccm и DbgFont14h.tpf в "
              "dvdroot_ps4/font из мода Nexus #253. Правый touchpad: Backspace."));

    bool restart = s.object_motion != s.startup_object_motion ||
                   s.model_lod != s.startup_model_lod ||
                   s.live_resolution != s.startup_live_resolution ||
                   BbSettings::ResolutionNeedsRestart();
    for (int e = 0; e < BbSettings::EffectCount; ++e) {
        restart |= s.effects[e] != s.startup_effects[e];
    }
    if (restart) {
        ImGui::TextColored(ImVec4(1.0f, 0.75f, 0.3f, 1.0f),
                           "%s", Text("Changes take effect after restarting the game",
                                "Изменения применятся после перезапуска игры"));
        if (ImGui::Button(Text("Apply and restart game###restart",
                               "Применить и перезапустить игру###restart"))) {
            BbSettings::Save();
            runtime_restart();
        }
    }

    ImGui::Spacing();
    if (ImGui::Button(Text("Close###close", "Закрыть###close"))) {
        keep_open = false;
    }
    ImGui::SameLine();
    ImGui::TextDisabled("%s", Text("Settings are saved automatically",
                                 "Настройки сохраняются автоматически"));
    ImGui::End();
    if (!keep_open) {
        SetOpen(false);
    }
}

// The game's text dialog: what is typed, and how to finish (keyboard or controller).
void TextEntryBox() {
    const ImGuiViewport* viewport = ImGui::GetMainViewport();
    ImGui::SetNextWindowPos(ImVec2(viewport->WorkPos.x + viewport->WorkSize.x * 0.5f,
                                   viewport->WorkPos.y + viewport->WorkSize.y * 0.42f),
                            ImGuiCond_Always, ImVec2(0.5f, 0.5f));
    ImGui::SetNextWindowSizeConstraints(ImVec2(viewport->WorkSize.x * 0.32f, 0.0f),
                                        ImVec2(viewport->WorkSize.x * 0.8f, FLT_MAX));
    ImGui::SetNextWindowBgAlpha(0.92f);
    ImGui::Begin("##text_entry", nullptr,
                 ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_AlwaysAutoResize |
                     ImGuiWindowFlags_NoInputs | ImGuiWindowFlags_NoNav |
                     ImGuiWindowFlags_NoFocusOnAppearing);
    ImGui::TextColored(ImVec4(0.85f, 0.72f, 0.45f, 1.0f), "%s", text_entry_prompt.c_str());
    ImGui::Separator();
    ImGui::SetWindowFontScale(1.4f);
    ImGui::Text("%s_", text_entry_text.c_str());
    ImGui::SetWindowFontScale(1.0f);
    ImGui::Separator();
    ImGui::TextDisabled("Keyboard: type, Backspace to erase, Enter = OK, Esc = cancel");
    ImGui::TextDisabled("Controller: Cross (A) = OK, Circle (B) = cancel");
    ImGui::End();
}

void FpsCounter() {
    const auto& s = BbSettings::Get();
    if (!s.show_fps) return;
    const ImGuiViewport* viewport = ImGui::GetMainViewport();
    const float pad = 12.0f * base_scale;
    ImGui::SetNextWindowPos(ImVec2(viewport->WorkPos.x + viewport->WorkSize.x - pad,
                                   viewport->WorkPos.y + pad),
                            ImGuiCond_Always, ImVec2(1.0f, 0.0f));
    ImGui::SetNextWindowBgAlpha(0.5f);
    ImGui::Begin("##fps", nullptr,
                 ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_AlwaysAutoResize |
                     ImGuiWindowFlags_NoInputs | ImGuiWindowFlags_NoNav |
                     ImGuiWindowFlags_NoFocusOnAppearing);
    const char* upscaler = s.upscaler == BbSettings::UpscalerFsr3   ? "FSR 3.1"
                : s.upscaler == BbSettings::UpscalerFsr4 ? "FSR 4"
                : s.upscaler == BbSettings::UpscalerFsr411 ? "FSR 4.1.1"
                : s.upscaler == BbSettings::UpscalerTaa ? "TAA"
                : s.upscaler == BbSettings::UpscalerDlss ? "DLSS"
                                                         : "";
    char dlss_label[48];
    if (s.upscaler == BbSettings::UpscalerDlss && s.show_dlss_preset) {
        const int active = s.dlss_active_preset.load();
        const int selected = s.dlss_preset.load();
        if (active == selected) {
            std::snprintf(dlss_label, sizeof(dlss_label), "DLSS (%s)",
                          BbSettings::DlssPresetShortName(active));
        } else {
            std::snprintf(dlss_label, sizeof(dlss_label), "DLSS (%s>%s)",
                          BbSettings::DlssPresetShortName(active),
                          BbSettings::DlssPresetShortName(selected));
        }
        upscaler = dlss_label;
    }
    char line[192];
    const float fps = frame_ms_avg > 0.0f ? 1000.0f / frame_ms_avg : 0.0f;
    if (s.show_resolution) {
        std::snprintf(line, sizeof(line), "%.0ffps %.1fms %s  %dx%d>%dx%d", fps, frame_ms_avg, upscaler,
                      s.active_render_width.load(), s.active_render_height.load(),
                      s.active_output_width.load(), s.active_output_height.load());
        // Keep one row and the original height. Fit extra details within a modest width,
        // retaining at least 85% of the normal font size even at a small viewport.
        const float limit = std::min(420.0f * base_scale, viewport->WorkSize.x - pad * 2.0f);
        const float natural = ImGui::CalcTextSize(line).x;
        ImGui::SetWindowFontScale(std::clamp((limit - ImGui::GetStyle().WindowPadding.x * 2.0f) /
                                              std::max(natural, 1.0f), 0.85f, 1.0f));
    } else {
        std::snprintf(line, sizeof(line), Text("%.0f FPS  %.1f ms  %s", "%.0f FPS  %.1f мс  %s"),
                      fps, frame_ms_avg, upscaler);
    }
    ImGui::TextUnformatted(line);
    ImGui::SetWindowFontScale(1.0f);
    ImGui::End();
}

} // namespace

void SavePendingSettings() {
    std::scoped_lock lock{imgui_mutex};
    if (dirty) {
        BbSettings::Save();
        dirty = false;
    }
}

void Init(const Vulkan::Instance& instance, vk::Format format, u32 image_count) {
    std::scoped_lock lock{imgui_mutex};
    if (initialized) {
        return;
    }
    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGuiIO& io = ImGui::GetIO();
    io.IniFilename = nullptr; // window positions are not kept
    io.ConfigFlags |= ImGuiConfigFlags_NavEnableKeyboard | ImGuiConfigFlags_NavEnableGamepad;
    io.BackendFlags |= ImGuiBackendFlags_HasGamepad;
    io.BackendPlatformName = "bbport";

    ImGui::StyleColorsDark();
    ImGuiStyle& style = ImGui::GetStyle();
    style.WindowRounding = 6.0f;
    style.FrameRounding = 4.0f;
    style.GrabRounding = 4.0f;
    style.Colors[ImGuiCol_WindowBg].w = 0.92f;

    ImFontConfig font_config;
    font_config.FontDataOwnedByAtlas = false;
    io.Fonts->AddFontFromMemoryTTF(const_cast<unsigned char*>(bb_font_ttf),
                                   int(bb_font_ttf_end - bb_font_ttf), 18.0f, &font_config);

    const vk::Instance vk_instance = instance.GetInstance();
    ImGui_ImplVulkan_LoadFunctions(
        instance.ApiVersion(),
        [](const char* name, void* user) {
            return VULKAN_HPP_DEFAULT_DISPATCHER.vkGetInstanceProcAddr(
                *static_cast<const vk::Instance*>(user), name);
        },
        const_cast<vk::Instance*>(&vk_instance));

    const VkFormat color_format = static_cast<VkFormat>(format);
    ImGui_ImplVulkan_InitInfo info{};
    info.ApiVersion = instance.ApiVersion();
    info.Instance = vk_instance;
    info.PhysicalDevice = instance.GetPhysicalDevice();
    info.Device = instance.GetDevice();
    info.QueueFamily = instance.GetGraphicsQueueFamilyIndex();
    info.Queue = instance.GetGraphicsQueue();
    info.DescriptorPoolSize = 16;
    info.MinImageCount = std::max(image_count, 2u);
    info.ImageCount = std::max(image_count, 2u);
    info.UseDynamicRendering = true;
    info.PipelineInfoMain.PipelineRenderingCreateInfo = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_RENDERING_CREATE_INFO_KHR,
        .colorAttachmentCount = 1,
        .pColorAttachmentFormats = &color_format,
    };
    if (!ImGui_ImplVulkan_Init(&info)) {
        std::printf("Overlay: ImGui Vulkan backend init failed\n");
        ImGui::DestroyContext();
        return;
    }
    initialized = true;
    std::printf("Overlay: menu ready (Insert or L3+R3)\n");
}

void UpdateTextInput(SDL_Window* window) {
    bool want = false;
    {
        std::scoped_lock lock{imgui_mutex};
        want = initialized && menu_open && ImGui::GetIO().WantTextInput;
    }
    if (want != SDL_TextInputActive(window)) {
        if (want) {
            SDL_StartTextInput(window);
        } else {
            SDL_StopTextInput(window);
        }
    }
}

bool HandleEvent(const SDL_Event& event) {
    std::scoped_lock lock{imgui_mutex};
    if (!initialized) {
        return false;
    }
    ImGuiIO& io = ImGui::GetIO();
    const bool is_open = menu_open;
    switch (event.type) {
    case SDL_EVENT_WINDOW_FOCUS_GAINED:
    case SDL_EVENT_WINDOW_FOCUS_LOST:
        io.AddFocusEvent(event.type == SDL_EVENT_WINDOW_FOCUS_GAINED);
        if (event.type == SDL_EVENT_WINDOW_FOCUS_LOST) l3_down = r3_down = false;
        return false; // WindowSDL also updates the background frame-cap policy.
    case SDL_EVENT_KEY_DOWN:
    case SDL_EVENT_KEY_UP: {
        const bool down = event.type == SDL_EVENT_KEY_DOWN;
        if (down && !event.key.repeat &&
            (event.key.key == SDLK_INSERT || (is_open && event.key.key == SDLK_ESCAPE))) {
            SetOpen(event.key.key == SDLK_INSERT ? !is_open : false);
            return true;
        }
        if (!is_open) {
            return false;
        }
        io.AddKeyEvent(ImGuiMod_Ctrl, (event.key.mod & SDL_KMOD_CTRL) != 0);
        io.AddKeyEvent(ImGuiMod_Shift, (event.key.mod & SDL_KMOD_SHIFT) != 0);
        io.AddKeyEvent(ImGuiMod_Alt, (event.key.mod & SDL_KMOD_ALT) != 0);
        if (const ImGuiKey key = KeyFromSdl(event.key.key); key != ImGuiKey_None) {
            io.AddKeyEvent(key, down);
        }
        return true;
    }
    case SDL_EVENT_GAMEPAD_BUTTON_DOWN:
    case SDL_EVENT_GAMEPAD_BUTTON_UP: {
        const bool down = event.type == SDL_EVENT_GAMEPAD_BUTTON_DOWN;
        const u8 button = event.gbutton.button;
        if (button == SDL_GAMEPAD_BUTTON_LEFT_STICK) {
            l3_down = down;
        } else if (button == SDL_GAMEPAD_BUTTON_RIGHT_STICK) {
            r3_down = down;
        }
        if (down && l3_down && r3_down) {
            SetOpen(!is_open);
            return true;
        }
        if (!is_open) {
            return false;
        }
        if (const ImGuiKey key = KeyFromGamepad(button); key != ImGuiKey_None) {
            io.AddKeyEvent(key, down);
        }
        return true;
    }
    case SDL_EVENT_TEXT_INPUT: {
        // Typed characters (Ctrl+click on a slider, a text field): key events alone erase but
        // do not type. SDL sends them while text input is on (UpdateTextInput).
        if (!is_open) {
            return false;
        }
        io.AddInputCharactersUTF8(event.text.text);
        return true;
    }
    case SDL_EVENT_MOUSE_MOTION: {
        if (!is_open) {
            return false;
        }
        const float density = PixelDensity(event.motion.windowID);
        io.AddMousePosEvent(event.motion.x * density, event.motion.y * density);
        return true;
    }
    case SDL_EVENT_MOUSE_BUTTON_DOWN:
    case SDL_EVENT_MOUSE_BUTTON_UP: {
        if (!is_open) {
            return false;
        }
        const int button = event.button.button == SDL_BUTTON_LEFT    ? 0
                           : event.button.button == SDL_BUTTON_RIGHT  ? 1
                           : event.button.button == SDL_BUTTON_MIDDLE ? 2
                                                                      : -1;
        if (button >= 0) {
            const float density = PixelDensity(event.button.windowID);
            io.AddMousePosEvent(event.button.x * density, event.button.y * density);
            io.AddMouseButtonEvent(button, event.type == SDL_EVENT_MOUSE_BUTTON_DOWN);
        }
        return true;
    }
    case SDL_EVENT_MOUSE_WHEEL:
        if (!is_open) {
            return false;
        }
        io.AddMouseWheelEvent(event.wheel.x, event.wheel.y);
        return true;
    default:
        return false;
    }
}

bool Visible() {
    return initialized && (menu_open || text_entry_active || BbSettings::Get().show_fps);
}

bool CapturesInput() {
    return menu_open || text_entry_active;
}

void SetTextEntry(bool active, const std::string& prompt, const std::string& text) {
    std::scoped_lock lock{imgui_mutex};
    text_entry_active = active;
    text_entry_prompt = prompt;
    text_entry_text = text;
}

void Render(vk::CommandBuffer cmdbuf, vk::ImageView view, vk::Extent2D extent) {
    // Present interval for the FPS readout (measured also while nothing is drawn).
    const auto now = std::chrono::steady_clock::now();
    const float ms = std::chrono::duration<float, std::milli>(now - last_present).count();
    last_present = now;
    if (ms > 0.0f && ms < 1000.0f) {
        frame_ms_avg = frame_ms_avg == 0.0f ? ms : frame_ms_avg * 0.95f + ms * 0.05f;
    }
    if (!Visible()) {
        return;
    }
    std::scoped_lock lock{imgui_mutex};
    ImGuiIO& io = ImGui::GetIO();
    io.DisplaySize = ImVec2(float(extent.width), float(extent.height));
    io.DeltaTime = ms > 0.0f && ms < 1000.0f ? ms / 1000.0f : 1.0f / 60.0f;
    // UI scale follows the display height (1080p = 1).
    const float scale = std::max(float(extent.height) / 1080.0f, 0.75f);
    if (std::abs(scale - base_scale) > 0.01f) {
        ImGuiStyle& style = ImGui::GetStyle();
        style.ScaleAllSizes(scale / base_scale);
        style.FontScaleMain = scale;
        base_scale = scale;
    }

    ImGui_ImplVulkan_NewFrame();
    ImGui::NewFrame();
    if (menu_open) {
        Menu();
    }
    if (BbSettings::Get().show_fps && !menu_open) {
        FpsCounter();
    }
    if (text_entry_active) {
        TextEntryBox();
    }
    ImGui::Render();

    const vk::RenderingAttachmentInfo attachment{
        .imageView = view,
        .imageLayout = vk::ImageLayout::eColorAttachmentOptimal,
        .loadOp = vk::AttachmentLoadOp::eLoad,
        .storeOp = vk::AttachmentStoreOp::eStore,
    };
    cmdbuf.beginRendering(vk::RenderingInfo{
        .renderArea = {{0, 0}, extent},
        .layerCount = 1,
        .colorAttachmentCount = 1,
        .pColorAttachments = &attachment,
    });
    {
        // Font atlas uploads submit to the graphics queue themselves.
        std::scoped_lock submit_lock{Vulkan::Scheduler::submit_mutex};
        ImGui_ImplVulkan_RenderDrawData(ImGui::GetDrawData(), cmdbuf);
    }
    cmdbuf.endRendering();
}

} // namespace BbOverlay
