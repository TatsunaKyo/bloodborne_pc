// SPDX-License-Identifier: GPL-2.0-or-later
// TatsunaKyo revision. VK_AMD_anti_lag needs no additional vendor DLL.
#include "bbport_amd.h"
#include "bbport_settings.h"
#include <algorithm>
#include <atomic>
#include <cstdio>
#include <deque>
#include <mutex>
#include <shared_mutex>

namespace BbAmd {
namespace {
std::shared_mutex lifetime;
std::mutex state;
std::mutex input_serial;
std::atomic<bool> ready{};
VkDevice device{};
PFN_vkAntiLagUpdateAMD update{};
uint64_t epoch{}, next_index{};
FrameToken input;
bool input_pending{}, on{};
struct Flip { int index; int64_t argument; FrameToken token; };
std::deque<Flip> flips;

bool Wanted() {
    const auto& s = BbSettings::Get();
    return s.amd_antilag && (s.window_focused || s.background_mode == BbSettings::BackgroundRun);
}
void Send(bool enabled, const VkAntiLagPresentationInfoAMD* presentation = nullptr) {
    const VkAntiLagDataAMD data{VK_STRUCTURE_TYPE_ANTI_LAG_DATA_AMD, nullptr,
        enabled ? VK_ANTI_LAG_MODE_ON_AMD : VK_ANTI_LAG_MODE_OFF_AMD,
        0, presentation}; // VideoOut owns the real-frame cap; never cap FG's output here.
    update(device, &data);
}
}

bool QueryFeature(VkPhysicalDevice physical, bool amd, bool extension,
                  PFN_vkGetPhysicalDeviceFeatures2 query) {
    if (!amd || !extension || !query) return false;
    VkPhysicalDeviceAntiLagFeaturesAMD feature{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_ANTI_LAG_FEATURES_AMD};
    VkPhysicalDeviceFeatures2 features{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2, &feature};
    query(physical, &features);
    return feature.antiLag == VK_TRUE;
}

void BindDevice(VkDevice dev, bool enabled, PFN_vkGetDeviceProcAddr resolve) {
    std::unique_lock lock{lifetime};
    ready = false;
    device = dev;
    update = enabled && dev && resolve
        ? reinterpret_cast<PFN_vkAntiLagUpdateAMD>(resolve(dev, "vkAntiLagUpdateAMD")) : nullptr;
    {
        std::scoped_lock guard{state};
        ++epoch; input = {}; input_pending = on = false; flips.clear();
    }
    BbSettings::Get().amd_antilag_supported = update != nullptr;
    // Enabling the device feature must not implicitly enable the user's setting.
    if (update) Send(false);
    ready = update != nullptr;
    std::printf("AMD Anti-Lag 2: %s (VK_AMD_anti_lag)\n", update ? "available" : "unavailable on this GPU/driver");
}

void BeforeInput() {
    if (!ready) return;
    std::scoped_lock sampling{input_serial};
    std::shared_lock lock{lifetime};
    if (!update) return;
    FrameToken token;
    const bool enabled = Wanted();
    {
        std::scoped_lock guard{state};
        if (!enabled) {
            input_pending = false; input = {};
            if (!on) return;
            on = false;
        } else {
            if (input_pending) return; // Multiple pad reads in the same simulation.
            on = input_pending = true;
            token = input = {++next_index, epoch};
        }
    }
    const VkAntiLagPresentationInfoAMD presentation{VK_STRUCTURE_TYPE_ANTI_LAG_PRESENTATION_INFO_AMD,
        nullptr, VK_ANTI_LAG_STAGE_INPUT_AMD, token.index};
    // The driver may wait here. Present must remain able to progress on its thread.
    Send(enabled, enabled ? &presentation : nullptr);
}

void QueueFlip(int index, int64_t argument) {
    if (!ready) return;
    std::scoped_lock guard{state};
    if (input_pending) flips.push_back({index, argument, input});
    input_pending = false; input = {};
}
void CancelFlip(int index, int64_t argument) {
    std::scoped_lock guard{state};
    std::erase_if(flips, [&](const Flip& f) {return f.index == index && f.argument == argument;});
}
FrameToken FinishRender(int index, int64_t argument) {
    std::scoped_lock guard{state};
    const auto it = std::find_if(flips.begin(), flips.end(), [&](const Flip& f) {
        return f.index == index && f.argument == argument;
    });
    if (it == flips.end()) return {};
    const auto token = it->token;
    flips.erase(it);
    return token;
}
void BeforePresent(FrameToken token, bool new_real_frame) {
    if (!ready || !new_real_frame || !token.index) return;
    std::shared_lock lock{lifetime};
    if (!update || token.epoch != epoch) return;
    const VkAntiLagPresentationInfoAMD presentation{VK_STRUCTURE_TYPE_ANTI_LAG_PRESENTATION_INFO_AMD,
        nullptr, VK_ANTI_LAG_STAGE_PRESENT_AMD, token.index};
    Send(Wanted(), &presentation);
}
void Shutdown() {
    std::unique_lock lock{lifetime};
    ready = false;
    if (update) Send(false);
    update = nullptr; device = nullptr;
    std::scoped_lock guard{state};
    ++epoch; input = {}; input_pending = on = false; flips.clear();
    BbSettings::Get().amd_antilag_supported = false;
}
}
