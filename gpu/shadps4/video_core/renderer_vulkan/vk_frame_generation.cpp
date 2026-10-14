// SPDX-License-Identifier: GPL-2.0-or-later
#include "video_core/renderer_vulkan/vk_frame_generation.h"
#include <algorithm>
#include <cstdio>
#include "bbport_background.h"
#include "bbport_settings.h"
#include "ffx_vk_fsr3_3_1_5_bridge.h"
#include "video_core/host_shaders/frame_generation_copy_comp.h"
#include <vk_mem_alloc.h>

namespace Vulkan {
namespace {
constexpr auto usage = vk::ImageUsageFlagBits::eSampled | vk::ImageUsageFlagBits::eStorage |
                       vk::ImageUsageFlagBits::eTransferSrc | vk::ImageUsageFlagBits::eTransferDst;
bool CreateImage(vk::Device device, VmaAllocator allocator, FrameGeneration::Image& image,
                 vk::UniqueImageView& view, vk::Format format, u32 width, u32 height) {
    if (!image.Create(allocator,format,width,height)) return false;
    auto result=device.createImageViewUnique({
        .image=vk::Image(image), .viewType=vk::ImageViewType::e2D, .format=format,
        .subresourceRange={vk::ImageAspectFlagBits::eColor,0,1,0,1}});
    if (result.result!=vk::Result::eSuccess) return false;
    view=std::move(result.value);
    return true;
}
FfxVkFsr3_3_1_6FrameGenerationImage Describe(vk::Image image, vk::Format format, u32 w, u32 h) {
    return {VkImage(image), VkFormat(format), w, h, VK_IMAGE_LAYOUT_GENERAL, VkImageUsageFlags(usage)};
}
void WriteBarrier(vk::CommandBuffer cmdbuf, vk::Image image) {
    const vk::ImageMemoryBarrier2 barrier{
        .srcStageMask=vk::PipelineStageFlagBits2::eAllCommands,
        .srcAccessMask=vk::AccessFlagBits2::eNone,
        .dstStageMask=vk::PipelineStageFlagBits2::eComputeShader,
        .dstAccessMask=vk::AccessFlagBits2::eShaderWrite,
        .oldLayout=vk::ImageLayout::eUndefined, .newLayout=vk::ImageLayout::eGeneral,
        .srcQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,
        .image=image, .subresourceRange={vk::ImageAspectFlagBits::eColor,0,1,0,1}};
    cmdbuf.pipelineBarrier2({.imageMemoryBarrierCount=1,.pImageMemoryBarriers=&barrier});
}
}

FrameGeneration::Image::~Image() {
    if (image) vmaDestroyImage(allocator,VkImage(image),allocation);
}
bool FrameGeneration::Image::Create(VmaAllocator allocator_, vk::Format format, u32 w, u32 h) {
    return Create(allocator_, format, w, h, usage);
}
bool FrameGeneration::Image::Create(VmaAllocator allocator_, vk::Format format, u32 w, u32 h,
                                    vk::ImageUsageFlags image_usage) {
    allocator=allocator_;
    const vk::ImageCreateInfo info{.imageType=vk::ImageType::e2D,.format=format,.extent={w,h,1},
        .mipLevels=1,.arrayLayers=1,.samples=vk::SampleCountFlagBits::e1,.usage=image_usage};
    const VkImageCreateInfo raw=info;
    const VmaAllocationCreateInfo allocation_info{
        .flags=VMA_ALLOCATION_CREATE_WITHIN_BUDGET_BIT,.usage=VMA_MEMORY_USAGE_AUTO_PREFER_DEVICE};
    VkImage handle{};
    if (vmaCreateImage(allocator,&raw,&allocation_info,&handle,&allocation,nullptr)!=VK_SUCCESS)
        return false;
    image=handle;
    return true;
}

bool FrameGeneration::FreezeDepth(vk::Device device, VmaAllocator allocator, vk::CommandBuffer command,
                                  vk::Image source, vk::Format format, u32 w, u32 h,
                                  std::shared_ptr<FrameGenerationDepthCopy>& copy) {
    if (!source || !w || !h || (format != vk::Format::eD32Sfloat &&
        format != vk::Format::eD32SfloatS8Uint && format != vk::Format::eR32Sfloat)) return false;
    const bool depth_format = format != vk::Format::eR32Sfloat;
    const vk::ImageAspectFlags copied_aspect = depth_format ? vk::ImageAspectFlagBits::eDepth
                                                          : vk::ImageAspectFlagBits::eColor;
    const auto all_aspects = copied_aspect | (format == vk::Format::eD32SfloatS8Uint
        ? vk::ImageAspectFlagBits::eStencil : vk::ImageAspectFlags{});
    // A shared owner keeps the previous scene's *contents*, not just its handle.
    // A later scene must not overwrite depth retained by a display/FG snapshot.
    const bool fresh = !copy || copy.use_count() > 1 || copy->width != w ||
                       copy->height != h || copy->format != format;
    if (fresh) {
        auto next = std::make_shared<FrameGenerationDepthCopy>();
        if (!next->depth.Create(allocator, format, w, h, vk::ImageUsageFlagBits::eSampled |
            vk::ImageUsageFlagBits::eTransferSrc | vk::ImageUsageFlagBits::eTransferDst)) return false;
        auto view = device.createImageViewUnique({.image=vk::Image(next->depth),
            .viewType=vk::ImageViewType::e2D,.format=format,
            .subresourceRange={copied_aspect,0,1,0,1}});
        if (view.result != vk::Result::eSuccess) return false;
        next->view = std::move(view.value); next->format=format; next->width=w; next->height=h;
        copy = std::move(next);
    }
    const vk::MemoryBarrier2 source_ready{.srcStageMask=vk::PipelineStageFlagBits2::eAllCommands,
        .srcAccessMask=vk::AccessFlagBits2::eMemoryWrite,
        .dstStageMask=vk::PipelineStageFlagBits2::eTransfer,.dstAccessMask=vk::AccessFlagBits2::eTransferRead};
    const vk::ImageMemoryBarrier2 before{.srcStageMask=vk::PipelineStageFlagBits2::eAllCommands,
            .srcAccessMask=vk::AccessFlagBits2::eMemoryRead|vk::AccessFlagBits2::eMemoryWrite,
            .dstStageMask=vk::PipelineStageFlagBits2::eTransfer,.dstAccessMask=vk::AccessFlagBits2::eTransferWrite,
            .oldLayout=fresh ? vk::ImageLayout::eUndefined : vk::ImageLayout::eGeneral,
            .newLayout=vk::ImageLayout::eGeneral,
            .srcQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,
            .image=vk::Image(copy->depth),.subresourceRange={all_aspects,0,1,0,1}};
    command.pipelineBarrier2({.memoryBarrierCount=1,.pMemoryBarriers=&source_ready,
                             .imageMemoryBarrierCount=1,.pImageMemoryBarriers=&before});
    const vk::ImageCopy region{.srcSubresource={copied_aspect,0,0,1},
        .dstSubresource={copied_aspect,0,0,1},.extent={w,h,1}};
    command.copyImage(source,vk::ImageLayout::eGeneral,vk::Image(copy->depth),vk::ImageLayout::eGeneral,region);
    const vk::MemoryBarrier2 after{.srcStageMask=vk::PipelineStageFlagBits2::eTransfer,
        .srcAccessMask=vk::AccessFlagBits2::eTransferRead|vk::AccessFlagBits2::eTransferWrite,
        .dstStageMask=vk::PipelineStageFlagBits2::eAllCommands,
        .dstAccessMask=vk::AccessFlagBits2::eMemoryRead|vk::AccessFlagBits2::eMemoryWrite};
    command.pipelineBarrier2({.memoryBarrierCount=1,.pMemoryBarriers=&after});
    return true;
}

bool FrameGeneration::FreezeMotion(vk::Device device, VmaAllocator allocator,
                                   vk::CommandBuffer command, vk::Image source,
                                   const std::shared_ptr<FrameGenerationDepthCopy>& copy) {
    if (!source || !copy || copy.use_count() != 1 || !copy->width || !copy->height)
        return false;
    const bool fresh = !copy->motion.image;
    if (fresh) {
        // Publish the image/view together: allocation/view failure leaves a
        // retryable slot rather than an image with a missing descriptor view.
        Image image;
        if (!image.Create(allocator, vk::Format::eR16G16Sfloat, copy->width, copy->height))
            return false;
        auto view = device.createImageViewUnique({.image = vk::Image(image),
            .viewType = vk::ImageViewType::e2D, .format = vk::Format::eR16G16Sfloat,
            .subresourceRange = {vk::ImageAspectFlagBits::eColor, 0, 1, 0, 1}});
        if (view.result != vk::Result::eSuccess) return false;
        std::swap(copy->motion.allocator, image.allocator);
        std::swap(copy->motion.allocation, image.allocation);
        std::swap(copy->motion.image, image.image);
        copy->motion_view = std::move(view.value);
    }
    const vk::MemoryBarrier2 ready{
        .srcStageMask = vk::PipelineStageFlagBits2::eAllCommands,
        .srcAccessMask = vk::AccessFlagBits2::eMemoryWrite,
        .dstStageMask = vk::PipelineStageFlagBits2::eTransfer,
        .dstAccessMask = vk::AccessFlagBits2::eTransferRead};
    const vk::ImageMemoryBarrier2 before{
        .srcStageMask = vk::PipelineStageFlagBits2::eAllCommands,
        .srcAccessMask = vk::AccessFlagBits2::eMemoryRead | vk::AccessFlagBits2::eMemoryWrite,
        .dstStageMask = vk::PipelineStageFlagBits2::eTransfer,
        .dstAccessMask = vk::AccessFlagBits2::eTransferWrite,
        .oldLayout = fresh ? vk::ImageLayout::eUndefined : vk::ImageLayout::eGeneral,
        .newLayout = vk::ImageLayout::eGeneral,
        .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
        .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
        .image = vk::Image(copy->motion),
        .subresourceRange = {vk::ImageAspectFlagBits::eColor, 0, 1, 0, 1}};
    command.pipelineBarrier2({.memoryBarrierCount = 1, .pMemoryBarriers = &ready,
                             .imageMemoryBarrierCount = 1, .pImageMemoryBarriers = &before});
    const vk::ImageCopy region{.srcSubresource = {vk::ImageAspectFlagBits::eColor, 0, 0, 1},
        .dstSubresource = {vk::ImageAspectFlagBits::eColor, 0, 0, 1},
        .extent = {copy->width, copy->height, 1}};
    command.copyImage(source, vk::ImageLayout::eGeneral, vk::Image(copy->motion),
                      vk::ImageLayout::eGeneral, region);
    const vk::MemoryBarrier2 complete{
        .srcStageMask = vk::PipelineStageFlagBits2::eTransfer,
        .srcAccessMask = vk::AccessFlagBits2::eTransferRead | vk::AccessFlagBits2::eTransferWrite,
        .dstStageMask = vk::PipelineStageFlagBits2::eAllCommands,
        .dstAccessMask = vk::AccessFlagBits2::eMemoryRead | vk::AccessFlagBits2::eMemoryWrite};
    command.pipelineBarrier2({.memoryBarrierCount = 1, .pMemoryBarriers = &complete});
    return true;
}
FrameGeneration::FrameGeneration(vk::PhysicalDevice physical_, vk::Device device_,
                                 VmaAllocator allocator_, Submissions submissions_)
    : physical{physical_}, device{device_}, allocator{allocator_},
      submissions{std::move(submissions_)} {}
FrameGeneration::~FrameGeneration() { Reset(); }

bool FrameGeneration::EnsureCopyPipeline() {
    if (copy_pipeline) return true;
    std::array<vk::DescriptorSetLayoutBinding,6> bindings{};
    for (u32 i=0;i<6;++i) bindings[i]={
        .binding=i, .descriptorType=i<2 ? vk::DescriptorType::eSampledImage : vk::DescriptorType::eStorageImage,
        .descriptorCount=1, .stageFlags=vk::ShaderStageFlagBits::eCompute};
    auto descriptors=device.createDescriptorSetLayoutUnique({
        .flags=vk::DescriptorSetLayoutCreateFlagBits::ePushDescriptorKHR,
        .bindingCount=u32(bindings.size()),.pBindings=bindings.data()});
    if (descriptors.result!=vk::Result::eSuccess) return false;
    copy_descriptors=std::move(descriptors.value);
    const vk::PushConstantRange range{.stageFlags=vk::ShaderStageFlagBits::eCompute,.offset=0,.size=20};
    auto layout=device.createPipelineLayoutUnique({
        .setLayoutCount=1,.pSetLayouts=&*copy_descriptors,.pushConstantRangeCount=1,.pPushConstantRanges=&range});
    if (layout.result!=vk::Result::eSuccess) return false;
    copy_layout=std::move(layout.value);
    auto shader=device.createShaderModuleUnique({.codeSize=sizeof(FRAME_GENERATION_COPY_COMP),
                                                 .pCode=FRAME_GENERATION_COPY_COMP});
    if (shader.result!=vk::Result::eSuccess) return false;
    auto pipeline=device.createComputePipelineUnique({},vk::ComputePipelineCreateInfo{
        .stage={.stage=vk::ShaderStageFlagBits::eCompute,.module=*shader.value,.pName="main"},.layout=*copy_layout});
    if (pipeline.result!=vk::Result::eSuccess) return false;
    copy_pipeline=std::move(pipeline.value);
    return true;
}

void FrameGeneration::Capture(vk::CommandBuffer cmdbuf, const FrameGenerationSource& source,
                              vk::ImageView color_view, u32 w, u32 h, vk::Format format,
                              std::shared_ptr<Snapshot>& snapshot) {
    auto& settings=BbSettings::Get();
    const bool nvidia=settings.frame_generation==BbSettings::FrameGenerationNvidia;
    const bool sdr_unorm=format==vk::Format::eR8G8B8A8Unorm || format==vk::Format::eB8G8R8A8Unorm;
    const bool hdr=format==vk::Format::eA2B10G10R10UnormPack32 || format==vk::Format::eA2R10G10B10UnormPack32;
    if (settings.frame_generation == BbSettings::FrameGenerationOff ||
        settings.upscaler==BbSettings::UpscalerOff ||
        (settings.frame_generation==BbSettings::FrameGenerationFsr && failed.load(std::memory_order_relaxed)) || !source.valid ||
        !source.depth_view || !source.motion_view || !source.render_width || !source.render_height || !w || !h ||
        (!settings.window_focused && settings.background_mode!=BbSettings::BackgroundRun) ||
        (!hdr && format != vk::Format::eB8G8R8A8Srgb && format != vk::Format::eR8G8B8A8Srgb &&
                 format != vk::Format::eB8G8R8A8Unorm && format != vk::Format::eR8G8B8A8Unorm)) {
        snapshot.reset(); return;
    }
    if (!EnsureCopyPipeline()) {
        settings.frame_generation_problem="FG input pipeline could not be created. The real frame is kept.";
        failed=true;
        snapshot.reset(); return;
    }
    // A 4K scene can be displayed in a smaller window. Keep FI render dimensions
    // within the final color extent, scaling motion vectors in pixels with them.
    const float scale=std::min({1.0f,float(w)/source.render_width,float(h)/source.render_height});
    const u32 rw=std::max(1u,u32(source.render_width*scale));
    const u32 rh=std::max(1u,u32(source.render_height*scale));
    if (!snapshot || snapshot->width!=w || snapshot->height!=h || snapshot->hdr!=hdr || snapshot->sdr_unorm!=sdr_unorm || snapshot->nvidia_input_only!=nvidia ||
        snapshot->source.render_width!=rw || snapshot->source.render_height!=rh) {
        snapshot=std::make_shared<Snapshot>(); snapshot->width=w; snapshot->height=h; snapshot->hdr=hdr;
        snapshot->nvidia_input_only=nvidia;
        snapshot->sdr_unorm=sdr_unorm;
        // NVIDIA consumes WSI color directly. Keep only a 1x1 descriptor dummy,
        // rather than allocating/copying three unused full-resolution FP16 images.
        if (!CreateImage(device,allocator,snapshot->color,snapshot->color_view,vk::Format::eR16G16B16A16Sfloat,nvidia ? 1u : w,nvidia ? 1u : h) ||
            (!nvidia && !CreateImage(device,allocator,snapshot->generated,snapshot->generated_view,vk::Format::eR16G16B16A16Sfloat,w,h)) ||
            !CreateImage(device,allocator,snapshot->depth,snapshot->depth_view,vk::Format::eR32Sfloat,rw,rh) ||
            !CreateImage(device,allocator,snapshot->motion,snapshot->motion_view,vk::Format::eR16G16Sfloat,rw,rh) ||
            ((hdr || sdr_unorm) && !nvidia && !CreateImage(device,allocator,snapshot->encoded,snapshot->encoded_view,vk::Format::eR16G16B16A16Sfloat,w,h))) {
            settings.frame_generation_problem="FG could not allocate its input images. The real frame is kept.";
            failed=true;
            snapshot.reset(); return;
        }
    }
    snapshot->source=source;
    snapshot->source.render_width=rw; snapshot->source.render_height=rh;
    snapshot->source.jitter[0]*=float(rw)/source.render_width;
    snapshot->source.jitter[1]*=float(rh)/source.render_height;
    WriteBarrier(cmdbuf,vk::Image(snapshot->color));
    WriteBarrier(cmdbuf,vk::Image(snapshot->depth));
    WriteBarrier(cmdbuf,vk::Image(snapshot->motion));
    const vk::MemoryBarrier2 source_ready{
        .srcStageMask=vk::PipelineStageFlagBits2::eAllCommands,
        .srcAccessMask=vk::AccessFlagBits2::eMemoryRead|vk::AccessFlagBits2::eMemoryWrite,
        .dstStageMask=vk::PipelineStageFlagBits2::eComputeShader,
        .dstAccessMask=vk::AccessFlagBits2::eShaderRead};
    cmdbuf.pipelineBarrier2({.memoryBarrierCount=1,.pMemoryBarriers=&source_ready});
    const std::array<vk::DescriptorImageInfo,6> images{{
        {.imageView=color_view,.imageLayout=vk::ImageLayout::eGeneral},
        {.imageView=source.depth_view,.imageLayout=vk::ImageLayout::eGeneral},
        {.imageView=source.motion_view,.imageLayout=vk::ImageLayout::eGeneral},
        {.imageView=*snapshot->color_view,.imageLayout=vk::ImageLayout::eGeneral},
        {.imageView=*snapshot->depth_view,.imageLayout=vk::ImageLayout::eGeneral},
        {.imageView=*snapshot->motion_view,.imageLayout=vk::ImageLayout::eGeneral}}};
    std::array<vk::WriteDescriptorSet,6> writes{};
    for (u32 i=0;i<6;++i) writes[i]={.dstBinding=i,.descriptorCount=1,
        .descriptorType=i<2 ? vk::DescriptorType::eSampledImage : vk::DescriptorType::eStorageImage,.pImageInfo=&images[i]};
    cmdbuf.bindPipeline(vk::PipelineBindPoint::eCompute,*copy_pipeline);
    cmdbuf.pushDescriptorSetKHR(vk::PipelineBindPoint::eCompute,*copy_layout,0,writes);
    const std::array<u32,5> render_size{source.render_width,source.render_height,rw,rh,nvidia ? 3u : hdr ? 1u : sdr_unorm ? 4u : 0u};
    cmdbuf.pushConstants(*copy_layout,vk::ShaderStageFlagBits::eCompute,0,20,render_size.data());
    cmdbuf.dispatch(((nvidia ? rw : w)+7)/8,((nvidia ? rh : h)+7)/8,1);
    const vk::MemoryBarrier2 complete{
        .srcStageMask=vk::PipelineStageFlagBits2::eComputeShader,.srcAccessMask=vk::AccessFlagBits2::eShaderWrite,
        .dstStageMask=vk::PipelineStageFlagBits2::eAllCommands,.dstAccessMask=vk::AccessFlagBits2::eMemoryRead};
    cmdbuf.pipelineBarrier2({.memoryBarrierCount=1,.pMemoryBarriers=&complete});
}

void FrameGeneration::RetireCompleted() {
    while (!pending.empty() && submissions.is_free(pending.front().tick)) {
        if (context) ffxVkFsr3_3_1_6FrameGenerationContextRetireFrame(context,pending.front().id);
        pending.pop_front();
    }
}
void FrameGeneration::Invalidate() {
    history=false;
    if (BbSettings::Get().frame_generation!=BbSettings::FrameGenerationNvidia)
        BbSettings::Get().frame_generation_active=0;
}
void FrameGeneration::Reset() {
    if (context) {
        submissions.wait_submitted();
        ffxVkFsr3_3_1_6FrameGenerationContextDestroy(context); context=nullptr;
    }
    pending.clear(); recording={}; Invalidate();
}
bool FrameGeneration::Record(vk::CommandBuffer cmdbuf, const std::shared_ptr<Snapshot>& snapshot) {
    auto& settings=BbSettings::Get();
    RetireCompleted();
    if (settings.frame_generation!=BbSettings::FrameGenerationFsr ||
        settings.upscaler==BbSettings::UpscalerOff || !snapshot ||
        (!settings.window_focused && settings.background_mode!=BbSettings::BackgroundRun)) {
        Invalidate();
        if (settings.frame_generation==BbSettings::FrameGenerationNvidia && context) Reset();
        if (settings.frame_generation==BbSettings::FrameGenerationOff) { Reset(); failed=false; settings.frame_generation_problem=nullptr; }
        return false;
    }
    if (failed) return false;
    // Keep the FI/OF context within its buffered-frame budget without growing
    // a presentation queue or treating ordinary GPU back-pressure as a failure.
    if (pending.size()>=2) { submissions.wait(pending.front().tick); RetireCompleted(); }
    const auto& source=snapshot->source;
    if (context && (width!=snapshot->width || height!=snapshot->height ||
        render_width!=source.render_width || render_height!=source.render_height || context_hdr!=snapshot->hdr)) Reset();
    if (!context) {
        const FfxVkFsr3_3_1_6FrameGenerationCreateInfo create{
            VkPhysicalDevice(physical),VkDevice(device),
            source.render_width,source.render_height,snapshot->width,snapshot->height,VK_FORMAT_R16G16B16A16_SFLOAT};
        const auto result=ffxVkFsr3_3_1_6FrameGenerationContextCreate(&create,&context);
        if (result!=FFX_VK_FSR3_3_1_6_FRAMEGEN_OK) {
            std::printf("FSR Frame Generation: context creation failed (%d)\n",int(result));
            settings.frame_generation_problem="FSR FG could not create its GPU context. Turn it off and on to retry.";
            failed=true; Invalidate(); return false;
        }
        width=snapshot->width; height=snapshot->height;
        context_hdr=snapshot->hdr;
        render_width=source.render_width; render_height=source.render_height;
        std::printf("FSR Frame Generation: %ux%u render, %ux%u display, analytical 3.1.6\n",render_width,render_height,width,height);
    }
    const u64 current_pause=BbBackground::PausedNanoseconds();
    const bool reset=!history || source.reset || paused_ns!=current_pause;
    paused_ns=current_pause;
    WriteBarrier(cmdbuf,vk::Image(snapshot->generated));
    FfxVkFsr3_3_1_6FrameGenerationPrepareInfo prepare{};
    prepare.commandBuffer=cmdbuf;
    prepare.color=Describe(vk::Image(snapshot->color),vk::Format::eR16G16B16A16Sfloat,width,height);
    prepare.depth=Describe(vk::Image(snapshot->depth),vk::Format::eR32Sfloat,render_width,render_height);
    prepare.motionVectors=Describe(vk::Image(snapshot->motion),vk::Format::eR16G16Sfloat,render_width,render_height);
    prepare.renderWidth=render_width; prepare.renderHeight=render_height;
    prepare.jitterOffsetX=source.jitter[0]; prepare.jitterOffsetY=source.jitter[1];
    prepare.motionVectorScaleX=prepare.motionVectorScaleY=1.0f;
    prepare.frameTimeMilliseconds=std::clamp(source.frame_ms,1.0f,100.0f);
    prepare.minLuminance=0.0f; prepare.maxLuminance=snapshot->hdr ? 10000.0f : 80.0f;
    prepare.transferFunction=FFX_VK_FSR3_3_1_6_FRAMEGEN_TRANSFER_SCRGB;
    prepare.cameraNear=source.near_plane; prepare.cameraFar=3000.0f;
    prepare.viewSpaceToMeters=1.0f; prepare.cameraVerticalFovRadians=source.vertical_fov;
    for (u32 i=0;i<3;++i) {
        prepare.cameraPosition[i]=source.inverse_view[i*4+3];
        prepare.cameraRight[i]=source.inverse_view[i*4];
        prepare.cameraUp[i]=source.inverse_view[i*4+1];
        prepare.cameraForward[i]=source.inverse_view[i*4+2];
    }
    prepare.frameId=++frame_id; prepare.reset=reset;
    recording={frame_id,0,snapshot};
    auto result=ffxVkFsr3_3_1_6FrameGenerationContextRecordPrepare(context,&prepare);
    if (result==FFX_VK_FSR3_3_1_6_FRAMEGEN_OK) {
        FfxVkFsr3_3_1_6FrameGenerationDispatchInfo dispatch{};
        dispatch.commandBuffer=cmdbuf; dispatch.color=prepare.color;
        dispatch.output=Describe(vk::Image(snapshot->generated),vk::Format::eR16G16B16A16Sfloat,width,height);
        dispatch.displayWidth=width; dispatch.displayHeight=height;
        dispatch.interpolationWidth=width; dispatch.interpolationHeight=height;
        dispatch.frameTimeMilliseconds=prepare.frameTimeMilliseconds;
        dispatch.cameraNear=prepare.cameraNear; dispatch.cameraFar=prepare.cameraFar;
        dispatch.viewSpaceToMeters=prepare.viewSpaceToMeters;
        dispatch.cameraVerticalFovRadians=prepare.cameraVerticalFovRadians;
        dispatch.minLuminance=prepare.minLuminance; dispatch.maxLuminance=prepare.maxLuminance;
        dispatch.transferFunction=prepare.transferFunction; dispatch.frameId=frame_id; dispatch.reset=reset;
        result=ffxVkFsr3_3_1_6FrameGenerationContextRecordDispatch(context,&dispatch);
    }
    if (result!=FFX_VK_FSR3_3_1_6_FRAMEGEN_OK) {
        std::printf("FSR Frame Generation: prepare/dispatch failed (%d)\n",int(result));
        settings.frame_generation_problem="FSR FG dispatch failed. The real frame is kept; turn FG off and on to retry.";
        failed=true; Invalidate(); return false;
    }
    if (snapshot->hdr || snapshot->sdr_unorm) {
        // FI writes linear FP16; a plain blit into a PQ swapchain would clamp
        // the HDR highlights. Encode into stable FP16 PQ, then blit to UNORM10.
        const vk::MemoryBarrier2 ready{.srcStageMask=vk::PipelineStageFlagBits2::eAllCommands,
            .srcAccessMask=vk::AccessFlagBits2::eMemoryWrite,.dstStageMask=vk::PipelineStageFlagBits2::eComputeShader,
            .dstAccessMask=vk::AccessFlagBits2::eShaderRead};
        cmdbuf.pipelineBarrier2({.memoryBarrierCount=1,.pMemoryBarriers=&ready});
        WriteBarrier(cmdbuf,vk::Image(snapshot->encoded));
        const std::array<vk::DescriptorImageInfo,6> images{{
            {.imageView=*snapshot->generated_view,.imageLayout=vk::ImageLayout::eGeneral},
            {.imageView=source.depth_view,.imageLayout=vk::ImageLayout::eGeneral},
            {.imageView=source.motion_view,.imageLayout=vk::ImageLayout::eGeneral},
            {.imageView=*snapshot->encoded_view,.imageLayout=vk::ImageLayout::eGeneral},
            {.imageView=*snapshot->depth_view,.imageLayout=vk::ImageLayout::eGeneral},
            {.imageView=*snapshot->motion_view,.imageLayout=vk::ImageLayout::eGeneral}}};
        std::array<vk::WriteDescriptorSet,6> writes{};
        for (u32 i=0;i<6;++i) writes[i]={.dstBinding=i,.descriptorCount=1,
            .descriptorType=i<2 ? vk::DescriptorType::eSampledImage : vk::DescriptorType::eStorageImage,.pImageInfo=&images[i]};
        cmdbuf.bindPipeline(vk::PipelineBindPoint::eCompute,*copy_pipeline);
        cmdbuf.pushDescriptorSetKHR(vk::PipelineBindPoint::eCompute,*copy_layout,0,writes);
        const std::array<u32,5> parameters{source.render_width,source.render_height,render_width,render_height,snapshot->hdr ? 2u : 5u};
        cmdbuf.pushConstants(*copy_layout,vk::ShaderStageFlagBits::eCompute,0,20,parameters.data());
        cmdbuf.dispatch((width+7)/8,(height+7)/8,1);
    }
    history=true; settings.frame_generation_active=reset ? 0 : 2;
    settings.frame_generation_problem=nullptr;
    return !reset;
}
void FrameGeneration::Submitted(u64 tick) {
    if (recording.snapshot) { recording.tick=tick; pending.push_back(std::move(recording)); recording={}; }
}
} // namespace Vulkan
