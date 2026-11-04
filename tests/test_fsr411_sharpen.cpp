// SPDX-License-Identifier: GPL-2.0-or-later
// Compare real legacy blit+RCAS and direct FP16 RCAS, including final FP16
// output.
#include "common/types.h"
#include "video_core/host_shaders/taa_sharpen_comp.h"
#include "video_core/host_shaders/taa_sharpen_direct_comp.h"
#include "video_core/renderer_vulkan/vk_common.h"
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

int main() {
    static vk::detail::DynamicLoader loader;
    vk::detail::DispatchLoaderDynamic d;
    d.init(loader.getProcAddress<PFN_vkGetInstanceProcAddr>("vkGetInstanceProcAddr"));
    const vk::ApplicationInfo application{.pApplicationName = "Private RCAS equivalence test",
                                          .apiVersion = VK_API_VERSION_1_3};
    auto instance = vk::createInstanceUnique({.pApplicationInfo = &application}, nullptr, d).value;
    d.init(*instance);
    const auto physical = instance->enumeratePhysicalDevices(d).value.at(0);
    const auto families = physical.getQueueFamilyProperties(d);
    uint32_t family = 0;
    while (family < families.size() &&
           !(families[family].queueFlags & vk::QueueFlagBits::eGraphics)) {
        ++family;
    }
    assert(family < families.size());
    const float priority = 1.f;
    const vk::DeviceQueueCreateInfo qi{
        .queueFamilyIndex = family, .queueCount = 1, .pQueuePriorities = &priority};
    vk::PhysicalDeviceVulkan13Features features13{.synchronization2 = true};
    const vk::PhysicalDeviceFeatures features{.shaderStorageImageExtendedFormats = true};
    const char* extension = VK_KHR_PUSH_DESCRIPTOR_EXTENSION_NAME;
    auto owned_device = physical
                            .createDeviceUnique({.pNext = &features13,
                                                 .queueCreateInfoCount = 1,
                                                 .pQueueCreateInfos = &qi,
                                                 .enabledExtensionCount = 1,
                                                 .ppEnabledExtensionNames = &extension,
                                                 .pEnabledFeatures = &features},
                                                nullptr, d)
                            .value;
    const auto device = *owned_device;
    d.init(device);
    const auto queue = device.getQueue(family, 0, d);
    auto pool =
        device
            .createCommandPoolUnique({.flags = vk::CommandPoolCreateFlagBits::eResetCommandBuffer,
                                      .queueFamilyIndex = family},
                                     nullptr, d)
            .value;
    auto commands = device
                        .allocateCommandBuffersUnique({.commandPool = *pool,
                                                       .level = vk::CommandBufferLevel::ePrimary,
                                                       .commandBufferCount = 1},
                                                      d)
                        .value;
    const auto cmd = *commands[0];
    auto fence = device.createFenceUnique({}, nullptr, d).value;
    const auto memory_properties = physical.getMemoryProperties(d);
    const auto memory_type = [&](uint32_t bits, vk::MemoryPropertyFlags flags,
                                 vk::MemoryPropertyFlags preferred = vk::MemoryPropertyFlags{}) {
        for (const auto wanted : {flags | preferred, flags}) {
            for (uint32_t i = 0; i < memory_properties.memoryTypeCount; ++i) {
                if ((bits & (1u << i)) &&
                    (memory_properties.memoryTypes[i].propertyFlags & wanted) == wanted) {
                    return i;
                }
            }
        }
        std::abort();
    };
    const auto check = [](vk::Result result) { assert(result == vk::Result::eSuccess); };
    const auto finish = [&] {
        check(cmd.end(d));
        const vk::SubmitInfo submit{.commandBufferCount = 1, .pCommandBuffers = &cmd};
        check(queue.submit(submit, *fence, d));
        assert(device.waitForFences(*fence, true, UINT64_MAX, d) == vk::Result::eSuccess);
        check(device.resetFences(*fence, d));
    };
    std::printf("RCAS GPU: %s\n", physical.getProperties(d).deviceName.data());
    std::fflush(stdout);
    std::array<vk::DescriptorSetLayoutBinding, 2> bindings{};
    for (u32 i = 0; i < 2; ++i) {
        bindings[i] = {.binding = i,
                       .descriptorType = vk::DescriptorType::eStorageImage,
                       .descriptorCount = 1,
                       .stageFlags = vk::ShaderStageFlagBits::eCompute};
    }
    auto desc = device
                    .createDescriptorSetLayoutUnique(
                        {.flags = vk::DescriptorSetLayoutCreateFlagBits::ePushDescriptorKHR,
                         .bindingCount = 2,
                         .pBindings = bindings.data()},
                        nullptr, d)
                    .value;
    const vk::PushConstantRange push{vk::ShaderStageFlagBits::eCompute, 0, sizeof(float)};
    auto layout = device
                      .createPipelineLayoutUnique({.setLayoutCount = 1,
                                                   .pSetLayouts = &*desc,
                                                   .pushConstantRangeCount = 1,
                                                   .pPushConstantRanges = &push},
                                                  nullptr, d)
                      .value;
    auto old_shader =
        device
            .createShaderModuleUnique(
                {.codeSize = sizeof(TAA_SHARPEN_COMP), .pCode = TAA_SHARPEN_COMP}, nullptr, d)
            .value;
    auto new_shader = device
                          .createShaderModuleUnique({.codeSize = sizeof(TAA_SHARPEN_DIRECT_COMP),
                                                     .pCode = TAA_SHARPEN_DIRECT_COMP},
                                                    nullptr, d)
                          .value;
    auto make_pipeline = [&](vk::ShaderModule module) {
        return device
            .createComputePipelineUnique({},
                                         {.stage = {.stage = vk::ShaderStageFlagBits::eCompute,
                                                    .module = module,
                                                    .pName = "main"},
                                          .layout = *layout},
                                         nullptr, d)
            .value;
    };
    auto old_pipeline = make_pipeline(*old_shader), new_pipeline = make_pipeline(*new_shader);
    const auto barrier = [&](vk::CommandBuffer cmd, vk::PipelineStageFlags2 src,
                             vk::AccessFlags2 sa, vk::PipelineStageFlags2 dst,
                             vk::AccessFlags2 da) {
        const vk::MemoryBarrier2 b{
            .srcStageMask = src, .srcAccessMask = sa, .dstStageMask = dst, .dstAccessMask = da};
        cmd.pipelineBarrier2({.memoryBarrierCount = 1, .pMemoryBarriers = &b}, d);
    };
    u32 cases = 0;
    uint64_t total_components = 0;
    const std::array<std::array<u32, 2>, 6> sizes{
        {{1, 1}, {17, 11}, {2049, 7}, {1920, 1080}, {2560, 1440}, {3840, 2160}}};
    for (const auto size : sizes) {
        const u32 w = size[0], h = size[1];
        const size_t pixels = size_t(w) * h, bytes = pixels * 8;
        std::array<vk::UniqueDeviceMemory, 4> image_memory;
        std::array<vk::UniqueImage, 4> images;
        std::array<vk::UniqueImageView, 4> views;
        for (u32 i = 0; i < 4; ++i) {
            const auto format =
                i == 1 ? vk::Format::eR32G32B32A32Sfloat : vk::Format::eR16G16B16A16Sfloat;
            images[i] = device
                            .createImageUnique({.imageType = vk::ImageType::e2D,
                                                .format = format,
                                                .extent = {w, h, 1},
                                                .mipLevels = 1,
                                                .arrayLayers = 1,
                                                .samples = vk::SampleCountFlagBits::e1,
                                                .tiling = vk::ImageTiling::eOptimal,
                                                .usage = vk::ImageUsageFlagBits::eStorage |
                                                         vk::ImageUsageFlagBits::eTransferSrc |
                                                         vk::ImageUsageFlagBits::eTransferDst},
                                               nullptr, d)
                            .value;
            const auto requirements = device.getImageMemoryRequirements(*images[i], d);
            image_memory[i] =
                device
                    .allocateMemoryUnique(
                        {.allocationSize = requirements.size,
                         .memoryTypeIndex = memory_type(requirements.memoryTypeBits,
                                                        vk::MemoryPropertyFlagBits::eDeviceLocal)},
                        nullptr, d)
                    .value;
            check(device.bindImageMemory(*images[i], *image_memory[i], 0, d));
            views[i] = device
                           .createImageViewUnique(
                               {.image = *images[i],
                                .viewType = vk::ImageViewType::e2D,
                                .format = format,
                                .subresourceRange = {vk::ImageAspectFlagBits::eColor, 0, 1, 0, 1}},
                               nullptr, d)
                           .value;
        }
        auto staging = device
                           .createBufferUnique({.size = bytes * 4,
                                                .usage = vk::BufferUsageFlagBits::eTransferSrc |
                                                         vk::BufferUsageFlagBits::eTransferDst},
                                               nullptr, d)
                           .value;
        const auto requirements = device.getBufferMemoryRequirements(*staging, d);
        auto staging_memory =
            device
                .allocateMemoryUnique(
                    {.allocationSize = requirements.size,
                     .memoryTypeIndex = memory_type(requirements.memoryTypeBits,
                                                    vk::MemoryPropertyFlagBits::eHostVisible |
                                                        vk::MemoryPropertyFlagBits::eHostCoherent,
                                                    vk::MemoryPropertyFlagBits::eHostCached)},
                    nullptr, d)
                .value;
        check(device.bindBufferMemory(*staging, *staging_memory, 0, d));
        void* mapped = device.mapMemory(*staging_memory, 0, bytes * 4, {}, d).value;
        for (u32 pattern = 0; pattern < 3; ++pattern) {
            auto* input = static_cast<u16*>(mapped);
            const std::array<u16, 12> sdr{0,      1,      0x3c00, 0x3bff, 0x3800, 0x3c01,
                                          0x3555, 0x3400, 0x0400, 0x0003, 0x3a00, 0x3200};
            for (size_t p = 0; p < pixels; ++p) {
                for (u32 c = 0; c < 4; ++c) {
                    uint32_t hash = uint32_t(p) * 747796405u + c * 2891336453u + 277803737u;
                    hash = ((hash >> ((hash >> 28) + 4)) ^ hash) * 277803737u;
                    if (pattern == 0) {
                        input[p * 4 + c] = sdr[(p + c * 7 + (p / w) * 3) % sdr.size()];
                    } else if (pattern == 1) {
                        const u16 magnitude = u16(hash & 0x7fffu);
                        input[p * 4 + c] =
                            u16(std::min<u16>(magnitude, 0x7bffu) | (hash & 0x8000u));
                    } else {
                        input[p * 4 + c] = c == 0   ? 0x4800u
                                           : c == 1 ? 0u
                                           : c == 2 ? 0x3800u
                                                    : 0x3bffu;
                    }
                }
            }
            for (const float strength : {0.f, .25f, .5f, 1.f, 2.f}) {
                check(cmd.reset({}, d));
                check(cmd.begin({.flags = vk::CommandBufferUsageFlagBits::eOneTimeSubmit}, d));
                std::array<vk::ImageMemoryBarrier2, 4> transitions{};
                for (u32 i = 0; i < 4; ++i) {
                    transitions[i] = {
                        .srcStageMask = vk::PipelineStageFlagBits2::eAllCommands,
                        .srcAccessMask =
                            vk::AccessFlagBits2::eMemoryRead | vk::AccessFlagBits2::eMemoryWrite,
                        .dstStageMask = vk::PipelineStageFlagBits2::eAllCommands,
                        .dstAccessMask =
                            vk::AccessFlagBits2::eMemoryRead | vk::AccessFlagBits2::eMemoryWrite,
                        .oldLayout = vk::ImageLayout::eUndefined,
                        .newLayout = vk::ImageLayout::eGeneral,
                        .image = *images[i],
                        .subresourceRange = {vk::ImageAspectFlagBits::eColor, 0, 1, 0, 1}};
                }
                cmd.pipelineBarrier2(
                    {.imageMemoryBarrierCount = 4, .pImageMemoryBarriers = transitions.data()}, d);
                const vk::BufferImageCopy upload{
                    .imageSubresource = {vk::ImageAspectFlagBits::eColor, 0, 0, 1},
                    .imageExtent = {w, h, 1}};
                cmd.copyBufferToImage(*staging, *images[0], vk::ImageLayout::eGeneral, upload, d);
                barrier(cmd, vk::PipelineStageFlagBits2::eTransfer,
                        vk::AccessFlagBits2::eTransferWrite,
                        vk::PipelineStageFlagBits2::eAllCommands,
                        vk::AccessFlagBits2::eMemoryRead | vk::AccessFlagBits2::eMemoryWrite);
                const vk::ImageBlit blit{
                    .srcSubresource = {vk::ImageAspectFlagBits::eColor, 0, 0, 1},
                    .srcOffsets = std::array{vk::Offset3D{}, vk::Offset3D{s32(w), s32(h), 1}},
                    .dstSubresource = {vk::ImageAspectFlagBits::eColor, 0, 0, 1},
                    .dstOffsets = std::array{vk::Offset3D{}, vk::Offset3D{s32(w), s32(h), 1}}};
                cmd.blitImage(*images[0], vk::ImageLayout::eGeneral, *images[1],
                              vk::ImageLayout::eGeneral, blit, vk::Filter::eNearest, d);
                barrier(cmd, vk::PipelineStageFlagBits2::eTransfer,
                        vk::AccessFlagBits2::eTransferWrite,
                        vk::PipelineStageFlagBits2::eComputeShader,
                        vk::AccessFlagBits2::eShaderStorageRead |
                            vk::AccessFlagBits2::eShaderStorageWrite);
                const auto dispatch = [&](u32 input_index, u32 output_index,
                                          vk::Pipeline pipeline) {
                    const std::array<vk::DescriptorImageInfo, 2> infos{
                        {{.imageView = *views[input_index],
                          .imageLayout = vk::ImageLayout::eGeneral},
                         {.imageView = *views[output_index],
                          .imageLayout = vk::ImageLayout::eGeneral}}};
                    std::array<vk::WriteDescriptorSet, 2> writes{};
                    for (u32 i = 0; i < 2; ++i) {
                        writes[i] = {.dstBinding = i,
                                     .descriptorCount = 1,
                                     .descriptorType = vk::DescriptorType::eStorageImage,
                                     .pImageInfo = &infos[i]};
                    }
                    cmd.bindPipeline(vk::PipelineBindPoint::eCompute, pipeline, d);
                    cmd.pushDescriptorSetKHR(vk::PipelineBindPoint::eCompute, *layout, 0, writes,
                                             d);
                    cmd.pushConstants(*layout, vk::ShaderStageFlagBits::eCompute, 0,
                                      sizeof(strength), &strength, d);
                    cmd.dispatch((w + 7) / 8, (h + 7) / 8, 1, d);
                };
                dispatch(1, 2, *old_pipeline);
                dispatch(0, 3, *new_pipeline);
                barrier(cmd, vk::PipelineStageFlagBits2::eComputeShader,
                        vk::AccessFlagBits2::eShaderStorageWrite,
                        vk::PipelineStageFlagBits2::eTransfer, vk::AccessFlagBits2::eTransferRead);
                for (u32 i = 0; i < 3; ++i) {
                    const vk::BufferImageCopy copy{
                        .bufferOffset = bytes * (i + 1),
                        .imageSubresource = {vk::ImageAspectFlagBits::eColor, 0, 0, 1},
                        .imageExtent = {w, h, 1}};
                    cmd.copyImageToBuffer(*images[i == 2 ? 0 : i + 2], vk::ImageLayout::eGeneral,
                                          *staging, copy, d);
                }
                barrier(cmd, vk::PipelineStageFlagBits2::eTransfer,
                        vk::AccessFlagBits2::eTransferWrite, vk::PipelineStageFlagBits2::eHost,
                        vk::AccessFlagBits2::eHostRead);
                finish();
                const auto* base = static_cast<const char*>(mapped);
                assert(!std::memcmp(base, base + bytes * 3, bytes));
                const auto* old_out = reinterpret_cast<const u16*>(base + bytes);
                const auto* new_out = reinterpret_cast<const u16*>(base + bytes * 2);
                size_t differences = 0;
                for (size_t i = 0; i < pixels * 4; ++i) {
                    if (old_out[i] != new_out[i]) {
                        if (differences < 4) {
                            std::fprintf(stderr,
                                         "mismatch %ux%u p=%zu c=%zu pattern=%u "
                                         "strength=%.2f old=%04x new=%04x\n",
                                         w, h, i / 4, i % 4, pattern, strength, old_out[i],
                                         new_out[i]);
                        }
                        ++differences;
                    }
                }
                std::printf("SHARPEN_COMPARE %ux%u pattern=%u strength=%.2f "
                            "components=%zu differences=%zu input_preserved=1\n",
                            w, h, pattern, strength, pixels * 4, differences);
                std::fflush(stdout);
                assert(differences == 0);
                ++cases;
                total_components += pixels * 4;
            }
        }
        device.unmapMemory(*staging_memory, d);
        staging.reset();
    }
    std::printf("PASS: %u cases, %llu FP16 components bit-identical; inputs unchanged\n", cases,
                static_cast<unsigned long long>(total_components));
}
