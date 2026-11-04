// SPDX-License-Identifier: GPL-2.0-or-later
#include "fused_fg_ui.h"
#include "video_core/host_shaders/frame_gen_fused_ui_comp.h"
#include "video_core/renderer_vulkan/vk_instance.h"
#include "video_core/renderer_vulkan/vk_shader_util.h"
#include <array>
namespace Vulkan {
FusedFgUi::FusedFgUi(const Instance &instance) {
    const auto device = instance.GetDevice();
    const std::array<vk::DescriptorSetLayoutBinding, 4> bindings{
        {{0, vk::DescriptorType::eStorageImage, 1, vk::ShaderStageFlagBits::eCompute},
         {1, vk::DescriptorType::eSampledImage, 1, vk::ShaderStageFlagBits::eCompute},
         {2, vk::DescriptorType::eSampledImage, 1, vk::ShaderStageFlagBits::eCompute},
         {3, vk::DescriptorType::eSampledImage, 1, vk::ShaderStageFlagBits::eCompute}}};
    descriptors = Check(device.createDescriptorSetLayoutUnique(
        {.flags = vk::DescriptorSetLayoutCreateFlagBits::ePushDescriptorKHR,
         .bindingCount = u32(bindings.size()),
         .pBindings = bindings.data()}));
    const vk::PushConstantRange push{vk::ShaderStageFlagBits::eCompute, 0, 2 * sizeof(s32)};
    layout = Check(device.createPipelineLayoutUnique({.setLayoutCount = 1,
                                                      .pSetLayouts = &*descriptors,
                                                      .pushConstantRangeCount = 1,
                                                      .pPushConstantRanges = &push}));
    const auto module = CompileSPV(FRAME_GEN_FUSED_UI_COMP, device);
    pipeline = Check(device.createComputePipelineUnique(
        {}, vk::ComputePipelineCreateInfo{.stage = {.stage = vk::ShaderStageFlagBits::eCompute,
                                                    .module = module,
                                                    .pName = "main"},
                                          .layout = *layout}));
    device.destroyShaderModule(module);
}
void FusedFgUi::Record(vk::CommandBuffer command, vk::Image output, vk::ImageView output_view,
                       vk::Image generated, vk::ImageView generated_view, vk::ImageView color,
                       vk::ImageView hudless, u32 width, u32 height) const {
    std::array<vk::ImageMemoryBarrier2, 2> barriers{};
    for (u32 i = 0; i < 2; ++i)
        barriers[i] = {.srcStageMask = vk::PipelineStageFlagBits2::eAllCommands,
                       .srcAccessMask =
                           vk::AccessFlagBits2::eMemoryRead | vk::AccessFlagBits2::eMemoryWrite,
                       .dstStageMask = vk::PipelineStageFlagBits2::eComputeShader,
                       .dstAccessMask =
                           i ? vk::AccessFlagBits2::eShaderRead : vk::AccessFlagBits2::eShaderWrite,
                       .oldLayout = vk::ImageLayout::eGeneral,
                       .newLayout = vk::ImageLayout::eGeneral,
                       .image = i ? generated : output,
                       .subresourceRange = {vk::ImageAspectFlagBits::eColor, 0, 1, 0, 1}};
    command.pipelineBarrier2(
        {.imageMemoryBarrierCount = u32(barriers.size()), .pImageMemoryBarriers = barriers.data()});
    const std::array<vk::DescriptorImageInfo, 4> infos{
        {{.imageView = output_view, .imageLayout = vk::ImageLayout::eGeneral},
         {.imageView = color, .imageLayout = vk::ImageLayout::eGeneral},
         {.imageView = hudless, .imageLayout = vk::ImageLayout::eGeneral},
         {.imageView = generated_view, .imageLayout = vk::ImageLayout::eGeneral}}};
    std::array<vk::WriteDescriptorSet, 4> writes{};
    for (u32 i = 0; i < 4; ++i)
        writes[i] = {.dstBinding = i,
                     .descriptorCount = 1,
                     .descriptorType =
                         i ? vk::DescriptorType::eSampledImage : vk::DescriptorType::eStorageImage,
                     .pImageInfo = &infos[i]};
    const std::array<s32, 2> size{s32(width), s32(height)};
    command.bindPipeline(vk::PipelineBindPoint::eCompute, *pipeline);
    command.pushDescriptorSetKHR(vk::PipelineBindPoint::eCompute, *layout, 0, writes);
    command.pushConstants(*layout, vk::ShaderStageFlagBits::eCompute, 0, sizeof(size), size.data());
    command.dispatch((width + 7) / 8, (height + 7) / 8, 1);
}
} // namespace Vulkan
