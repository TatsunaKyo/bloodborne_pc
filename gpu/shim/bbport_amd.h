// SPDX-License-Identifier: GPL-2.0-or-later
// TatsunaKyo: Radeon Anti-Lag 2 through the driver's Vulkan interface.
#pragma once
#include <cstdint>
#ifndef VK_ENABLE_BETA_EXTENSIONS
#define VK_ENABLE_BETA_EXTENSIONS
#endif
#ifndef VK_NO_PROTOTYPES
#define VK_NO_PROTOTYPES
#endif
#include <vulkan/vulkan_core.h>

namespace BbAmd {
struct FrameToken {
    uint64_t index{}, epoch{};
};
bool QueryFeature(VkPhysicalDevice physical, bool amd, bool extension,
                  PFN_vkGetPhysicalDeviceFeatures2 query);
void BindDevice(VkDevice device, bool feature_enabled, PFN_vkGetDeviceProcAddr resolve);
void Shutdown();
// Called before sampling the pad, once for each real simulation/flip.
void BeforeInput();
void QueueFlip(int index, int64_t argument);
void CancelFlip(int index, int64_t argument);
FrameToken FinishRender(int index, int64_t argument);
// Interpolated frames and redisplays must not become new simulation frames.
void BeforePresent(FrameToken token, bool new_real_frame);
}
