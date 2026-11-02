// SPDX-License-Identifier: GPL-2.0-or-later
#include "bbport_hitch.h"
#include "bbport_overlay.h"
#include "bbport_nvidia_preset.h"

#include <algorithm>
#include <array>
#include <atomic>
#include <cfloat>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <string>
#include <type_traits>

#ifdef _WIN32
#include <windows.h>
#include <pdh.h>
#include <pdhmsg.h>
#include <cwchar>
#include <thread>
#include <vector>
#endif

#include <SDL3/SDL.h>
#include "bbport_process_memory.h"
#include "bbport_settings.h"
#include "bbport_frametime.h"
#include "../bbcheats.h"
#include "bbport_fsr41_ui.h"
#include <filesystem>
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
bool l3_down = false, r3_down = false, back_down = false, start_down = false;

// What opens the menu (the launcher's Controls page): BB_MENU_KEY, a key's name ("Insert", the
// default, "F10", ...) or "none"; BB_MENU_PAD, "l3+r3" (the default), "back+start" or "off".
SDL_Keycode MenuKey() {
    static const SDL_Keycode key = [] {
        const char* name = std::getenv("BB_MENU_KEY");
        if (!name || !*name) return SDLK_INSERT;
        if (!SDL_strcasecmp(name, "none")) return SDLK_UNKNOWN;
        const SDL_Keycode found = SDL_GetKeyFromName(name);
        return found != SDLK_UNKNOWN ? found : SDLK_INSERT;
    }();
    return key;
}
enum class MenuPad { Off, L3R3, BackStart };
MenuPad MenuPadCombo() {
    static const MenuPad combo = [] {
        const char* name = std::getenv("BB_MENU_PAD");
        if (name && !SDL_strcasecmp(name, "off")) return MenuPad::Off;
        if (name && !SDL_strcasecmp(name, "back+start")) return MenuPad::BackStart;
        return MenuPad::L3R3;
    }();
    return combo;
}
// "Insert / L3+R3", as the window title and the log name it.
std::string MenuOpeners() {
    std::string text = MenuKey() != SDLK_UNKNOWN ? SDL_GetKeyName(MenuKey()) : "";
    const MenuPad pad = MenuPadCombo();
    if (pad != MenuPad::Off) {
        text += text.empty() ? "" : " / ";
        text += pad == MenuPad::L3R3 ? "L3+R3" : "Select+Start";
    }
    return text.empty() ? "the launcher only" : text;
}
bool dirty = false; // settings changed while open: saved on close
// The game's text dialog (SetTextEntry), guarded by imgui_mutex.
bool text_entry_active = false;
std::string text_entry_prompt, text_entry_text;
// Video memory warning (BbOverlay::Warn): text from the GPU thread, read by the present thread.
std::mutex warn_mutex;
std::string warn_headline;
std::string warn_detail;
float warn_fraction = -1.0f; ///< memory in use over the limit, or negative for no bar
std::chrono::steady_clock::time_point warn_until{};

// Video memory readout (SetVramUsage): written by the GPU thread's collector, read by the present
// thread.
std::atomic<u64> vram_used{0};
std::atomic<u64> vram_limit{0};
std::atomic<u64> vram_pressure{0};
std::atomic<u64> vram_critical{0};
std::atomic<u64> vram_card_free{0};

// CPU, GPU and RAM for the counter, sampled at a few Hz (the readings are syscalls, and none of
// the numbers moves between two frames). Negative: not known (yet, or not available).
struct SystemLoad {
    std::atomic<float> cpu{-1.0f}; ///< this process, % of the machine (all cores = 100 %)
    std::atomic<float> gpu{-1.0f}; ///< this process, % of the busiest 3D engine
    std::atomic<u64> ram{0};       ///< this process's working set
    std::atomic<u64> ram_free{0};  ///< the machine's available physical memory, 0: not known
};
// Leaked on purpose: the GPU sampler thread reads it while the process is shutting down.
SystemLoad& Load() {
    static SystemLoad* load = new SystemLoad;
    return *load;
}

#ifdef _WIN32
// This process's CPU time over wall time, as a share of the whole machine.
void SampleCpu() {
    FILETIME created{}, exited{}, kernel{}, user{};
    if (!GetProcessTimes(GetCurrentProcess(), &created, &exited, &kernel, &user)) {
        return;
    }
    const u64 ticks = (u64(kernel.dwHighDateTime) << 32 | kernel.dwLowDateTime) +
                      (u64(user.dwHighDateTime) << 32 | user.dwLowDateTime);
    static u64 last_ticks = 0;
    static std::chrono::steady_clock::time_point last_time{};
    const auto now = std::chrono::steady_clock::now();
    if (last_ticks != 0 && now > last_time) {
        const double wall_us = std::chrono::duration<double, std::micro>(now - last_time).count();
        const double cpu_us = double(ticks - last_ticks) / 10.0; // FILETIME: 100 ns ticks
        const unsigned cores = std::max(1u, std::thread::hardware_concurrency());
        Load().cpu.store(float(100.0 * cpu_us / (wall_us * cores)), std::memory_order_relaxed);
    }
    last_ticks = ticks;
    last_time = now;
}

// Windows' per-process GPU Engine counters (the number Task Manager shows), 3D engine only: the
// one a game loads. Opening the query and enumerating the instances is not free, so this runs on
// its own thread once a second, never on the present thread.
float QueryGpuLoad() {
    static PDH_HQUERY query{};
    static PDH_HCOUNTER counter{};
    static const bool ready = [&] {
        return PdhOpenQueryW(nullptr, 0, &query) == ERROR_SUCCESS &&
               PdhAddEnglishCounterW(query, L"\\GPU Engine(*)\\Utilization Percentage", 0,
                                     &counter) == ERROR_SUCCESS;
    }();
    if (!ready || PdhCollectQueryData(query) != ERROR_SUCCESS) {
        return -1.0f;
    }
    constexpr DWORD format = PDH_FMT_DOUBLE | PDH_FMT_NOCAP100;
    DWORD bytes = 0, count = 0;
    if (PdhGetFormattedCounterArrayW(counter, format, &bytes, &count, nullptr) != PDH_MORE_DATA) {
        return -1.0f;
    }
    static std::vector<BYTE> buffer;
    buffer.resize(bytes);
    auto* items = reinterpret_cast<PDH_FMT_COUNTERVALUE_ITEM_W*>(buffer.data());
    if (PdhGetFormattedCounterArrayW(counter, format, &bytes, &count, items) != ERROR_SUCCESS) {
        return -1.0f;
    }
    const std::wstring mine = L"pid_" + std::to_wstring(GetCurrentProcessId()) + L"_";
    double load = 0.0;
    for (DWORD i = 0; i < count; ++i) {
        if (!items[i].szName || !std::wcsstr(items[i].szName, L"engtype_3D") ||
            std::wcsncmp(items[i].szName, mine.c_str(), mine.size()) != 0) {
            continue;
        }
        load += items[i].FmtValue.doubleValue;
    }
    return float(std::min(load, 100.0));
}

// The machine's available physical memory: what Task Manager's "Available" shows (free plus
// standby). The RAM row's process figure alone reads as a leak.
u64 AvailableMemory() {
    MEMORYSTATUSEX status{};
    status.dwLength = sizeof(status);
    return GlobalMemoryStatusEx(&status) ? status.ullAvailPhys : 0;
}

void StartGpuSampler() {
    static std::once_flag once;
    std::call_once(once, [] {
        // shortcut: runs until the process exits (nothing joins it), upgrade if the overlay ever
        // needs an orderly shutdown. Idle while the readout is switched off, so it costs nothing
        // for players who never enable it.
        std::thread([] {
            for (;;) {
                if (BbSettings::Get().show_gpu) {
                    Load().gpu.store(QueryGpuLoad(), std::memory_order_relaxed);
                }
                std::this_thread::sleep_for(std::chrono::seconds(1));
            }
        }).detach();
    });
}
#else
void SampleCpu() {}
u64 AvailableMemory() {
    return 0;
}
void StartGpuSampler() {}
#endif

// The frame-time graph (NotePresent writes, FpsCounter reads, both on the present thread).
constexpr size_t FrameHistorySize = 240; ///< about four seconds at 60 Hz
std::array<float, FrameHistorySize> frame_history{};
size_t frame_history_count = 0;
size_t frame_history_next = 0;

// The counter's values in plain grey when the player turned its colours off (counter_colors=0).
constexpr ImVec4 PlainValue{0.80f, 0.80f, 0.80f, 1.0f};
bool PlainCounter() {
    return !BbSettings::Get().counter_colors.load(std::memory_order_relaxed);
}

// Green while the frame rate can keep up with a display, amber down to the game's 30 FPS floor,
// red below it. The numbers mean the same thing however the game is capped.
ImVec4 PaceColor(float frame_ms) {
    if (PlainCounter()) {
        return PlainValue;
    }
    if (frame_ms <= 20.0f) {
        return ImVec4(0.55f, 0.95f, 0.55f, 1.0f);
    }
    if (frame_ms <= 33.5f) {
        return ImVec4(1.00f, 0.82f, 0.45f, 1.0f);
    }
    return ImVec4(1.00f, 0.45f, 0.40f, 1.0f);
}

// A load in percent: amber from `amber`, red from `red`.
ImVec4 LoadColor(float percent, float amber, float red) {
    if (PlainCounter()) {
        return PlainValue;
    }
    if (percent >= red) {
        return ImVec4(1.00f, 0.45f, 0.40f, 1.0f);
    }
    if (percent >= amber) {
        return ImVec4(1.00f, 0.82f, 0.45f, 1.0f);
    }
    return ImVec4(0.55f, 0.95f, 0.55f, 1.0f);
}

// Video memory against the collector's own marks: the colours then mean what the collector does
// (green: room, amber: evicting, red: evicting aggressively).
ImVec4 VramColor(u64 used, u64 pressure, u64 critical) {
    if (PlainCounter()) {
        return PlainValue;
    }
    if (critical != 0 && used >= critical) {
        return ImVec4(1.00f, 0.45f, 0.40f, 1.0f);
    }
    if (pressure != 0 && used >= pressure) {
        return ImVec4(1.00f, 0.82f, 0.45f, 1.0f);
    }
    return ImVec4(0.55f, 0.95f, 0.55f, 1.0f);
}
float base_scale = 1.0f;

// Present rate for the FPS counter.
std::chrono::steady_clock::time_point last_present{};
float last_present_ms = 0.0f;
float frame_ms_avg = 0.0f;
BbFrameMetrics::RealFrameHistory real_frame_history;

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
        if constexpr (std::is_same_v<T, int>) {
            auto& settings = BbSettings::Get();
            if (&target == &settings.frame_generation)
                settings.frame_gen = BbSettings::NativeForRoute(value);
            if (&target == &settings.real_fps_limit) settings.frame_cap = value;
            if (&target == &settings.frame_cap) settings.real_fps_limit = value;
        }
        BbSettings::UpdateCheatMask();
        dirty = true;
    }
}

std::string WrappedCaption(const char* label, float width) {
    const char* id = std::strstr(label, "###");
    const std::string caption(label, id ? id : label + std::strlen(label));
    std::string result, line;
    for (size_t first = 0; first < caption.size();) {
        const size_t end = caption.find(' ', first);
        const std::string word = caption.substr(first, end == std::string::npos ? end : end - first);
        const std::string next = line.empty() ? word : line + " " + word;
        if (!line.empty() && ImGui::CalcTextSize(next.c_str()).x > width) {
            result += line + "\n";
            line = word;
        } else {
            line = next;
        }
        if (end == std::string::npos) break;
        first = end + 1;
    }
    result += line;
    if (id) result += id; // wrapping a caption must not change the saved/navigation ID
    return result;
}

void Checkbox(const char* label, std::atomic<bool>& value) {
    bool v = value;
    const float width = std::max(80.0f, ImGui::GetContentRegionAvail().x -
        ImGui::GetFrameHeight() - ImGui::GetStyle().ItemInnerSpacing.x - 36.0f);
    const auto caption = WrappedCaption(label, width);
    const bool changed = ImGui::Checkbox(caption.c_str(), &v);
    Store(value, v, changed);
}

void Slider(const char* label, std::atomic<float>& value, float lo, float hi) {
    float v = value;
    const bool changed = ImGui::SliderFloat(label, &v, lo, hi, "%.2f");
    Store(value, v, changed);
}

void Hint(const char* text) {
    const float right = ImGui::GetWindowPos().x + ImGui::GetWindowContentRegionMax().x;
    if (ImGui::GetItemRectMax().x + ImGui::GetStyle().ItemSpacing.x +
        ImGui::CalcTextSize("(?)").x <= right) {
        ImGui::SameLine();
        ImGui::TextDisabled("(?)");
    }
    // A full-width field keeps its own hover tooltip instead of clipping a help marker.
    if (ImGui::BeginItemTooltip()) {
        ImGui::PushTextWrapPos(ImGui::GetFontSize() * 30.0f);
        ImGui::TextUnformatted(text);
        ImGui::PopTextWrapPos();
        ImGui::EndTooltip();
    }
}

bool IsFsr41(int upscaler) {
    return upscaler == BbSettings::UpscalerFsr411 || upscaler == BbSettings::UpscalerFsr412;
}
struct Fsr41Route { int version, backend; const char* title; const char* method; int hint; };
static constexpr Fsr41Route Fsr41Routes[] = {
    {BbSettings::UpscalerFsr412, 0, "FSR 4.1.2 - AMD Vulkan", "AMD Vulkan", Fsr41Ui::Hint412Vk},
    {BbSettings::UpscalerFsr412, 1, "FSR 4.1.2 - AMD DX12", "AMD DX12", Fsr41Ui::Hint412Dx},
    {BbSettings::UpscalerFsr411, 1, "FSR 4.1.1 - AMD DX12", "AMD DX12", Fsr41Ui::Hint411Dx},
    {BbSettings::UpscalerFsr411, 0, "FSR 4.1.1 - Vulkan (fsr4vk)", "Vulkan (fsr4vk)", Fsr41Ui::Hint411Vk},
};
bool AnyFsr41() {
    const auto& s=BbSettings::Get();
    for(const auto& route:Fsr41Routes) if(s.FsrMethodSupported(route.version,route.backend)) return true;
    return false;
}
void Fsr41Settings() {
    auto& s=BbSettings::Get();
    const float max_width=std::max(300.f, ImGui::GetMainViewport()->WorkSize.x-60.f*base_scale);
    ImGui::SetNextWindowSize(ImVec2(std::min(420.f*base_scale,max_width),0), ImGuiCond_Appearing);
    const std::string title=std::string(Fsr41Ui::Text(Fsr41Ui::Settings))+"###FSR41Settings";
    if(!ImGui::BeginPopupModal(title.c_str(),nullptr,ImGuiWindowFlags_AlwaysAutoResize|ImGuiWindowFlags_NoTitleBar)) return;
    ImGui::TextUnformatted(Fsr41Ui::Text(Fsr41Ui::Settings));
    ImGui::Spacing();
    if(ImGui::BeginTable("FSR41Methods",2,ImGuiTableFlags_SizingStretchProp)) {
        ImGui::TableSetupColumn("Method",ImGuiTableColumnFlags_WidthStretch,1.1f);
        ImGui::TableSetupColumn("Support",ImGuiTableColumnFlags_WidthStretch,1.f);
        for(const auto& route:Fsr41Routes) {
            if ((route.backend==0 && route.version==BbSettings::UpscalerFsr412) ||
                (route.backend==1 && route.version==BbSettings::UpscalerFsr411)) {
                ImGui::TableNextRow(); ImGui::TableSetColumnIndex(0);
                ImGui::TextDisabled("FSR %s",route.version==BbSettings::UpscalerFsr412 ? "4.1.2" : "4.1.1");
            }
            const bool ready=s.FsrMethodSupported(route.version,route.backend);
            const bool selected=s.upscaler==route.version && s.fsr411_backend==route.backend;
            int status=ready ? 0 : s.fsr41_status[route.version==BbSettings::UpscalerFsr412][route.backend].load();
            if(status<0 || status>8 || (!ready && status==0)) status=5;
            ImGui::TableNextRow(); ImGui::TableSetColumnIndex(0);
            if(selected) ImGui::TableSetBgColor(ImGuiTableBgTarget_RowBg0,IM_COL32(45,42,34,255));
            ImGui::BeginDisabled(!ready);
            const std::string label=std::string(route.method)+"###"+route.title;
            if(ImGui::RadioButton(label.c_str(),selected)) {
                Store(s.fsr41_version,route.version,true);
                Store(s.fsr411_backend,route.backend,true);
                Store(s.upscaler,route.version,true);
            }
            ImGui::EndDisabled();
            ImGui::SameLine();
            ImGui::PushID(route.title);
            ImGui::SmallButton("(i)");
            if(ImGui::IsItemHovered(ImGuiHoveredFlags_DelayNormal) || ImGui::IsItemFocused()) {
                ImGui::BeginTooltip();
                ImGui::PushTextWrapPos(ImGui::GetFontSize()*30.f);
                ImGui::TextUnformatted(Fsr41Ui::Text(route.hint));
                ImGui::PopTextWrapPos();
                ImGui::EndTooltip();
            }
            ImGui::PopID();
            ImGui::TableSetColumnIndex(1);
            const ImVec4 color=status==0 ? ImVec4(.47f,.74f,.57f,1) :
                status==1 ? ImVec4(.88f,.47f,.44f,1) :
                status==5 || status==6 || status==8 ? ImVec4(.54f,.55f,.56f,1) : ImVec4(.85f,.64f,.25f,1);
            ImGui::PushTextWrapPos();
            ImGui::TextColored(color,"%s",Fsr41Ui::Text(Fsr41Ui::Supported+status));
            ImGui::PopTextWrapPos();
        }
        ImGui::EndTable();
    }
    ImGui::Spacing();
    if(ImGui::Button(Fsr41Ui::Text(Fsr41Ui::Close))) ImGui::CloseCurrentPopup();
    ImGui::EndPopup();
}

float DisplayFps() {
    const auto& s=BbSettings::Get();
    const float confirmed=s.nvidia_output_fps;
    if (s.frame_generation==BbSettings::FrameGenerationNvidia &&
        s.frame_generation_active>1 && confirmed>0.0f) return confirmed;
    return frame_ms_avg>0.0f ? 1000.0f/frame_ms_avg : 0.0f;
}


void WorkshopTheme(ImGuiStyle& style) {
    style.WindowRounding = 8.0f;
    style.ChildRounding = 4.0f;
    style.PopupRounding = 6.0f;
    style.FrameRounding = 3.0f;
    style.GrabRounding = 3.0f;
    style.TabRounding = 4.0f;
    style.WindowBorderSize = 1.0f;
    const ImVec4 brass(0.84f, 0.76f, 0.63f, 1.0f);
    const ImVec4 slate(0.11f, 0.13f, 0.15f, 1.0f);
    const ImVec4 hover(0.23f, 0.24f, 0.25f, 1.0f);
    style.Colors[ImGuiCol_Text] = ImVec4(0.94f, 0.90f, 0.85f, 1.0f);
    style.Colors[ImGuiCol_TextDisabled] = ImVec4(0.63f, 0.62f, 0.58f, 1.0f);
    style.Colors[ImGuiCol_WindowBg] = ImVec4(0.047f, 0.059f, 0.071f, 0.96f);
    style.Colors[ImGuiCol_ChildBg] = ImVec4(0.078f, 0.094f, 0.11f, 0.72f);
    style.Colors[ImGuiCol_PopupBg] = ImVec4(0.078f, 0.094f, 0.11f, 0.99f);
    style.Colors[ImGuiCol_Border] = ImVec4(0.25f, 0.25f, 0.22f, 0.9f);
    style.Colors[ImGuiCol_FrameBg] = slate;
    style.Colors[ImGuiCol_FrameBgHovered] = hover;
    style.Colors[ImGuiCol_FrameBgActive] = ImVec4(0.31f, 0.29f, 0.25f, 1.0f);
    style.Colors[ImGuiCol_TitleBg] = ImVec4(0.055f, 0.067f, 0.078f, 1.0f);
    style.Colors[ImGuiCol_TitleBgActive] = ImVec4(0.094f, 0.11f, 0.125f, 1.0f);
    style.Colors[ImGuiCol_CheckMark] = brass;
    style.Colors[ImGuiCol_SliderGrab] = brass;
    style.Colors[ImGuiCol_SliderGrabActive] = ImVec4(0.94f, 0.85f, 0.7f, 1.0f);
    style.Colors[ImGuiCol_Button] = slate;
    style.Colors[ImGuiCol_ButtonHovered] = hover;
    style.Colors[ImGuiCol_ButtonActive] = ImVec4(0.34f, 0.31f, 0.25f, 1.0f);
    style.Colors[ImGuiCol_Header] = ImVec4(0.25f, 0.23f, 0.19f, 1.0f);
    style.Colors[ImGuiCol_HeaderHovered] = hover;
    style.Colors[ImGuiCol_HeaderActive] = ImVec4(0.34f, 0.31f, 0.25f, 1.0f);
    style.Colors[ImGuiCol_Tab] = slate;
    style.Colors[ImGuiCol_TabHovered] = hover;
    style.Colors[ImGuiCol_TabSelected] = ImVec4(0.25f, 0.23f, 0.19f, 1.0f);
    style.Colors[ImGuiCol_TabSelectedOverline] = brass;
    style.Colors[ImGuiCol_Separator] = ImVec4(0.3f, 0.28f, 0.23f, 1.0f);
    style.Colors[ImGuiCol_NavCursor] = brass;
}

void Section(const char* label) {
    ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(0.84f, 0.76f, 0.63f, 1.0f));
    ImGui::SeparatorText(label);
    ImGui::PopStyleColor();
}

float MenuScale() {
    return ImGui::GetFontSize() / 18.0f;
}
void ImageSettings() {
    auto& s = BbSettings::Get();
    Section(Text("Temporal upscaler", "Временной апскейлер"));
    const char* upscalers[] = {
        Text("Off###upscaler_off", "Выкл###upscaler_off"),
        "FSR 3.1", "FSR 4 (INT8)", "FSR 4.1.1 (INT8)",
        Text("TAA (native anti-aliasing)###upscaler_taa",
             "TAA (нативное сглаживание)###upscaler_taa"),
        "DLSS (NVIDIA RTX)", "XeSS (Intel / compatible GPUs)", "FSR 4.1.2",
    };
    int upscaler = s.upscaler;
    if (ImGui::BeginCombo(Text("Upscaler###upscaler", "Апскейлер###upscaler"), upscalers[upscaler])) {
        for (int i = 0; i < BbSettings::UpscalerCount; ++i) {
            const bool supported = i == BbSettings::UpscalerFsr4 ? s.fsr4_supported.load()
                : i == BbSettings::UpscalerFsr411 ? s.fsr411_supported.load()
                : i == BbSettings::UpscalerDlss   ? s.dlss_supported.load()
                : i == BbSettings::UpscalerXess   ? s.xess_supported.load()
                : i == BbSettings::UpscalerFsr412 ? AnyFsr41() : true;
            ImGui::BeginDisabled(!supported);
            const bool family = i == BbSettings::UpscalerFsr412;
            if (ImGui::Selectable(family ? Fsr41Ui::Text(Fsr41Ui::Family) : upscalers[i],
                                  family ? IsFsr41(upscaler) : i == upscaler)) {
                if (family) {
                    if (!IsFsr41(upscaler)) {
                        bool restored=false;
                        if(s.FsrMethodSupported(s.fsr41_version,s.fsr411_backend)) {
                            Store(s.upscaler,s.fsr41_version.load(),true);
                            restored=true;
                        }
                        if(!restored) for (const auto& route : Fsr41Routes) {
                            if (!s.FsrMethodSupported(route.version, route.backend)) continue;
                            Store(s.fsr41_version, route.version, true);
                            Store(s.fsr411_backend, route.backend, true);
                            Store(s.upscaler, route.version, true);
                            break;
                        }
                    }
                } else Store(s.upscaler, i, true);
            }
            ImGui::EndDisabled();
            if (!supported) {
                ImGui::SameLine();
                ImGui::TextDisabled("%s", i == BbSettings::UpscalerDlss
                    ? Text("— unavailable", "— недоступен")
                    : Text("— not supported by this GPU", "— не поддерживается видеокартой"));
            }
        }
        ImGui::EndCombo();
    }
#ifdef _WIN32
    const bool fsr411_selected = IsFsr41(s.upscaler);
    const std::string settings_button = std::string(Fsr41Ui::Text(Fsr41Ui::Settings))+"##FSR41SettingsButton";
    ImGui::BeginDisabled(!fsr411_selected);
    if (ImGui::Button(settings_button.c_str())) ImGui::OpenPopup("###FSR41Settings");
    ImGui::EndDisabled();
    if (fsr411_selected) {
        ImGui::SameLine();
        for (const auto& route : Fsr41Routes) if (route.version==s.upscaler && route.backend==s.fsr411_backend)
            ImGui::TextDisabled("%s: %s", Fsr41Ui::Text(Fsr41Ui::Selected), route.title);
    } else if (!AnyFsr41()) ImGui::TextDisabled("%s", Fsr41Ui::Text(Fsr41Ui::Unavailable));
    Fsr41Settings();
    if (const char* problem = s.fsr4_method_problem.load(); problem && fsr411_selected) {
        ImGui::PushTextWrapPos();
        ImGui::TextColored(ImVec4(1.0f, 0.5f, 0.3f, 1.0f), "%s", problem);
        ImGui::PopTextWrapPos();
    }
#endif
    // ConfigureDlssSupport switches to FSR on failure. Keep the reason visible
    // after that fallback instead of incorrectly blaming the selected GPU.
    if (const char* problem = s.dlss_problem.load()) {
        ImGui::PushTextWrapPos();
        ImGui::TextColored(ImVec4(1.0f, 0.5f, 0.3f, 1.0f), "DLSS: %s", problem);
        ImGui::PopTextWrapPos();
    }
    if (const char* problem=s.xess_problem.load()) ImGui::TextWrapped("XeSS: %s",problem);
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
        if (s.upscaler == BbSettings::UpscalerFsr412) {
            Hint("FSR 4.1.2 uses the original AMD Vulkan driver or AMD DX12 bridge. Both FSR 4.1.1 methods remain available.");
        } else if (s.upscaler == BbSettings::UpscalerFsr411) {
#ifdef _WIN32
            Hint("FSR 4.1.1 temporal upscaling uses the method selected above. AMD DX12 is included in the Windows package; Vulkan assets can be downloaded in the launcher. Quality presets and sharpening apply to both methods.");
#else
            Hint("FSR 4.1.1 uses the Vulkan model passes. One model covers Native through Performance, with another for Ultra Performance. See tools/fsr4cap/build_assets.sh for asset preparation.");
#endif
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
    const bool xess = s.upscaler == BbSettings::UpscalerXess;
    int preset = xess ? s.xess_preset.load() : taa ? BbSettings::NativeAA : s.preset.load();
    if (xess && preset < 0) preset = BbSettings::LegacyXessPreset(s.preset);
    char preset_label[64];
    std::snprintf(preset_label, sizeof(preset_label), "%s (x%.1f)",
                  xess ? BbSettings::XessPresetName(preset) : BbSettings::PresetName(preset),
                  xess ? BbSettings::XessPresetScale(preset) : BbSettings::PresetScale(preset));
    const char* quality_title = xess ? Text("XeSS quality###xess_preset", "Качество XeSS###xess_preset")
                                    : Text("Quality preset###preset", "Пресет качества###preset");
    if (ImGui::BeginCombo(quality_title, preset_label)) {
        const int preset_count = xess ? int(BbSettings::XessPresetCount) : int(BbSettings::PresetCount);
        for (int i = 0; i < preset_count; ++i) {
            char label[96];
            const float scale = xess ? BbSettings::XessPresetScale(i) : BbSettings::PresetScale(i);
            const int output = s.output_res;
            const char* item_format = xess ? Text("%s (x%.1f, render %dx%d)###xess_preset_%d",
                                                 "%s (x%.1f, рендер %dx%d)###xess_preset_%d")
                                          : Text("%s (x%.1f, render %dx%d)###preset_%d",
                                                 "%s (x%.1f, рендер %dx%d)###preset_%d");
            std::snprintf(label, sizeof(label), item_format,
                          xess ? BbSettings::XessPresetName(i) : BbSettings::PresetName(i), scale,
                          int(std::lround(BbSettings::OutputWidths[output] / scale / 2) * 2),
                          int(std::lround(BbSettings::OutputHeights[output] / scale / 2) * 2), i);
            if (ImGui::Selectable(label, i == preset)) {
                Store(xess ? s.xess_preset : s.preset, i, true);
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
        ImGui::Text(Text("Startup preset: %s", "Пресет при запуске: %s"),
                    s.startup_upscaler == BbSettings::UpscalerXess ?
                    BbSettings::XessPresetName(s.startup_xess_preset) : BbSettings::PresetName(s.startup_preset));
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
    ImGui::EndDisabled(); // upscaler off
    Section(Text("Output resolution", "Разрешение вывода"));
    Hint(Text("Ultrawide camera and HUD patches are applied at startup. Changing to, from or "
              "between ultrawide outputs requires restarting the game.",
              "Патчи камеры и HUD для сверхширокого экрана применяются при запуске. Смена на "
              "сверхширокое разрешение, с него или между такими разрешениями требует перезапуска игры."));
    const int output = s.output_res;
    char output_label[32];
    std::snprintf(output_label, sizeof(output_label), "%d x %d",
                  BbSettings::OutputWidths[output], BbSettings::OutputHeights[output]);
    if (ImGui::BeginCombo(Text("Output resolution###output_res", "Разрешение вывода###output_res"), output_label)) {
        for (int i = 0; i < BbSettings::OutputCount; ++i) {
            char label[32];
            std::snprintf(label, sizeof(label), "%d x %d",
                          BbSettings::OutputWidths[i], BbSettings::OutputHeights[i]);
            if (ImGui::Selectable(label, i == output)) {
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
    Section(Text("Image tuning", "Настройка изображения"));
    ImGui::BeginDisabled(!upscaler_on);
    Checkbox(Text("Sharpening (RCAS)###sharpen", "Резкость (RCAS)###sharpen"), s.sharpen);
    ImGui::BeginDisabled(!s.sharpen);
    Slider(Text("Sharpness###sharpness", "Сила резкости###sharpness"), s.sharpness, 0.0f, 2.0f);
    Hint(Text("Up to 1: the upscaler's own sharpening (RCAS). Above 1: adds another RCAS pass. "
              "Ctrl+click the slider to enter an exact value.",
              "До 1 — резкость самого апскейлера (RCAS). Выше 1 добавляется ещё один проход RCAS."
              " Ctrl+клик по ползунку — ввести точное значение."));
    ImGui::EndDisabled();
    Checkbox(Text("Object motion vectors###object_motion",
                  "Векторы движения объектов###object_motion"), s.object_motion);
    Hint(Text("Accurate vectors for animated objects: clothing and weapons break up less during "
              "motion. Static scenes do not receive an extra pass. Changes take effect after "
              "restarting the game.",
              "Точные векторы для анимированных объектов: одежда и оружие меньше рассыпаются при "
              "движении. Статичная сцена не получает дополнительный проход. Изменение применяется"
              " после перезапуска игры."));
    ImGui::EndDisabled();

}

void FrameSettings() {
    auto& s = BbSettings::Get();
    Section(Text("Real game frames", "Реальные кадры игры"));
    ImGui::BeginDisabled(!s.variable_frame_time);
    const int real_cap = s.real_fps_limit;
    const char* cap_modes[] = {Text("Launcher / display policy", "Настройка запуска / монитора"),
                              Text("Custom cap", "Свой лимит"), Text("No cap", "Без ограничения")};
    const int cap_mode = real_cap < 0 ? 0 : real_cap == 0 ? 2 : 1;
    if (ImGui::BeginCombo(Text("Real game FPS###real_fps_mode", "Реальные FPS игры###real_fps_mode"),cap_modes[cap_mode])) {
        for (int i=0; i<3; ++i) {
            const std::string name = std::string(cap_modes[i])+"###real_fps_mode_"+std::to_string(i);
            if (ImGui::Selectable(name.c_str(),i==cap_mode)) Store(s.real_fps_limit,i==0 ? -1 : i==2 ? 0 : 75,true);
        }
        ImGui::EndCombo();
    }
    if (s.real_fps_limit > 0) {
        static int real_limit = 75;
        static bool editing_real_limit = false;
        if (!editing_real_limit) real_limit=s.real_fps_limit;
        ImGui::TextUnformatted(Text("Real FPS cap", "Лимит реальных FPS"));
        ImGui::SameLine();
        ImGui::SetNextItemWidth(std::max(80.0f, ImGui::GetContentRegionAvail().x -
            148.0f * MenuScale() - ImGui::GetStyle().ItemSpacing.x));
        if (ImGui::DragInt("###real_fps_limit",&real_limit,1.0f,30,120,"%d FPS",ImGuiSliderFlags_AlwaysClamp))
            Store(s.real_fps_limit,real_limit,true);
        ImGui::SameLine();
        ImGui::SetNextItemWidth(148.0f*MenuScale());
        if (ImGui::InputInt("###real_fps_entry",&real_limit,1,10,ImGuiInputTextFlags_EnterReturnsTrue) ||
            ImGui::IsItemDeactivatedAfterEdit())
            Store(s.real_fps_limit,std::clamp(real_limit,30,120),true);
        editing_real_limit=ImGui::IsItemActive();
    }
    ImGui::EndDisabled();
    Hint(s.variable_frame_time ?
        Text("Counts real game frames; FG can add frames above this cap. Changes are shared with the launcher. Keep real FPS at or below 120 for the game's timing.",
             "Лимит реальных кадров; FG может добавлять кадры сверх него. Общая настройка с лаунчером. Для тайминга игры рекомендуется не выше 120 FPS.") :
        Text("Choose Unlocked under Frames in the launcher to change game FPS live. This session uses a fixed game-timing patch.",
             "Выберите Unlocked в разделе Frames лаунчера для изменения FPS в игре. В этой сессии используется фиксированный тайминг."));
    const bool upscaler_on = s.upscaler != BbSettings::UpscalerOff;
    Section(Text("Frame Generation and output cap", "Генерация кадров и лимит вывода"));
    Checkbox(Text("DLSSG mod for RTX 20/30 (experimental)###nvidia_fg_mod",
                  "Мод DLSSG для RTX 20/30 (экспериментальный)###nvidia_fg_mod"),s.nvidia_fg_mod);
    Hint(Text("Requires Apply and restart. Only the selected RTX 20/30 can load the isolated mod; RTX 40/50 keep the original NVIDIA path. Vulkan support is experimental. The launcher prepares the provider on restart.",
              "Нужны применение и перезапуск. Изолированный мод загружается только для выбранной RTX 20/30; RTX 40/50 используют исходный путь NVIDIA. Vulkan экспериментален. Лаунчер подготовит мод при перезапуске."));
    if (const char* status=s.nvidia_fg_mod_status) ImGui::TextWrapped("DLSSG: %s",status);
    const char* frame_generators[]={Text("Off###fg_off","Выключено###fg_off"),"FSR Frame Generation (2x)","NVIDIA DLSS Frame Generation / MFG","FSR FG - Supermedo (SDR)","DLSS FG - Supermedo (SDR, restart)", "AMD ML-FG 4.0.1 (SDR, RX 9000)", "AMD ML-FG 4.0.2 (SDR, RX 9000)"};
    const int fg=std::clamp(s.frame_generation.load(),0,6);
    if (ImGui::BeginCombo(Text("Frame Generation###frame_generation","Генерация кадров###frame_generation"),frame_generators[fg])) {
        for (int i=0;i<7;++i) {
            ImGui::BeginDisabled(i!=0 && !upscaler_on);
            if (ImGui::Selectable(frame_generators[i],fg==i)) Store(s.frame_generation,i,true);
            ImGui::EndDisabled();
        }
        ImGui::EndCombo();
    }
    if ((s.frame_generation == BbSettings::FrameGenerationNvidia && !s.startup_workshop_nvidia) ||
        (s.startup_workshop_nvidia && s.frame_generation >= BbSettings::FrameGenerationNativeFsr))
        ImGui::TextWrapped("FG backend change saved: Apply and restart to activate it.");
    if (s.startup_native_dlss != (s.frame_generation==BbSettings::FrameGenerationNativeDlss))
        ImGui::TextWrapped("Apply and restart to switch between the native DLSS bridge and Streamline.");
    if (s.frame_generation>=BbSettings::FrameGenerationNativeFsr) {
        ImGui::TextWrapped("Supermedo native FG uses SDR output. HDR retains the existing providers.");
        int multiplier=s.frame_gen_multiplier;
        if(ImGui::SliderInt("Native FG multiplier###frame_gen_multiplier",&multiplier,2,4,"%dx")) Store(s.frame_gen_multiplier,multiplier,true);
        Checkbox("Fit native FG to display###frame_gen_fit_display",s.frame_gen_fit_display);
        if(const char* message=s.frame_gen_problem)ImGui::TextWrapped("Native FG: %s",message);
    }
    if (s.frame_generation==BbSettings::FrameGenerationNvidia) {
        const int fg_preset=std::clamp(s.nvidia_fg_preset.load(),0,3);
        if (ImGui::BeginCombo(Text("NVIDIA FG preset###nvidia_fg_preset","Пресет NVIDIA FG###nvidia_fg_preset"),
                              BbSettings::NvidiaFgPresetName(fg_preset))) {
            for (int i=0;i<4;++i)
                if (ImGui::Selectable(BbSettings::NvidiaFgPresetName(i),i==fg_preset)) Store(s.nvidia_fg_preset,i,true);
            ImGui::EndCombo();
        }
        if (s.nvidia_fg_preset!=s.startup_nvidia_fg_preset)
            Hint(Text("FG preset saved. Apply and restart to change the NVIDIA driver profile.",
                      "Пресет FG сохранён. Примените и перезапустите игру для изменения профиля NVIDIA."));
        if (s.nvidia_fg_preset_status==1)
            ImGui::Text(Text("NVIDIA driver reports FG preset: %s","Драйвер NVIDIA сообщает пресет FG: %s"),
                        BbSettings::NvidiaFgPresetName(s.nvidia_fg_reported_preset));
        else if (s.nvidia_fg_preset_status==2) {
            ImGui::TextWrapped("NVIDIA FG: %s (0x%llx).",
                BbNvidia::Preset::ErrorName(s.nvidia_fg_feedback),
                static_cast<unsigned long long>(s.nvidia_fg_feedback.load()));
            Hint(Text("The driver did not confirm the selected FG model. See last_run.log for the profile and runtime result.",
                      "Драйвер не подтвердил модель FG. Результат профиля и среды — в last_run.log."));
        } else
            Hint(Text("FG model not yet confirmed by NVIDIA. Runtime updates are enabled; the driver must accept the override for this process.",
                      "Модель FG ещё не подтверждена NVIDIA. Обновления среды включены; драйвер должен принять переопределение для этого процесса."));
        if (s.nvidia_fg_profile_preset>=1)
            ImGui::Text(Text("Driver profile FG preference: %s","Пресет FG в профиле драйвера: %s"),
                        BbSettings::NvidiaFgPresetName(s.nvidia_fg_profile_preset));
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
    Hint(Text("FSR FG adds one interpolated frame between real frames, in SDR or HDR10. The normal FPS limit counts real frames: 75 can produce 150 with FG 2x. Background FPS caps disable generation.",
              "FSR FG добавляет промежуточный кадр в SDR или HDR10. Обычный лимит относится к реальным кадрам: 75 даёт до 150 с FG 2x. При лимите FPS в фоне генерация отключается."));
    Checkbox(Text("Limit total FPS with Frame Generation###limit_generated_fps",
                  "Лимит общих FPS с генерацией кадров###limit_generated_fps"),s.limit_generated_fps);
    ImGui::BeginDisabled(!s.limit_generated_fps);
    static int generated_limit=144;
    static bool editing_generated_limit=false;
    if (!editing_generated_limit) generated_limit=s.generated_fps_limit;
    ImGui::TextUnformatted(Text("Total FPS cap","Общий лимит FPS"));
    ImGui::SameLine();
    ImGui::SetNextItemWidth(std::max(80.0f, ImGui::GetContentRegionAvail().x -
        148.0f * MenuScale() - ImGui::GetStyle().ItemSpacing.x));
    if (ImGui::DragInt("###generated_fps_limit",
                      &generated_limit,1.0f,30,1000,"%d FPS",ImGuiSliderFlags_AlwaysClamp))
        Store(s.generated_fps_limit,generated_limit,true);
    ImGui::SameLine();
    ImGui::SetNextItemWidth(148.0f * MenuScale());
    if (ImGui::InputInt("###generated_fps_entry",&generated_limit,1,10,ImGuiInputTextFlags_EnterReturnsTrue) ||
        ImGui::IsItemDeactivatedAfterEdit())
        Store(s.generated_fps_limit,std::clamp(generated_limit,30,1000),true);
    editing_generated_limit=ImGui::IsItemActive();
    ImGui::EndDisabled();
    Hint(Text("Optional. This cap includes generated frames and can reduce the real frame rate. Generated frames do not advance game logic or physics.",
              "Этот необязательный лимит включает промежуточные кадры и может снизить реальные FPS. Генерация не меняет физику и логику игры."));
    if (s.frame_generation==BbSettings::FrameGenerationFsr) {
        if (const char* problem=s.frame_generation_problem.load()) ImGui::TextWrapped("%s",problem);
        else ImGui::TextUnformatted(s.frame_generation_active==2 ? Text("FSR FG active: 2x","FSR FG активна: 2x") :
                                  Text("FSR FG: waiting for valid scene frames","FSR FG: ожидание кадров сцены"));
    }
    Section(Text("Latency", "Задержка"));
    const char* reflex_modes[]={Text("Off","Выключено"),Text("On","Включено"),"On + Boost"};
    const int reflex=std::clamp(s.reflex.load(),0,2);
    ImGui::BeginDisabled(!s.reflex_supported && s.gpu_vendor_id != 0x10de);
    if (ImGui::BeginCombo("NVIDIA Reflex###reflex",reflex_modes[reflex])) {
        for(int i=0;i<3;++i) if(ImGui::Selectable(reflex_modes[i],i==reflex)) Store(s.reflex,i,true);
        ImGui::EndCombo();
    }
    ImGui::EndDisabled();
    Hint(Text("Reflex works independently of NVIDIA FG. NVIDIA FG enables Reflex automatically; Boost is optional. Unsupported choices are disabled.",
              "Reflex работает независимо от NVIDIA FG. Генерация NVIDIA включает Reflex автоматически; Boost необязателен. Неподдерживаемые настройки недоступны."));
    ImGui::BeginDisabled(!s.amd_antilag_supported);
    Checkbox("AMD Anti-Lag 2###amd_antilag",s.amd_antilag);
    ImGui::EndDisabled();
    Hint(s.amd_antilag_supported ?
        Text("Reduces input latency through the Radeon Vulkan driver. Works independently of the upscaler and FSR FG.",
             "Снижает задержку ввода через драйвер Radeon Vulkan. Работает независимо от апскейлера и FSR FG.") :
        Text("AMD Anti-Lag 2 needs a Radeon GPU and a driver with VK_AMD_anti_lag support.",
             "AMD Anti-Lag 2 требует Radeon и драйвер с поддержкой VK_AMD_anti_lag."));

}

void WindowSettings() {
    auto& s = BbSettings::Get();
    Section(Text("Window and presentation", "Окно и показ кадров"));
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

    Section(Text("Background behavior", "Работа в фоне"));
    Checkbox("Mute when the game is in the background###mute_unfocused", s.mute_unfocused);
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


}

void OverlaySettings() {
    auto& s = BbSettings::Get();
    Section(Text("Performance overlay", "Статистика производительности"));
    Checkbox(Text("Show performance overlay###show_fps", "Показывать статистику###show_fps"), s.show_fps);
    Hint(Text("FPS, frame time and upscaler in the top-right corner. "
              "Hide it without disabling this settings menu.",
              "FPS, время кадра и апскейлер в правом верхнем углу. "
              "Отключение не скрывает это меню настроек."));
    Section(Text("Optional fields", "Дополнительные поля"));
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
    Checkbox(Text("Show Frame Generation in overlay###show_frame_generation",
                  "Показывать генерацию кадров в статистике###show_frame_generation"),s.show_frame_generation);
    Checkbox(Text("Show NVIDIA FG preset in overlay###show_fg_preset",
                  "Показывать пресет NVIDIA FG в статистике###show_fg_preset"),s.show_fg_preset);
    Hint(Text("FG model:C: NVIDIA confirms C. C?: profile preference, not yet confirmed. C!: override error. Separate from DLSS upscaling.",
              "FG model:C: NVIDIA подтверждает C. C?: значение профиля без подтверждения. C!: ошибка. Отдельно от апскейлера DLSS."));
    Checkbox(Text("Show PC latency in overlay###show_latency",
                  "Показывать задержку ПК в статистике###show_latency"),s.show_latency);
    Hint(Text("Reflex measures simulation start to GPU completion. N/A means there is no valid driver sample. Monitor and input-device latency are not included.",
              "Reflex измеряет время от начала симуляции до завершения GPU. N/A: нет данных драйвера. Задержка монитора и устройства ввода не учитывается."));
    Section(Text("Frametime graph", "График времени кадров"));
    Checkbox(Text("Show frametime graph in overlay###show_frametime_graph",
                  "Показывать график времени кадров###show_frametime_graph"),s.show_frametime_graph);
    Hint(Text("Last 240 real-frame presentation intervals, latest and peak time. Generated frames are not included. This is not GPU render time or monitor latency.",
              "Последние 240 интервалов показа реальных кадров, текущее и пиковое время. Сгенерированные кадры не включены. Это не время рендера GPU и не задержка монитора."));
    Section(Text("System readouts", "Системная статистика"));
    Checkbox("App-present interval###show_frame_times", s.show_frame_times);
    Checkbox("Render-path latency###show_render_latency", s.show_render_latency);
    Checkbox("VRAM usage###show_vram", s.show_vram);
    Checkbox("GPU usage###show_gpu", s.show_gpu);
    Checkbox("CPU usage###show_cpu", s.show_cpu);
    Checkbox("RAM usage###show_ram", s.show_ram);
    Checkbox("App-present graph###show_fps_graph", s.show_fps_graph);
    Checkbox("Color-coded values###counter_colors", s.counter_colors);

}

void CheatSettings() {
    auto& s = BbSettings::Get();
    Section(Text("Runtime cheats", "Читы во время игры"));
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
    ImGui::BeginDisabled(!(s.cheat_supported.load()&BB_CHEAT_FALL));
    Checkbox(Text("No fall damage###cheat_no_fall_damage","Без урона от падения###cheat_no_fall_damage"),s.cheat_no_fall_damage);
    ImGui::EndDisabled();
    ImGui::BeginDisabled(!(s.cheat_supported.load() & 32u));
    Checkbox(Text("Consumables are not reduced on use###cheat_no_consume",
                  "Расходники не тратятся при использовании###cheat_no_consume"), s.cheat_no_consume);
    ImGui::EndDisabled();
    Hint(Text("Includes ammunition. You still need to own the item; selling, dropping and buying keep their normal behavior.",
              "Включая боеприпасы. Предмет должен быть в инвентаре; продажа, выбрасывание и покупка работают как обычно."));
    if (s.cheat_supported.load() != BB_CHEAT_ALL)
        ImGui::TextWrapped("%s", Text("Some live cheats are unavailable for this executable or conflict with a patch. See last_run.log.",
                                     "Часть читов недоступна для этого исполняемого файла или конфликтует с патчем. См. last_run.log."));
    Section(Text("Startup cheats (restart required)", "Читы при запуске (после перезапуска)"));
    for (int e=0;e<BbSettings::EffectCount;++e) {
        const auto& effect=BbSettings::Effects[e];
        if (std::string_view(effect.key).starts_with("cheat_")) {
            const std::string label=std::string(Text(effect.label_en,effect.label))+
                "###"+effect.key;
            Checkbox(label.c_str(),s.effects[e]);
        }
    }
}

void AdvancedSettings() {
    auto& s = BbSettings::Get();
    Section(Text("Menu language", "Язык меню"));
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

    const bool taa = s.upscaler == BbSettings::UpscalerTaa;
    ImGui::BeginDisabled(s.upscaler == BbSettings::UpscalerOff);
    Section(Text("Reconstruction and motion", "Реконструкция и движение"));
    Checkbox(Text("Subpixel jitter###jitter", "Субпиксельный сдвиг (jitter)###jitter"), s.jitter);
    Hint(Text("Each frame shifts the scene by a fraction of a pixel, letting the upscaler combine"
              " several frames to recover more detail. Without jitter, only history-based "
              "smoothing remains.",
              "Каждый кадр сцена сдвигается на долю пикселя, и апскейлер собирает из нескольких "
              "кадров больше деталей. Без него получается только сглаживание по истории."));

    Section(Text("Reactive mask", "Маска реактивности"));
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

}

void EffectSettings() {
    auto& s = BbSettings::Get();
    static const char* prompt_modes[] = {"Follow the device in use", "PlayStation", "Keyboard and mouse", "Xbox", "Nintendo Switch"};
    const int prompts = std::clamp(s.button_prompts.load(), 0, BbSettings::PromptsCount - 1);
    if (ImGui::BeginCombo("Button prompts", prompt_modes[prompts])) {
        for (int i = 0; i < BbSettings::PromptsCount; ++i) {
            if (ImGui::Selectable(prompt_modes[i], i == prompts)) Store(s.button_prompts, i, true);
        }
        ImGui::EndCombo();
    }
    Section(Text("Game effects (restart required)", "Эффекты игры (после перезапуска)"));
    Hint(Text("The game's AA preference is used with the upscaler off. Temporal upscalers use their own AA. Switching between Off and a temporal upscaler requires a restart.",
              "Собственное сглаживание игры используется без апскейлера. Временные апскейлеры используют своё сглаживание. Для переключения между Off и временным апскейлером нужен перезапуск."));
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
    int fov = s.fov;
    const bool fov_changed = ImGui::SliderInt("Field of view", &fov, BbSettings::FovMin, BbSettings::FovMax,
                                           fov == BbSettings::FovDefault ? "%d (game)" : "%d");
    Store(s.fov, fov, fov_changed);
    Hint("Vertical field of view in degrees. Camera changes apply after restart.");
    const int columns = ImGui::GetContentRegionAvail().x >= ImGui::GetFontSize() * 34.0f ? 2 : 1;
    if (ImGui::BeginTable("###effects_grid", columns, ImGuiTableFlags_SizingStretchSame)) {
        for (int e = 0; e < BbSettings::EffectCount; ++e) {
            const auto& effect = BbSettings::Effects[e];
            if (std::string_view(effect.key).starts_with("cheat_")) continue;
            ImGui::TableNextColumn();
            const std::string label = std::string(Text(effect.label_en, effect.label)) + "###" + effect.key;
            Checkbox(label.c_str(), s.effects[e]);
        }
        ImGui::EndTable();
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

}


void Menu() {
    auto& s = BbSettings::Get();
    const ImGuiViewport* viewport = ImGui::GetMainViewport();
    const float scale = std::min({base_scale, viewport->WorkSize.x / 760.0f,
                                 viewport->WorkSize.y / 620.0f});
    const ImVec2 maximum(viewport->WorkSize.x - 24.0f * scale,
                        viewport->WorkSize.y - 24.0f * scale);
    const ImVec2 size(std::min(720.0f * scale, maximum.x),
                      std::min(560.0f * scale, maximum.y));
    static ImVec2 last_viewport{};
    static float last_scale = 0.0f;
    const bool resized = last_viewport.x != viewport->WorkSize.x ||
                         last_viewport.y != viewport->WorkSize.y || last_scale != scale;
    last_viewport = viewport->WorkSize;
    last_scale = scale;
    ImGui::SetNextWindowPos(ImVec2(viewport->WorkPos.x + (viewport->WorkSize.x - size.x) * 0.5f,
                                   viewport->WorkPos.y + 24.0f * scale),
                            resized ? ImGuiCond_Always : ImGuiCond_Appearing);
    ImGui::SetNextWindowSize(size, resized ? ImGuiCond_Always : ImGuiCond_Appearing);
    ImGui::SetNextWindowSizeConstraints(ImVec2(580.0f * scale, 400.0f * scale), maximum);
    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(16.0f * scale, 12.0f * scale));
    ImGui::PushStyleVar(ImGuiStyleVar_FramePadding, ImVec2(7.0f * scale, 4.0f * scale));
    ImGui::PushStyleVar(ImGuiStyleVar_ItemSpacing, ImVec2(10.0f * scale, 7.0f * scale));
    ImGui::PushStyleVar(ImGuiStyleVar_ItemInnerSpacing, ImVec2(8.0f * scale, 4.0f * scale));
    ImGui::PushStyleVar(ImGuiStyleVar_ScrollbarSize, 12.0f * scale);
    ImGui::PushStyleVar(ImGuiStyleVar_WindowRounding, 8.0f * scale);
    ImGui::PushStyleVar(ImGuiStyleVar_FrameRounding, 3.0f * scale);
    ImGui::PushStyleVar(ImGuiStyleVar_TabRounding, 4.0f * scale);
    // PushFont also scales children and popups; per-window scaling does not in ImGui 1.92.
    ImGui::PushFont(nullptr, 18.0f * scale / base_scale);
    bool keep_open = true;
    // Language-independent IDs also preserve the selected tab when the language changes.
    if (!ImGui::Begin(Text("The Crowned Workshop: settings###bbport_settings",
                           "The Crowned Workshop: настройки###bbport_settings"), &keep_open,
                      ImGuiWindowFlags_NoCollapse | ImGuiWindowFlags_NoScrollbar |
                      ImGuiWindowFlags_NoScrollWithMouse)) {
        ImGui::End();
        ImGui::PopStyleVar(8);
        ImGui::PopFont();
        if (!keep_open) SetOpen(false);
        return;
    }
    const ImVec2 mark = ImGui::GetCursorScreenPos();
    ImDrawList* draw = ImGui::GetWindowDrawList();
    const ImU32 brass = IM_COL32(214, 194, 162, 255);
    const ImVec2 crown[] = {
        {mark.x + 2 * scale, mark.y + 5 * scale},
        {mark.x + 8 * scale, mark.y + 9 * scale},
        {mark.x + 14 * scale, mark.y},
        {mark.x + 20 * scale, mark.y + 9 * scale},
        {mark.x + 26 * scale, mark.y + 5 * scale},
        {mark.x + 23 * scale, mark.y + 15 * scale},
        {mark.x + 5 * scale, mark.y + 15 * scale},
    };
    draw->AddPolyline(crown, 7, brass, ImDrawFlags_Closed, 1.5f * scale);
    draw->AddText(ImVec2(mark.x + 2 * scale, mark.y + 18 * scale), brass, "TK");
    ImGui::Dummy(ImVec2(38.0f * scale, 40.0f * scale));
    ImGui::SameLine();
    ImGui::BeginGroup();
    ImGui::TextColored(ImVec4(0.84f, 0.76f, 0.63f, 1.0f), "THE CROWNED WORKSHOP");
    const float fps = DisplayFps();
    if (s.frame_generation == BbSettings::FrameGenerationNvidia &&
        s.frame_generation_active > 1 && s.nvidia_real_fps > 0.0f)
        ImGui::TextDisabled(Text("%.0f FPS  |  %.0f real  |  %.1f ms", "%.0f FPS  |  %.0f реальных  |  %.1f мс"),
                            fps, s.nvidia_real_fps.load(), fps > 0.0f ? 1000.0f / fps : 0.0f);
    else
        ImGui::TextDisabled(Text("%.0f FPS  |  %.1f ms", "%.0f FPS  |  %.1f мс"),
                            fps, fps > 0.0f ? 1000.0f / fps : 0.0f);
    ImGui::EndGroup();

    const float footer = ImGui::GetTextLineHeightWithSpacing() +
                         ImGui::GetFrameHeightWithSpacing() +
                         ImGui::GetStyle().ItemSpacing.y * 2.0f + 2.0f * scale;
    struct Tab { const char* label; const char* child; void (*content)(); };
    const Tab tabs[] = {
        {Text("Image###image", "Картинка###image"), "###image_panel", ImageSettings},
        {Text("Frames###frames", "Кадры###frames"), "###frames_panel", FrameSettings},
        {Text("Window###window", "Окно###window"), "###window_panel", WindowSettings},
        {Text("Overlay###overlay", "Оверлей###overlay"), "###overlay_panel", OverlaySettings},
        {Text("Cheats###cheats", "Читы###cheats"), "###cheats_panel", CheatSettings},
        {Text("Effects###effects", "Эффекты###effects"), "###effects_panel", EffectSettings},
        {Text("Advanced###advanced", "Дополн.###advanced"), "###advanced_panel", AdvancedSettings},
    };
    if (ImGui::BeginTabBar("###workshop_tabs", ImGuiTabBarFlags_FittingPolicyResizeDown)) {
        for (const Tab& tab : tabs) {
            if (ImGui::BeginTabItem(tab.label)) {
                if (ImGui::BeginChild(tab.child, ImVec2(0.0f, -footer), ImGuiChildFlags_AlwaysUseWindowPadding)) {
                    // Leave a consistent right-hand caption column for combos/sliders.
                    ImGui::PushItemWidth(std::max(120.0f * scale, ImGui::GetContentRegionAvail().x - 250.0f * scale));
                    tab.content();
                    ImGui::PopItemWidth();
                }
                ImGui::EndChild();
                ImGui::EndTabItem();
            }
        }
        ImGui::EndTabBar();
    }
    ImGui::Separator();
    bool restart =
        (s.frame_generation == BbSettings::FrameGenerationNvidia && !s.startup_workshop_nvidia) ||
        (s.startup_workshop_nvidia && s.frame_generation >= BbSettings::FrameGenerationNativeFsr) ||
        (!s.startup_workshop_nvidia && (s.reflex != s.startup_reflex || s.amd_antilag != s.startup_amd_antilag)) ||
        s.object_motion != s.startup_object_motion ||
                   ((s.upscaler == BbSettings::UpscalerOff) != (s.startup_upscaler == BbSettings::UpscalerOff)) ||
                   s.nvidia_fg_mod != s.startup_nvidia_fg_mod ||
                   s.nvidia_fg_preset != s.startup_nvidia_fg_preset ||
                   s.model_lod != s.startup_model_lod ||
                   s.fov != s.startup_fov ||
                   s.live_resolution != s.startup_live_resolution ||
                   s.fps_mode != s.startup_fps_mode || s.frame_cap != s.startup_frame_cap ||
                   BbSettings::ResolutionNeedsRestart();
    for (int e = 0; e < BbSettings::EffectCount; ++e) {
        restart |= s.effects[e] != s.startup_effects[e];
    }
    if (restart)
        ImGui::TextColored(ImVec4(0.84f, 0.76f, 0.63f, 1.0f), "%s",
                          Text("Some changes require a restart", "Некоторые изменения требуют перезапуска"));
    else
        ImGui::TextDisabled("%s", Text("Changes are saved when you close the menu",
                                       "Изменения сохраняются при закрытии меню"));
    if (ImGui::Button(Text("Close###close", "Закрыть###close"))) keep_open = false;
    if (restart) {
        ImGui::SameLine();
        if (ImGui::Button(Text("Apply and restart###restart", "Применить и перезапустить###restart"))) {
            BbSettings::Save();
            runtime_restart();
        }
    }
    // Issues #74, #116: leaving the game from the pad (this menu opens with L3+R3). A second
    // press confirms; the window thread then closes like the window's own close button.
    // (From bbport 0.51.)
    static bool quit_armed;
    ImGui::SameLine();
    // One ID for both labels ("###bb_quit"): with a new ID the button lost the pad's or keyboard's
    // focus at the first press, which disarmed it at once.
    if (ImGui::Button(quit_armed ? "Press again to quit###bb_quit" : "Quit game###bb_quit")) {
        if (quit_armed) {
            SDL_Event quit{};
            quit.type = SDL_EVENT_QUIT;
            SDL_PushEvent(&quit);
        }
        quit_armed = !quit_armed;
    }
    if (quit_armed && !ImGui::IsItemFocused() && !ImGui::IsItemHovered()) {
        quit_armed = false;
    }
    ImGui::SameLine();
    ImGui::TextDisabled("Insert / L3+R3");
    ImGui::End();
    ImGui::PopStyleVar(8);
    ImGui::PopFont();
    if (!keep_open) SetOpen(false);
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

const char* UpscalerLabel(int upscaler) {
    switch (upscaler) {
    case BbSettings::UpscalerFsr3: return "FSR 3.1";
    case BbSettings::UpscalerFsr4: return "FSR 4";
    case BbSettings::UpscalerFsr411: return "FSR 4.1.1";
    case BbSettings::UpscalerFsr412: return "FSR 4.1.2";
    case BbSettings::UpscalerTaa: return "TAA";
    case BbSettings::UpscalerDlss: return "DLSS";
    default: return "";
    }
}

// The upscaler's vendor colour, as the vendors brand them.
// TODO(port): Intel XeSS (blue, #0068B5) when it is implemented: add the enum value in
// bbport_settings.h and a case here.
ImVec4 UpscalerColor(int upscaler) {
    switch (upscaler) {
    case BbSettings::UpscalerDlss:
        return ImVec4(0.55f, 0.90f, 0.30f, 1.0f); // NVIDIA green
    case BbSettings::UpscalerFsr3:
    case BbSettings::UpscalerFsr4:
    case BbSettings::UpscalerFsr411:
    case BbSettings::UpscalerFsr412:
        return ImVec4(0.95f, 0.40f, 0.35f, 1.0f); // AMD red
    default:
        return ImVec4(0.75f, 0.75f, 0.75f, 1.0f); // TAA, off: no vendor
    }
}

/// The processor name Windows shows in System settings, read once (a reference: the counter asks
/// for it every frame).
const std::string& CpuName() {
#if defined(_WIN32)
    static const std::string name = [] {
        wchar_t buffer[256]{};
        DWORD bytes = sizeof(buffer);
        if (RegGetValueW(HKEY_LOCAL_MACHINE, L"HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0",
                         L"ProcessorNameString", RRF_RT_REG_SZ, nullptr, buffer, &bytes) !=
            ERROR_SUCCESS) {
            return std::string{};
        }
        char utf8[512]{};
        const int length =
            WideCharToMultiByte(CP_UTF8, 0, buffer, -1, utf8, sizeof(utf8), nullptr, nullptr);
        return std::string(utf8, length > 1 ? size_t(length - 1) : 0);
    }();
    return name;
#else
    static const std::string name;
    return name;
#endif
}

std::string gpu_name; ///< the Vulkan device's model name, set in Init
u32 output_width = 0, output_height = 0; ///< the presented size, set in Render

// A dim label, with every value starting in the same column (the reference overlay's look). The
// column is measured, not a constant: a longer label or a larger UI scale would otherwise crowd a
// value or clip it.
void Label(const char* text, float column) {
    ImGui::TextDisabled("%s", text);
    ImGui::SameLine(column);
}

// Frame-time graph: the last four seconds as a filled curve, milliseconds on the left, the same
// heights read as FPS on the right. Auto-ranged like a scope, no fixed reference lines: the axes
// carry the scale. Each axis gets a gutter sized from its own widest tick, and the plot is inset by
// half a line top and bottom, so no number sits on the curve or gets cut by the box.
void FrameTimeGraph(float average_ms) {
    char text[32];
    const float font = ImGui::GetFontSize();
    const float unit = 4.0f * base_scale;
    // The samples in ring order, oldest first. frame_history_next is the next slot to write, so the
    // oldest stored one is frame_history_count back from it (not next itself: it is unwritten until
    // the ring has filled once).
    const size_t oldest =
        (frame_history_next + FrameHistorySize - frame_history_count) % FrameHistorySize;
    float lo = frame_history[oldest];
    float hi = lo;
    for (size_t i = 1; i < frame_history_count; ++i) {
        const float ms = frame_history[(oldest + i) % FrameHistorySize];
        lo = std::min(lo, ms);
        hi = std::max(hi, ms);
    }
    // At least 4 ms of span, so a steady scene does not zoom into noise.
    if (hi - lo < 4.0f) {
        const float mid = 0.5f * (lo + hi);
        lo = mid - 2.0f;
        hi = mid + 2.0f;
    }
    lo = std::max(lo - 0.4f, 0.0f);
    hi += 0.4f;

    const float ticks[3] = {lo, 0.5f * (lo + hi), hi};
    float gutter_l = 0.0f, gutter_r = 0.0f;
    for (const float ms : ticks) {
        std::snprintf(text, sizeof(text), "%.1f", double(ms));
        gutter_l = std::max(gutter_l, ImGui::CalcTextSize(text).x);
        std::snprintf(text, sizeof(text), "%.0f", double(ms > 0.0f ? 1000.0f / ms : 0.0f));
        gutter_r = std::max(gutter_r, ImGui::CalcTextSize(text).x);
    }
    gutter_l += unit * 2.0f;
    gutter_r += unit * 2.0f;

    const float plot_w = 210.0f * base_scale;
    const float vpad = font * 0.5f + unit; // half a line above and below the plot
    const float w = gutter_l + plot_w + gutter_r;
    const float h = 60.0f * base_scale + 2.0f * vpad;

    const ImVec2 origin = ImGui::GetCursorScreenPos();
    const ImVec2 end{origin.x + w, origin.y + h};
    ImGui::Dummy(ImVec2(w, h));
    ImDrawList* draw = ImGui::GetWindowDrawList();
    const ImVec2 plot_min{origin.x + gutter_l, origin.y + vpad};
    const ImVec2 plot_max{end.x - gutter_r, end.y - vpad};
    IM_ASSERT(plot_max.x > plot_min.x && plot_max.y > plot_min.y); // gutters fit in the box
    const float plot_h = plot_max.y - plot_min.y;
    const ImVec4 tone = PaceColor(average_ms);
    const ImU32 line = ImGui::ColorConvertFloat4ToU32(tone);
    const ImU32 fill_top = ImGui::ColorConvertFloat4ToU32(ImVec4(tone.x, tone.y, tone.z, 0.35f));
    const ImU32 fill_bottom = ImGui::ColorConvertFloat4ToU32(ImVec4(tone.x, tone.y, tone.z, 0.02f));
    const ImU32 grid = ImGui::ColorConvertFloat4ToU32(ImVec4(1.0f, 1.0f, 1.0f, 0.08f));
    const bool plain = PlainCounter();
    const ImU32 ms_text = ImGui::ColorConvertFloat4ToU32(plain ? PlainValue : ImVec4(0.62f, 0.80f, 0.92f, 1.0f));
    const ImU32 fps_text = ImGui::ColorConvertFloat4ToU32(plain ? PlainValue : ImVec4(0.55f, 0.95f, 0.55f, 1.0f));

    draw->AddRectFilled(origin, end, ImGui::ColorConvertFloat4ToU32(ImVec4(0, 0, 0, 0.42f)),
                        4.0f * base_scale);
    const auto y_for = [&](float ms) {
        return plot_max.y - plot_h * (ms - lo) / (hi - lo);
    };
    for (int tick = 2; tick >= 0; --tick) {
        const float y = y_for(ticks[tick]);
        draw->AddLine(ImVec2(plot_min.x, y), ImVec2(plot_max.x, y), grid, 1.0f);
        std::snprintf(text, sizeof(text), "%.1f", double(ticks[tick]));
        draw->AddText(ImVec2(origin.x + unit, y - font * 0.5f), ms_text, text);
        std::snprintf(text, sizeof(text), "%.0f",
                      double(ticks[tick] > 0.0f ? 1000.0f / ticks[tick] : 0.0f));
        const ImVec2 size = ImGui::CalcTextSize(text);
        draw->AddText(ImVec2(end.x - unit - size.x, y - font * 0.5f), fps_text, text);
    }

    const float step = (plot_max.x - plot_min.x) / float(FrameHistorySize);
    ImVec2 points[FrameHistorySize];
    for (size_t i = 0; i < frame_history_count; ++i) {
        const size_t sample = (oldest + i) % FrameHistorySize; // oldest first
        const float x = plot_min.x + step * float(i + 1);
        points[i] = ImVec2(x, std::clamp(y_for(frame_history[sample]), plot_min.y, plot_max.y));
        draw->AddRectFilledMultiColor(ImVec2(x - step, points[i].y), ImVec2(x, plot_max.y),
                                      fill_top, fill_top, fill_bottom, fill_bottom);
    }
    draw->AddPolyline(points, int(frame_history_count), line, ImDrawFlags_None, 1.5f * base_scale);
    draw->AddCircleFilled(points[frame_history_count - 1], 2.2f * base_scale, line);
}

float counter_bottom = 12.0f;

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
                : s.upscaler == BbSettings::UpscalerFsr412 ? "FSR 4.1.2"
                : s.upscaler == BbSettings::UpscalerTaa ? "TAA"
                : s.upscaler == BbSettings::UpscalerDlss ? "DLSS"
                : s.upscaler == BbSettings::UpscalerXess ? "XeSS"
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
    char line[384];
    const float fps = DisplayFps();
    const float displayed_ms=fps>0.0f ? 1000.0f/fps : 0.0f;
    if (s.show_resolution) {
        std::snprintf(line, sizeof(line), "%.1ffps %.1fms %s  %dx%d>%dx%d", fps, displayed_ms, upscaler,
                      s.active_render_width.load(), s.active_render_height.load(),
                      s.active_output_width.load(), s.active_output_height.load());
    } else {
        if (s.show_frame_generation || s.show_fg_preset || s.show_latency)
            std::snprintf(line,sizeof(line),"%.1ffps %.1fms %s",fps,displayed_ms,upscaler);
        else std::snprintf(line, sizeof(line), Text("%.0f FPS  %.1f ms  %s", "%.0f FPS  %.1f мс  %s"),
                           fps, displayed_ms, upscaler);
    }
    const auto append=[&](const char* detail) {
        const size_t length=std::strlen(line);
        std::snprintf(line+length,sizeof(line)-length," %s",detail);
    };
    if (s.show_frame_generation) {
        char detail[48];
        const int active=s.frame_generation_active;
        if (s.frame_generation==BbSettings::FrameGenerationOff) append("FG:off");
        else {
            const char* mode=(s.frame_generation==BbSettings::FrameGenerationNvidia || s.frame_generation==BbSettings::FrameGenerationNativeDlss) ? "NV" : "FSR";
            if (active>1) std::snprintf(detail,sizeof(detail),"FG:%s%dx",mode,active);
            else std::snprintf(detail,sizeof(detail),"FG:%s wait",mode);
            append(detail);
        }
    }
    if (s.show_fg_preset && s.frame_generation==BbSettings::FrameGenerationNvidia) {
        char detail[48];
        BbNvidia::Preset::FormatLabel(detail,sizeof(detail),s.frame_generation_active>1,
            s.nvidia_fg_reported_preset,s.nvidia_fg_profile_preset,s.nvidia_fg_feedback.load()&BbNvidia::Preset::ErrorMask);
        append(detail);
    }
    if (s.show_latency) {
        char detail[48];
        const float latency=s.pc_latency_ms;
        if (latency>=0.0f) std::snprintf(detail,sizeof(detail),"PC:%.1fms",latency);
        else std::snprintf(detail,sizeof(detail),"PC:N/A");
        append(detail);
    }
    if (s.show_resolution || s.show_frame_generation || s.show_fg_preset || s.show_latency) {
        // Extra fields stay on one row. Preserve the usual font unless a fit is needed.
        const float width=s.show_frame_generation || s.show_fg_preset || s.show_latency ? 520.0f : 420.0f;
        const float limit=std::min(width*base_scale,viewport->WorkSize.x-pad*2.0f);
        const float natural=ImGui::CalcTextSize(line).x;
        // Extra fields may need slightly more room than resolution alone.
        const float floor=s.show_frame_generation || s.show_fg_preset || s.show_latency ? 0.80f : 0.85f;
        const float ratio=std::clamp((limit-ImGui::GetStyle().WindowPadding.x*2.0f-2.0f) /
                                     std::max(natural,1.0f),floor,1.0f);
        // ImGui rounds font sizes to pixels; a fractional fit can round back
        // up and overflow the requested width. Choose a whole pixel size first.
        const float font=ImGui::GetFontSize();
        ImGui::SetWindowFontScale(std::max(std::ceil(font*floor),std::floor(font*ratio))/font);
    }
    ImGui::TextUnformatted(line);
    ImGui::SetWindowFontScale(1.0f);
    if (s.show_frametime_graph) {
        // A shallow trace under the existing row, bounded to the same compact OSD.
        const float limit=std::min(520.0f*base_scale,viewport->WorkSize.x-pad*2.0f);
        const float width=std::clamp(ImGui::CalcTextSize(line).x,300.0f*base_scale,
                                    std::max(300.0f*base_scale,limit-ImGui::GetStyle().WindowPadding.x*2.0f));
        char caption[96];
        if (real_frame_history.Size()) {
            std::snprintf(caption,sizeof(caption),Text("Real: %.1fms | peak %.1fms", "Реал.: %.1fмс | пик %.1fмс"),
                          real_frame_history.Latest(),real_frame_history.Peak());
        } else {
            std::snprintf(caption,sizeof(caption),"%s",Text("Real frames: waiting", "Реальные кадры: ожидание"));
        }
        ImGui::SetWindowFontScale(0.85f);
        ImGui::TextDisabled("%s",caption);
        ImGui::SetWindowFontScale(1.0f);
        ImGui::PushStyleColor(ImGuiCol_PlotLines,ImVec4(0.84f,0.70f,0.43f,1.0f));
        ImGui::PlotLines("##real_frametime",[](void* data,int index) {
            return static_cast<BbFrameMetrics::RealFrameHistory*>(data)->At(std::size_t(index));
        },&real_frame_history,int(real_frame_history.Size()),0,nullptr,0.0f,
            real_frame_history.PlotCeiling(),ImVec2(width,32.0f*base_scale));
        ImGui::PopStyleColor();
    }
    counter_bottom = ImGui::GetWindowPos().y + ImGui::GetWindowSize().y - viewport->WorkPos.y + 8.0f * base_scale;
    ImGui::End();
}

void SystemCounter() {
    const auto& options = BbSettings::Get();
    if (!(options.show_frame_times || options.show_render_latency || options.show_vram || options.show_gpu ||
          options.show_cpu || options.show_ram || options.show_fps_graph)) return;
    const ImGuiViewport* viewport = ImGui::GetMainViewport();
    const float pad = 12.0f * base_scale;
    ImGui::SetNextWindowPos(ImVec2(viewport->WorkPos.x + viewport->WorkSize.x - pad,
                                   viewport->WorkPos.y + counter_bottom),
                            ImGuiCond_Always, ImVec2(1.0f, 0.0f));
    ImGui::SetNextWindowBgAlpha(0.5f);
    ImGui::Begin("##system_readouts", nullptr,
                 ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_AlwaysAutoResize |
                     ImGuiWindowFlags_NoInputs | ImGuiWindowFlags_NoNav |
                     ImGuiWindowFlags_NoFocusOnAppearing);
    const auto& s = BbSettings::Get();
    const ImVec4 pace = PaceColor(frame_ms_avg);
    const float model_gap = 8.0f * base_scale;
    const double rate = frame_ms_avg > 0.0f ? 1000.0 / frame_ms_avg : 0.0;
    constexpr double gb = 1024.0 * 1024.0 * 1024.0;
    // One value column for the whole panel, as wide as the longest label it can show plus a gap.
    // Measured and constant, so values line up and never move when a switch is flipped.
    float column = 0.0f;
    for (const char* label : {"FPS:", "Frame:", "Latency:", "VRAM:", "GPU:", "CPU:", "RAM:"}) {
        column = std::max(column, ImGui::CalcTextSize(label).x);
    }
    column += 10.0f * base_scale;

    if (s.show_frame_times) {
        Label("Frame:", column);
        ImGui::PushStyleColor(ImGuiCol_Text, pace);
        ImGui::Text("%.1f ms", frame_ms_avg);
        ImGui::PopStyleColor();
    }
    // Render latency, its own line (it sat under FPS, where players took it for the frame time):
    // from the game starting a frame to its present (vk_low_latency.cpp), and the low latency mode.
    if (s.show_render_latency) {
        static const char* modes[] = {"Low latency off", "Reflex", "Reflex + Boost", "Anti-Lag 2",
                                      "Low latency"};
        const int mode = std::clamp(s.latency_mode.load(), 0, 4);
        Label("Latency:", column);
        if (const float latency = s.latency_ms.load(std::memory_order_relaxed); latency > 0.0f) {
            ImGui::Text("%.1f ms", double(latency));
        } else {
            ImGui::TextDisabled("--");
        }
        ImGui::SameLine(0.0f, model_gap);
        ImGui::TextDisabled("|  render latency, %s", modes[mode]);
    }
    // Video memory in use, against the limit the collector holds itself to: the same numbers the
    // low-memory warning reports. 0, so nothing shown, until the first collector pass.
    const u64 used = vram_used.load(std::memory_order_relaxed);
    if (s.show_vram && used != 0) {
        const u64 limit = vram_limit.load(std::memory_order_relaxed);
        Label("VRAM:", column);
        ImGui::PushStyleColor(ImGuiCol_Text,
                             VramColor(used, vram_pressure.load(std::memory_order_relaxed),
                                       vram_critical.load(std::memory_order_relaxed)));
        if (limit != 0) {
            ImGui::Text("%.1f / %.1f GB", double(used) / gb, double(limit) / gb);
        } else {
            ImGui::Text("%.1f GB", double(used) / gb);
        }
        ImGui::PopStyleColor();
        // The card's own headroom: the limit above is the port's conservative budget, so without
        // this "4.6 of 4.6" reads as "the card is full" when it is not.
        ImGui::SameLine(0.0f, 8.0f * base_scale);
        ImGui::TextDisabled("(card: %.1f GB free)",
                            double(vram_card_free.load(std::memory_order_relaxed)) / gb);
    }
    if (s.show_gpu) {
        Label("GPU:", column);
        const float gpu = Load().gpu.load(std::memory_order_relaxed);
        if (gpu < 0.0f) {
            ImGui::TextDisabled("--");
        } else {
            ImGui::TextColored(LoadColor(gpu, 90.0f, 97.0f), "%.0f%%", double(gpu));
        }
        if (!gpu_name.empty()) {
            ImGui::SameLine(0.0f, model_gap);
            ImGui::TextDisabled("%s", gpu_name.c_str());
        }
    }
    if (s.show_cpu) {
        Label("CPU:", column);
        const float cpu = Load().cpu.load(std::memory_order_relaxed);
        if (cpu < 0.0f) {
            ImGui::TextDisabled("--");
        } else {
            ImGui::TextColored(LoadColor(cpu, 70.0f, 90.0f), "%.0f%%", double(cpu));
        }
        const std::string& model = CpuName();
        if (!model.empty()) {
            ImGui::SameLine(0.0f, model_gap);
            ImGui::TextDisabled("%s", model.c_str());
        }
    }
    if (s.show_ram) {
        Label("RAM:", column);
        const u64 ram = Load().ram.load(std::memory_order_relaxed);
        if (ram == 0) {
            ImGui::TextDisabled("--");
        } else {
            ImGui::Text("%.1f GB", double(ram) / gb);
            // The machine's headroom, like the VRAM row's card figure: the game's working set on
            // its own looks like it is eating all the memory.
            const u64 free = Load().ram_free.load(std::memory_order_relaxed);
            if (free != 0) {
                ImGui::SameLine(0.0f, 8.0f * base_scale);
                ImGui::TextDisabled("(%.1f GB free)", double(free) / gb);
            }
        }
    }
    if (s.show_fps_graph && frame_history_count > 1) {
        FrameTimeGraph(frame_ms_avg);
        // Legend under the graph, the current values of what the line shows.
        const float square = 9.0f * base_scale;
        const ImVec2 at = ImGui::GetCursorScreenPos();
        ImGui::Dummy(ImVec2(square, square));
        ImGui::GetWindowDrawList()->AddRectFilled(at, ImVec2(at.x + square, at.y + square),
                                                  ImGui::ColorConvertFloat4ToU32(pace),
                                                  1.5f * base_scale);
        ImGui::SameLine(0.0f, 6.0f * base_scale);
        ImGui::Text("Frame: %.1f ms", frame_ms_avg);
        ImGui::SameLine(0.0f, 14.0f * base_scale);
        ImGui::TextDisabled("%.0f FPS", double(rate));
    }
    ImGui::End();
}

bool WarningActive() {
    std::scoped_lock lock{warn_mutex};
    return !warn_headline.empty() && std::chrono::steady_clock::now() < warn_until;
}

// Amber banner at the top of the screen: the player should save before the game runs out of
// video memory (nothing is blocked; the game still crashes if it has to). The headline is
// brighter than the detail so the point of the banner reads first.
void WarningBanner() {
    std::string headline, detail;
    float fraction = -1.0f;
    {
        std::scoped_lock lock{warn_mutex};
        headline = warn_headline;
        detail = warn_detail;
        fraction = warn_fraction;
    }
    const ImGuiViewport* viewport = ImGui::GetMainViewport();
    ImGui::SetNextWindowPos(ImVec2(viewport->WorkPos.x + viewport->WorkSize.x * 0.5f,
                                   viewport->WorkPos.y + 24.0f * base_scale),
                            ImGuiCond_Always, ImVec2(0.5f, 0.0f));
    ImGui::SetNextWindowBgAlpha(0.92f);
    ImGui::PushStyleColor(ImGuiCol_WindowBg, ImVec4(0.42f, 0.20f, 0.02f, 1.0f));
    ImGui::PushStyleColor(ImGuiCol_Border, ImVec4(0.95f, 0.60f, 0.20f, 1.0f));
    if (ImGui::Begin("##vram-warning", nullptr,
                     ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_AlwaysAutoResize |
                         ImGuiWindowFlags_NoInputs | ImGuiWindowFlags_NoNav |
                         ImGuiWindowFlags_NoSavedSettings |
                         ImGuiWindowFlags_NoFocusOnAppearing)) {
        ImGui::PushTextWrapPos(560.0f * base_scale);
        ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(1.00f, 0.82f, 0.45f, 1.00f));
        ImGui::TextUnformatted(headline.c_str());
        ImGui::PopStyleColor();
        if (fraction >= 0.0f) {
            // How much of the memory in use: the bar says in one glance what the numbers say.
            ImGui::PushStyleColor(ImGuiCol_PlotHistogram,
                                  fraction > 0.90f ? ImVec4(1.00f, 0.45f, 0.40f, 1.0f)
                                                   : ImVec4(1.00f, 0.72f, 0.30f, 1.0f));
            ImGui::ProgressBar(std::min(fraction, 1.0f), ImVec2(-FLT_MIN, 5.0f * base_scale), "");
            ImGui::PopStyleColor();
        }
        if (!detail.empty()) {
            ImGui::Spacing();
            ImGui::TextUnformatted(detail.c_str());
        }
        ImGui::PopTextWrapPos();
    }
    ImGui::End();
    ImGui::PopStyleColor(2);
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
    gpu_name = std::string(instance.GetModelName());
    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGuiIO& io = ImGui::GetIO();
    io.IniFilename = nullptr; // window positions are not kept
    io.ConfigFlags |= ImGuiConfigFlags_NavEnableKeyboard | ImGuiConfigFlags_NavEnableGamepad;
    io.BackendFlags |= ImGuiBackendFlags_HasGamepad;
    io.BackendPlatformName = "bbport";

    ImGui::StyleColorsDark();
    ImGuiStyle& style = ImGui::GetStyle();
    WorkshopTheme(style);

    static ImVector<ImWchar> picker_glyphs;
    ImFontGlyphRangesBuilder ranges;
    ranges.AddRanges(io.Fonts->GetGlyphRangesDefault());
    ranges.AddRanges(io.Fonts->GetGlyphRangesCyrillic());
    for (const char* text : Fsr41Ui::texts[Fsr41Ui::Language()]) ranges.AddText(text);
    ranges.BuildRanges(&picker_glyphs);
    ImFontConfig font_config;
    font_config.FontDataOwnedByAtlas = false;
    io.Fonts->AddFontFromMemoryTTF(const_cast<unsigned char*>(bb_font_ttf),
                                   int(bb_font_ttf_end - bb_font_ttf), 18.0f, &font_config, picker_glyphs.Data);

#ifdef _WIN32
    if (const char* windows=std::getenv("WINDIR")) {
        const std::string language=Fsr41Ui::languages[Fsr41Ui::Language()];
        const char* candidates[] = {"msyh.ttc","YuGothM.ttc","msgothic.ttc","malgun.ttf"};
        if (language=="zh" || language=="ja" || language=="ko") for(const char* file:candidates) {
            const auto path=std::filesystem::path(windows)/"Fonts"/file;
            if(!std::filesystem::is_regular_file(path)) continue;
            ImFontConfig merge; merge.MergeMode=true;
            io.Fonts->AddFontFromFileTTF(path.string().c_str(),18.f,&merge,picker_glyphs.Data);
        }
    }
#endif
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
    info.Queue = instance.GetPresentQueue();
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
    std::printf("Overlay: menu ready (%s)\n", MenuOpeners().c_str());
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
        // Clear even a short pause: rendering may stop before another unfocused
        // present is recorded, so its duration must not appear as a gameplay hitch.
        real_frame_history.Reset();
        if (event.type == SDL_EVENT_WINDOW_FOCUS_LOST) l3_down = r3_down = false;
        return false; // WindowSDL also updates the background frame-cap policy.
    case SDL_EVENT_KEY_DOWN:
    case SDL_EVENT_KEY_UP: {
        const bool down = event.type == SDL_EVENT_KEY_DOWN;
        const bool menu_key = MenuKey() != SDLK_UNKNOWN && event.key.key == MenuKey();
        if (down && !event.key.repeat && (menu_key || (is_open && event.key.key == SDLK_ESCAPE))) {
            SetOpen(menu_key ? !is_open : false);
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
        } else if (button == SDL_GAMEPAD_BUTTON_BACK) {
            back_down = down;
        } else if (button == SDL_GAMEPAD_BUTTON_START) {
            start_down = down;
        }
        const MenuPad pad = MenuPadCombo();
        if (down && ((pad == MenuPad::L3R3 && l3_down && r3_down) ||
                     (pad == MenuPad::BackStart && back_down && start_down))) {
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

// Any of the counter's readouts asked for (the graph lives in the same window).
bool ReadoutsOn() {
    const auto& s = BbSettings::Get();
    return s.show_fps || s.show_frame_times || s.show_render_latency || s.show_vram || s.show_gpu ||
           s.show_cpu || s.show_ram || s.show_fps_graph;
}

bool Visible() {
    return initialized &&
           (menu_open || text_entry_active || WarningActive() || ReadoutsOn());
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

void RecordPresent(bool real_frame, bool presented) {
    BbHitch::Present(real_frame,presented,BbSettings::Get().window_focused);
    std::scoped_lock lock{imgui_mutex};
    if (!initialized) return;
    if (!presented || !BbSettings::Get().window_focused) {
        real_frame_history.Reset();
    } else if (real_frame) {
        real_frame_history.Present();
    }
}

void Warn(const std::string& headline, const std::string& detail, float used_fraction) {
    std::scoped_lock lock{warn_mutex};
    warn_headline = headline;
    warn_detail = detail;
    warn_fraction = used_fraction;
    warn_until = std::chrono::steady_clock::now() + std::chrono::seconds(10);
}

void SetVramUsage(u64 used_bytes, u64 limit_bytes, u64 pressure_bytes, u64 critical_bytes,
                  u64 card_free_bytes) {
    vram_used.store(used_bytes, std::memory_order_relaxed);
    vram_limit.store(limit_bytes, std::memory_order_relaxed);
    vram_pressure.store(pressure_bytes, std::memory_order_relaxed);
    vram_critical.store(critical_bytes, std::memory_order_relaxed);
    vram_card_free.store(card_free_bytes, std::memory_order_relaxed);
}

// Called for every presented image: the interval for the FPS readout and BB_FPS_LOG.
void NotePresent() {
    const auto now = std::chrono::steady_clock::now();
    const float ms = std::chrono::duration<float, std::milli>(now - last_present).count();
    last_present_ms = ms;
    last_present = now;
    if (ms > 0.0f && ms < 1000.0f) {
        frame_ms_avg = frame_ms_avg == 0.0f ? ms : frame_ms_avg * 0.95f + ms * 0.05f;
        frame_history[frame_history_next] = ms;
        frame_history_next = (frame_history_next + 1) % FrameHistorySize;
        frame_history_count = std::min(frame_history_count + 1, FrameHistorySize);
    }
    // CPU and RAM at 4 Hz (syscalls, and neither changes between two frames); the GPU reading
    // has its own thread, started the first time the readout is asked for.
    static auto last_sample = now;
    if (now - last_sample >= std::chrono::milliseconds(250)) {
        last_sample = now;
        SampleCpu();
        Load().ram.store(BbProcessMemory::Get().working_set, std::memory_order_relaxed);
        Load().ram_free.store(AvailableMemory(), std::memory_order_relaxed);
        if (BbSettings::Get().show_gpu) {
            StartGpuSampler();
        }
    }
    // BB_FPS_LOG=1: presents per second and the slowest frame, every 5 seconds (test runs).
    static const bool fps_log = [] {
        const char* env = std::getenv("BB_FPS_LOG");
        return env && env[0] == '1';
    }();
    if (fps_log) {
        static auto window_start = now;
        static int frames = 0;
        static float worst = 0.0f;
        ++frames;
        worst = std::max(worst, ms < 1000.0f ? ms : 0.0f);
        const float elapsed = std::chrono::duration<float>(now - window_start).count();
        if (elapsed >= 5.0f) {
            std::printf("Frame rate: %.1f FPS, slowest frame %.1f ms\n", frames / elapsed, worst);
            window_start = now;
            frames = 0;
            worst = 0.0f;
        }
    }

}

void Render(vk::CommandBuffer cmdbuf, vk::ImageView view, vk::Extent2D extent) {
    const float ms = last_present_ms;
    // What is actually presented: follows a window resize, unlike the configured output.
    output_width = extent.width;
    output_height = extent.height;
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
    if (ReadoutsOn() && !menu_open) {
        counter_bottom = 12.0f * base_scale;
        FpsCounter();
        SystemCounter();
    }
    if (text_entry_active) {
        TextEntryBox();
    }
    if (WarningActive()) {
        WarningBanner();
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
        // Font atlas uploads use the same queue as this presentation pass.
        std::scoped_lock submit_lock{Vulkan::Scheduler::submit_mutex};
        ImGui_ImplVulkan_RenderDrawData(ImGui::GetDrawData(), cmdbuf);
    }
    cmdbuf.endRendering();
}

} // namespace BbOverlay
