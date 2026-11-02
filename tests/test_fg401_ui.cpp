// Actual reference copy + existing game HUD shader vs fused pass, with CPU pixel oracle.
#include "fused_fg_ui.h"
#include "video_core/host_shaders/frame_gen_ui_comp.h"
#include "video_core/renderer_vulkan/vk_instance.h"
#include "video_core/renderer_vulkan/vk_scheduler.h"
#include "video_core/renderer_vulkan/vk_shader_util.h"
#include "video_core/texture_cache/image.h"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>
#include <vk_mem_alloc.h>
using namespace Vulkan;
extern "C" void runtime_restart() { std::abort(); }
int main(int argc, char **argv) {
    std::setvbuf(stdout, nullptr, _IONBF, 0);
    try {
        u32 width = 257, height = 129, iterations = 128;
        std::string pattern = "mixed";
        if (argc > 1)
            std::sscanf(argv[1], "%ux%u", &width, &height);
        if (argc > 2)
            iterations = std::stoul(argv[2]);
        if (argc > 3)
            pattern = argv[3];
        if (!width || !height || width > 3840 || height > 2160 || iterations < 1 ||
            iterations > 1000 ||
            (pattern != "none" && pattern != "mixed" && pattern != "threshold" &&
             pattern != "full"))
            throw std::runtime_error("Invalid test arguments");
        Instance instance(0, false);
        VULKAN_HPP_DEFAULT_DISPATCHER.init(instance.GetInstance());
        VULKAN_HPP_DEFAULT_DISPATCHER.init(instance.GetDevice());
        auto device = instance.GetDevice();
        Scheduler scheduler(instance);
        std::array<VideoCore::UniqueImage, 5> images;
        std::array<vk::UniqueImageView, 5> views;
        for (u32 i = 0; i < 5; ++i) {
            images[i] = VideoCore::UniqueImage(device, instance.GetAllocator());
            images[i].Create({.imageType = vk::ImageType::e2D,
                              .format = vk::Format::eR8G8B8A8Unorm,
                              .extent = {width, height, 1},
                              .mipLevels = 1,
                              .arrayLayers = 1,
                              .samples = vk::SampleCountFlagBits::e1,
                              .tiling = vk::ImageTiling::eOptimal,
                              .usage = vk::ImageUsageFlagBits::eTransferSrc |
                                       vk::ImageUsageFlagBits::eTransferDst |
                                       vk::ImageUsageFlagBits::eSampled |
                                       vk::ImageUsageFlagBits::eStorage});
            views[i] = Check(device.createImageViewUnique(
                {.image = vk::Image(images[i]),
                 .viewType = vk::ImageViewType::e2D,
                 .format = vk::Format::eR8G8B8A8Unorm,
                 .subresourceRange = {vk::ImageAspectFlagBits::eColor, 0, 1, 0, 1}}));
        }
        const size_t pixels = size_t(width) * height, bytes = pixels * 4;
        VkBuffer host{};
        VmaAllocation allocation{};
        VmaAllocationInfo mapping{};
        VkBufferCreateInfo bc{VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};
        bc.size = bytes * 5;
        bc.usage = VK_BUFFER_USAGE_TRANSFER_SRC_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT;
        VmaAllocationCreateInfo ac{};
        ac.usage = VMA_MEMORY_USAGE_AUTO;
        ac.flags = VMA_ALLOCATION_CREATE_HOST_ACCESS_RANDOM_BIT | VMA_ALLOCATION_CREATE_MAPPED_BIT;
        if (vmaCreateBuffer(instance.GetAllocator(), &bc, &ac, &host, &allocation, &mapping) !=
            VK_SUCCESS)
            throw std::runtime_error("Staging allocation failed");
        auto *data = static_cast<uint8_t *>(mapping.pMappedData);
        std::vector<uint8_t> expected(bytes);
        size_t hud_pixels{};
        for (size_t i = 0; i < pixels; ++i) {
            const size_t p = i * 4;
            for (unsigned c = 0; c < 4; ++c) {
                data[p + c] = uint8_t(i * (17 + c * 38) + c * 41);
                data[bytes + p + c] = data[2 * bytes + p + c] = uint8_t(i * (29 + c * 16) + c * 67);
            }
            unsigned delta = pattern == "none"        ? 0
                             : pattern == "full"      ? 71
                             : pattern == "threshold" ? i % 3
                                                      : (i % 16 == 0   ? 71
                                                         : i % 16 == 1 ? 2
                                                         : i % 16 == 2 ? 1
                                                                       : 0);
            data[bytes + p + (i % 3)] = uint8_t(data[bytes + p + (i % 3)] + delta);
            int difference = 0;
            for (unsigned c = 0; c < 3; ++c)
                difference = std::max(
                    difference, std::abs(int(data[bytes + p + c]) - int(data[2 * bytes + p + c])));
            const bool hud = difference > 1;
            hud_pixels += hud;
            for (unsigned c = 0; c < 4; ++c)
                expected[p + c] = hud ? (c == 3 ? 255 : data[bytes + p + c]) : data[p + c];
        }
        vmaFlushAllocation(instance.GetAllocator(), allocation, 0, bytes * 3);
        auto cmd = scheduler.CommandBuffer();
        std::array<vk::ImageMemoryBarrier2, 5> initial{};
        for (u32 i = 0; i < 5; ++i)
            initial[i] = {.srcStageMask = vk::PipelineStageFlagBits2::eNone,
                          .dstStageMask = vk::PipelineStageFlagBits2::eAllCommands,
                          .dstAccessMask =
                              vk::AccessFlagBits2::eMemoryWrite | vk::AccessFlagBits2::eMemoryRead,
                          .oldLayout = vk::ImageLayout::eUndefined,
                          .newLayout = vk::ImageLayout::eGeneral,
                          .image = vk::Image(images[i]),
                          .subresourceRange = {vk::ImageAspectFlagBits::eColor, 0, 1, 0, 1}};
        cmd.pipelineBarrier2(
            {.imageMemoryBarrierCount = 5, .pImageMemoryBarriers = initial.data()});
        for (u32 i = 0; i < 3; ++i)
            cmd.copyBufferToImage(
                host, vk::Image(images[i]), vk::ImageLayout::eGeneral,
                vk::BufferImageCopy{.bufferOffset = bytes * i,
                                    .imageSubresource = {vk::ImageAspectFlagBits::eColor, 0, 0, 1},
                                    .imageExtent = {width, height, 1}});
        scheduler.Finish();
        const std::array<vk::DescriptorSetLayoutBinding, 3> bindings{
            {{0, vk::DescriptorType::eStorageImage, 1, vk::ShaderStageFlagBits::eCompute},
             {1, vk::DescriptorType::eSampledImage, 1, vk::ShaderStageFlagBits::eCompute},
             {2, vk::DescriptorType::eSampledImage, 1, vk::ShaderStageFlagBits::eCompute}}};
        auto desc = Check(device.createDescriptorSetLayoutUnique(
            {.flags = vk::DescriptorSetLayoutCreateFlagBits::ePushDescriptorKHR,
             .bindingCount = 3,
             .pBindings = bindings.data()}));
        const vk::PushConstantRange push{vk::ShaderStageFlagBits::eCompute, 0, 2 * sizeof(s32)};
        auto layout = Check(device.createPipelineLayoutUnique({.setLayoutCount = 1,
                                                               .pSetLayouts = &*desc,
                                                               .pushConstantRangeCount = 1,
                                                               .pPushConstantRanges = &push}));
        auto module = CompileSPV(FRAME_GEN_UI_COMP, device);
        auto pipeline = Check(device.createComputePipelineUnique(
            {}, vk::ComputePipelineCreateInfo{.stage = {.stage = vk::ShaderStageFlagBits::eCompute,
                                                        .module = module,
                                                        .pName = "main"},
                                              .layout = *layout}));
        device.destroyShaderModule(module);
        auto queries = Check(device.createQueryPoolUnique(
            {.queryType = vk::QueryType::eTimestamp, .queryCount = 4}));
        const double factor =
            instance.GetPhysicalDevice().getProperties().limits.timestampPeriod / 1e6;
        FusedFgUi fused(instance);
        std::vector<double> old_times, new_times;
        const auto memory_barrier = [&](vk::CommandBuffer command) {
            const vk::MemoryBarrier2 b{.srcStageMask = vk::PipelineStageFlagBits2::eAllCommands,
                                       .srcAccessMask = vk::AccessFlagBits2::eMemoryRead |
                                                        vk::AccessFlagBits2::eMemoryWrite,
                                       .dstStageMask = vk::PipelineStageFlagBits2::eAllCommands,
                                       .dstAccessMask = vk::AccessFlagBits2::eMemoryRead |
                                                        vk::AccessFlagBits2::eMemoryWrite};
            command.pipelineBarrier2({.memoryBarrierCount = 1, .pMemoryBarriers = &b});
        };
        const auto reference = [&](vk::CommandBuffer command) {
            memory_barrier(command);
            command.copyImage(
                vk::Image(images[0]), vk::ImageLayout::eGeneral, vk::Image(images[3]),
                vk::ImageLayout::eGeneral,
                vk::ImageCopy{.srcSubresource = {vk::ImageAspectFlagBits::eColor, 0, 0, 1},
                              .dstSubresource = {vk::ImageAspectFlagBits::eColor, 0, 0, 1},
                              .extent = {width, height, 1}});
            memory_barrier(command);
            const std::array<vk::DescriptorImageInfo, 3> infos{
                {{.imageView = *views[3], .imageLayout = vk::ImageLayout::eGeneral},
                 {.imageView = *views[1], .imageLayout = vk::ImageLayout::eGeneral},
                 {.imageView = *views[2], .imageLayout = vk::ImageLayout::eGeneral}}};
            std::array<vk::WriteDescriptorSet, 3> writes{};
            for (u32 i = 0; i < 3; ++i)
                writes[i] = {.dstBinding = i,
                             .descriptorCount = 1,
                             .descriptorType = i ? vk::DescriptorType::eSampledImage
                                                 : vk::DescriptorType::eStorageImage,
                             .pImageInfo = &infos[i]};
            const std::array<s32, 2> size{s32(width), s32(height)};
            command.bindPipeline(vk::PipelineBindPoint::eCompute, *pipeline);
            command.pushDescriptorSetKHR(vk::PipelineBindPoint::eCompute, *layout, 0, writes);
            command.pushConstants(*layout, vk::ShaderStageFlagBits::eCompute, 0, sizeof(size),
                                  size.data());
            command.dispatch((width + 7) / 8, (height + 7) / 8, 1);
        };
        for (u32 iteration = 0; iteration < iterations + 16; ++iteration) {
            device.resetQueryPool(*queries, 0, 4);
            cmd = scheduler.CommandBuffer();
            const bool reverse = iteration % 2;
            for (u32 pass = 0; pass < 2; ++pass) {
                const bool candidate = bool(pass) ^ reverse;
                const u32 q = candidate ? 2 : 0;
                cmd.writeTimestamp2(vk::PipelineStageFlagBits2::eAllCommands, *queries, q);
                if (candidate)
                    fused.Record(cmd, vk::Image(images[4]), *views[4], vk::Image(images[0]),
                                 *views[0], *views[1], *views[2], width, height);
                else
                    reference(cmd);
                cmd.writeTimestamp2(vk::PipelineStageFlagBits2::eAllCommands, *queries, q + 1);
            }
            if (iteration == iterations + 15) {
                memory_barrier(cmd);
                for (u32 i = 3; i < 5; ++i)
                    cmd.copyImageToBuffer(
                        vk::Image(images[i]), vk::ImageLayout::eGeneral, host,
                        vk::BufferImageCopy{
                            .bufferOffset = bytes * i,
                            .imageSubresource = {vk::ImageAspectFlagBits::eColor, 0, 0, 1},
                            .imageExtent = {width, height, 1}});
            }
            scheduler.Finish();
            std::array<u64, 4> stamps{};
            Check(device.getQueryPoolResults(*queries, 0, 4, sizeof(stamps), stamps.data(),
                                             sizeof(u64), vk::QueryResultFlagBits::e64));
            if (iteration >= 16) {
                old_times.push_back((stamps[1] - stamps[0]) * factor);
                new_times.push_back((stamps[3] - stamps[2]) * factor);
            }
        }
        vmaInvalidateAllocation(instance.GetAllocator(), allocation, bytes * 3, bytes * 2);
        size_t differing{}, oracle_old{}, oracle_new{};
        uint64_t hash = 14695981039346656037ull;
        for (size_t i = 0; i < bytes; ++i) {
            differing += data[bytes * 3 + i] != data[bytes * 4 + i];
            oracle_old += data[bytes * 3 + i] != expected[i];
            oracle_new += data[bytes * 4 + i] != expected[i];
            hash ^= data[bytes * 4 + i];
            hash *= 1099511628211ull;
        }
        const double old_ms =
            std::accumulate(old_times.begin(), old_times.end(), 0.0) / old_times.size();
        const double new_ms =
            std::accumulate(new_times.begin(), new_times.end(), 0.0) / new_times.size();
        std::printf(
            "RESULT size=%ux%u pattern=%s hud_pixels=%zu bytes=%zu differing=%zu oracle_old=%zu "
            "oracle_fused=%zu reference_ms=%.9f fused_ms=%.9f hash=%016llx\n",
            width, height, pattern.c_str(), hud_pixels, bytes, differing, oracle_old, oracle_new,
            old_ms, new_ms, (unsigned long long)hash);
        if (differing || oracle_old || oracle_new)
            throw std::runtime_error("Pixel regression");
        vmaDestroyBuffer(instance.GetAllocator(), host, allocation);
        std::puts(
            "PASS reference and fused images are byte-identical and match CPU HUD/alpha oracle");
        return 0;
    } catch (const std::exception &e) {
        std::fprintf(stderr, "FAIL %s\n", e.what());
        return 1;
    }
}
