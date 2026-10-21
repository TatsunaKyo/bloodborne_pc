// SPDX-FileCopyrightText: Copyright 2024 shadPS4 Emulator Project
// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
// SPDX-License-Identifier: GPL-2.0-or-later

#pragma once

#include <span>
#include <shared_mutex>
#include <stdexcept>

#include "common/types.h"
#include "video_core/renderer_vulkan/vk_common.h"

namespace Vulkan {
std::shared_mutex& DriverCacheMutex();
void SaveDriverCaches();
struct CacheLoadError : std::runtime_error {
  using std::runtime_error::runtime_error;
};

/**
 * @brief Creates a vulkan shader module from SPIR-V bytecode.
 * @param code The SPIR-V bytecode data.
 * @param device The vulkan device handle
 */
vk::ShaderModule CompileSPV(std::span<const u32> code, vk::Device device,
                            bool preloading = false);

} // namespace Vulkan
