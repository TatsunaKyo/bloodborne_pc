// SPDX-FileCopyrightText: Copyright 2024 shadPS4 Emulator Project
// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
// SPDX-License-Identifier: GPL-2.0-or-later

#include "video_core/renderer_vulkan/vk_shader_util.h"
#include "common/assert.h"
#include "common/cache_blob.h"

namespace Vulkan {

vk::ShaderModule CompileSPV(std::span<const u32> code, vk::Device device,
                            bool preloading) {
  if (preloading && !Storage::Blob::WellFormedSpirv(code)) {
    throw CacheLoadError("Malformed cached SPIR-V");
  }
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
