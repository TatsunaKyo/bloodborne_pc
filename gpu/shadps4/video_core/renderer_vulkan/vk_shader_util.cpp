// SPDX-FileCopyrightText: Copyright 2024 shadPS4 Emulator Project
// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
// SPDX-License-Identifier: GPL-2.0-or-later

#include "video_core/renderer_vulkan/vk_shader_util.h"
#include "common/assert.h"
#include "common/cache_blob.h"
#include "shader_recompiler/motion_address.h"
#include "shader_recompiler/push_data_upgrade.h"

namespace Vulkan {
std::shared_mutex& DriverCacheMutex() { static auto* mutex = new std::shared_mutex; return *mutex; }

vk::ShaderModule CompileSPV(std::span<const u32> code, vk::Device device,
                            bool preloading) {
  if (preloading && !Storage::Blob::WellFormedSpirv(code)) {
    throw CacheLoadError("Malformed cached SPIR-V");
  }
  std::vector<u32> upgraded;
  if (!Shader::PushLayout::Upgrade(code, upgraded)) {
    if (preloading) throw CacheLoadError("Malformed cached push layout");
    ASSERT_MSG(false, "Malformed push layout");
  }
  if (!upgraded.empty()) code = upgraded;
  std::vector<u32> linked;
  const auto result = Shader::MotionAddress::Link(code, linked);
  if (result == Shader::MotionAddress::Result::Invalid) {
    if (preloading) throw CacheLoadError("Invalid cached motion-address relocations");
    ASSERT_MSG(false, "Invalid motion-address relocations");
  }
  if (result == Shader::MotionAddress::Result::Linked) code = linked;
  const vk::ShaderModuleCreateInfo shader_info = {
      .codeSize = code.size() * sizeof(u32),
      .pCode = code.data(),
  };

  auto [module_result, module] = device.createShaderModule(shader_info);
  if (preloading && module_result != vk::Result::eSuccess) {
    throw CacheLoadError("Driver rejected cached SPIR-V");
  }
  ASSERT_MSG(module_result == vk::Result::eSuccess,
             "Failed to compile SPIR-V shader: {}",
             vk::to_string(module_result));
  return module;
}

} // namespace Vulkan
