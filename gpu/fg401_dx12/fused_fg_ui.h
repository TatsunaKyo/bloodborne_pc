// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "common/types.h"
#include "video_core/renderer_vulkan/vk_common.h"
namespace Vulkan {
class Instance;
class FusedFgUi {
  public:
    explicit FusedFgUi(const Instance &instance);
    void Record(vk::CommandBuffer command, vk::Image output, vk::ImageView output_view,
                vk::Image generated, vk::ImageView generated_view, vk::ImageView color,
                vk::ImageView hudless, u32 width, u32 height) const;

  private:
    vk::UniqueDescriptorSetLayout descriptors;
    vk::UniquePipelineLayout layout;
    vk::UniquePipeline pipeline;
};
} // namespace Vulkan
