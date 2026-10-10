// SPDX-License-Identifier: GPL-2.0-or-later
#include "video_core/renderer_vulkan/vk_frame_generation.h"
#include "bbport_background.h"
#include "bbport_settings.h"
#define VMA_IMPLEMENTATION
#include <vk_mem_alloc.h>
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <vector>
#ifdef _WIN32
#include <windows.h>
#else
#include <dlfcn.h>
#endif

VULKAN_HPP_DEFAULT_DISPATCH_LOADER_DYNAMIC_STORAGE

namespace {
unsigned validation_errors{}, validation_warnings{};
VKAPI_ATTR VkBool32 VKAPI_CALL Validation(vk::DebugUtilsMessageSeverityFlagBitsEXT severity,
    vk::DebugUtilsMessageTypeFlagsEXT, const vk::DebugUtilsMessengerCallbackDataEXT* data, void*) {
    if (severity == vk::DebugUtilsMessageSeverityFlagBitsEXT::eError) ++validation_errors;
    if (severity == vk::DebugUtilsMessageSeverityFlagBitsEXT::eWarning) ++validation_warnings;
    std::fprintf(stderr,"Frame Generation validation: %s\n",data->pMessage);
    return VK_FALSE;
}
void Check(vk::Result result) {
    if (result!=vk::Result::eSuccess) throw std::runtime_error(vk::to_string(result));
}
template<class T> T Check(vk::ResultValue<T> result) {
    Check(result.result); return std::move(result.value);
}
struct Buffer {
    VmaAllocator allocator{};
    VkBuffer buffer{};
    VmaAllocation allocation{};
    void* mapped{};
    Buffer(VmaAllocator allocator_, size_t bytes) : allocator{allocator_} {
        const VkBufferCreateInfo create{.sType=VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,.size=bytes,
            .usage=VK_BUFFER_USAGE_TRANSFER_SRC_BIT|VK_BUFFER_USAGE_TRANSFER_DST_BIT};
        const VmaAllocationCreateInfo memory{
            .flags=VMA_ALLOCATION_CREATE_MAPPED_BIT|VMA_ALLOCATION_CREATE_HOST_ACCESS_RANDOM_BIT,
            .usage=VMA_MEMORY_USAGE_AUTO_PREFER_HOST};
        VmaAllocationInfo info{};
        Check(vk::Result(vmaCreateBuffer(allocator,&create,&memory,&buffer,&allocation,&info)));
        mapped=info.pMappedData;
    }
    ~Buffer() { vmaDestroyBuffer(allocator,buffer,allocation); }
};
struct InputImage {
    VmaAllocator allocator{};
    VkImage image{};
    VmaAllocation allocation{};
    vk::UniqueImageView view;
    InputImage(vk::Device device, VmaAllocator allocator_, vk::Format format,
               u32 w, u32 h, vk::ImageAspectFlags aspect, bool storage=false) : allocator{allocator_} {
        const vk::ImageCreateInfo create{.imageType=vk::ImageType::e2D,.format=format,.extent={w,h,1},
            .mipLevels=1,.arrayLayers=1,.samples=vk::SampleCountFlagBits::e1,
            .usage=vk::ImageUsageFlagBits::eSampled|vk::ImageUsageFlagBits::eTransferSrc|
                   vk::ImageUsageFlagBits::eTransferDst|(storage ? vk::ImageUsageFlagBits::eStorage : vk::ImageUsageFlags{})};
        const VkImageCreateInfo raw=create;
        const VmaAllocationCreateInfo memory{.usage=VMA_MEMORY_USAGE_AUTO_PREFER_DEVICE};
        Check(vk::Result(vmaCreateImage(allocator,&raw,&memory,&image,&allocation,nullptr)));
        view=Check(device.createImageViewUnique({.image=image,.viewType=vk::ImageViewType::e2D,
            .format=format,.subresourceRange={aspect,0,1,0,1}}));
    }
    ~InputImage() { view.reset(); vmaDestroyImage(allocator,image,allocation); }
};
struct Device {
    vk::UniqueInstance instance;
    vk::UniqueDebugUtilsMessengerEXT messenger;
    vk::PhysicalDevice physical;
    vk::UniqueDevice device;
    VmaAllocator allocator{};
    vk::Queue queue;
    vk::UniqueCommandPool pool;
    vk::UniqueSemaphore timeline;
    u64 tick{}, wait_calls{};
    bool hold_retirement{};

    bool Create() {
#ifdef _WIN32
        const auto library=LoadLibraryW(L"vulkan-1.dll");
        const auto proc=reinterpret_cast<PFN_vkGetInstanceProcAddr>(GetProcAddress(library,"vkGetInstanceProcAddr"));
#else
        const auto library=dlopen("libvulkan.so.1",RTLD_NOW|RTLD_LOCAL);
        const auto proc=library ? reinterpret_cast<PFN_vkGetInstanceProcAddr>(dlsym(library,"vkGetInstanceProcAddr")) : nullptr;
#endif
        if (!proc) return false;
        VULKAN_HPP_DEFAULT_DISPATCHER.init(proc);
        const auto layers=Check(vk::enumerateInstanceLayerProperties());
        if (std::none_of(layers.begin(),layers.end(),[](const auto& layer) {
            return std::strcmp(layer.layerName,"VK_LAYER_KHRONOS_validation")==0;
        })) return false;
        const char* layer="VK_LAYER_KHRONOS_validation";
        const char* extensions[]={VK_EXT_DEBUG_UTILS_EXTENSION_NAME,VK_EXT_VALIDATION_FEATURES_EXTENSION_NAME};
        const vk::ValidationFeatureEnableEXT sync=vk::ValidationFeatureEnableEXT::eSynchronizationValidation;
        const vk::ValidationFeaturesEXT validation{.enabledValidationFeatureCount=1,.pEnabledValidationFeatures=&sync};
        const vk::DebugUtilsMessengerCreateInfoEXT debug{
            .pNext=&validation,
            .messageSeverity=vk::DebugUtilsMessageSeverityFlagBitsEXT::eWarning|vk::DebugUtilsMessageSeverityFlagBitsEXT::eError,
            .messageType=vk::DebugUtilsMessageTypeFlagBitsEXT::eValidation|vk::DebugUtilsMessageTypeFlagBitsEXT::ePerformance,
            .pfnUserCallback=Validation};
        const vk::ApplicationInfo app{.pApplicationName="TatsunaKyo Frame Generation test",.apiVersion=VK_API_VERSION_1_3};
        instance=Check(vk::createInstanceUnique({.pNext=&debug,.pApplicationInfo=&app,.enabledLayerCount=1,
            .ppEnabledLayerNames=&layer,.enabledExtensionCount=2,.ppEnabledExtensionNames=extensions}));
        VULKAN_HPP_DEFAULT_DISPATCHER.init(*instance);
        auto debug_create=debug; debug_create.pNext=nullptr;
        messenger=Check(instance->createDebugUtilsMessengerEXTUnique(debug_create));
        const auto devices=Check(instance->enumeratePhysicalDevices());
        if (devices.empty()) return false;
        physical=devices.front();
        const auto families=physical.getQueueFamilyProperties();
        u32 family=0;
        while (family<families.size() && !(families[family].queueFlags&vk::QueueFlagBits::eCompute)) ++family;
        if (family==families.size()) return false;
        const auto features=physical.getFeatures2<vk::PhysicalDeviceFeatures2,
            vk::PhysicalDeviceVulkan12Features,vk::PhysicalDeviceVulkan13Features,
            vk::PhysicalDeviceComputeShaderDerivativesFeaturesKHR>();
        const auto base=features.get<vk::PhysicalDeviceFeatures2>().features;
        const auto v12=features.get<vk::PhysicalDeviceVulkan12Features>();
        const auto v13=features.get<vk::PhysicalDeviceVulkan13Features>();
        if (!v12.timelineSemaphore || !v13.synchronization2 || !base.shaderStorageImageExtendedFormats ||
            !base.shaderStorageImageReadWithoutFormat || !base.shaderStorageImageWriteWithoutFormat) return false;
        const auto available=Check(physical.enumerateDeviceExtensionProperties());
        auto has=[&](const char* name) { return std::any_of(available.begin(),available.end(),[&](const auto& ext) {
            return std::strcmp(ext.extensionName,name)==0;
        }); };
        if (!has(VK_KHR_PUSH_DESCRIPTOR_EXTENSION_NAME)) return false;
        std::vector<const char*> enabled{VK_KHR_PUSH_DESCRIPTOR_EXTENSION_NAME};
        vk::PhysicalDeviceComputeShaderDerivativesFeaturesKHR derivative{};
        if (has(VK_KHR_COMPUTE_SHADER_DERIVATIVES_EXTENSION_NAME) &&
            features.get<vk::PhysicalDeviceComputeShaderDerivativesFeaturesKHR>().computeDerivativeGroupLinear) {
            enabled.push_back(VK_KHR_COMPUTE_SHADER_DERIVATIVES_EXTENSION_NAME);
            derivative.computeDerivativeGroupLinear=true;
        }
        vk::PhysicalDeviceVulkan13Features enabled13{.synchronization2=true};
        vk::PhysicalDeviceVulkan12Features enabled12{.pNext=&enabled13,.timelineSemaphore=true};
        enabled13.pNext=derivative.computeDerivativeGroupLinear ? &derivative : nullptr;
        const vk::PhysicalDeviceFeatures enabled_base{.shaderStorageImageExtendedFormats=true,
            .shaderStorageImageReadWithoutFormat=true,.shaderStorageImageWriteWithoutFormat=true};
        const float priority=1;
        const vk::DeviceQueueCreateInfo create_queue{.queueFamilyIndex=family,.queueCount=1,.pQueuePriorities=&priority};
        device=Check(physical.createDeviceUnique({.pNext=&enabled12,.queueCreateInfoCount=1,.pQueueCreateInfos=&create_queue,
            .enabledExtensionCount=u32(enabled.size()),.ppEnabledExtensionNames=enabled.data(),.pEnabledFeatures=&enabled_base}));
        VULKAN_HPP_DEFAULT_DISPATCHER.init(*device);
        queue=device->getQueue(family,0);
        pool=Check(device->createCommandPoolUnique({.flags=vk::CommandPoolCreateFlagBits::eResetCommandBuffer,.queueFamilyIndex=family}));
        const vk::SemaphoreTypeCreateInfo type{.semaphoreType=vk::SemaphoreType::eTimeline};
        timeline=Check(device->createSemaphoreUnique({.pNext=&type}));
        const VmaVulkanFunctions functions{.vkGetInstanceProcAddr=proc,.vkGetDeviceProcAddr=VULKAN_HPP_DEFAULT_DISPATCHER.vkGetDeviceProcAddr};
        const VmaAllocatorCreateInfo create_allocator{.physicalDevice=physical,.device=*device,
            .pVulkanFunctions=&functions,.instance=*instance,.vulkanApiVersion=VK_API_VERSION_1_3};
        Check(vk::Result(vmaCreateAllocator(&create_allocator,&allocator)));
        std::printf("Frame Generation test device: %s\n",physical.getProperties().deviceName.data());
        return true;
    }
    ~Device() {
        if (device) Check(device->waitIdle());
        if (allocator) vmaDestroyAllocator(allocator);
    }
    vk::UniqueCommandBuffer Begin() {
        auto buffers=Check(device->allocateCommandBuffersUnique({.commandPool=*pool,
            .level=vk::CommandBufferLevel::ePrimary,.commandBufferCount=1}));
        auto buffer=std::move(buffers.front()); Check(buffer->begin(vk::CommandBufferBeginInfo{})); return buffer;
    }
    u64 Submit(vk::CommandBuffer command) {
        Check(command.end());
        const vk::CommandBufferSubmitInfo cmd{.commandBuffer=command};
        const vk::SemaphoreSubmitInfo signal{.semaphore=*timeline,.value=++tick,.stageMask=vk::PipelineStageFlagBits2::eAllCommands};
        Check(queue.submit2(vk::SubmitInfo2{.commandBufferInfoCount=1,.pCommandBufferInfos=&cmd,
            .signalSemaphoreInfoCount=1,.pSignalSemaphoreInfos=&signal}));
        Wait(tick); return tick;
    }
    void Wait(u64 value) {
        ++wait_calls;
        Check(device->waitSemaphores({.semaphoreCount=1,.pSemaphores=&*timeline,.pValues=&value},UINT64_MAX));
    }
    bool Free(u64 value) { return !hold_retirement && Check(device->getSemaphoreCounterValue(*timeline))>=value; }
    Vulkan::FrameGeneration::Submissions Submissions() {
        return {[this] { Wait(tick); },[this](u64 value) { Wait(value); },[this](u64 value) { return Free(value); }};
    }
    std::vector<std::byte> Read(vk::Image image, u32 w, u32 h, unsigned pixel_bytes) {
        Buffer output(allocator,size_t(w)*h*pixel_bytes);
        auto cmd=Begin();
        const vk::MemoryBarrier2 ready{.srcStageMask=vk::PipelineStageFlagBits2::eAllCommands,
            .srcAccessMask=vk::AccessFlagBits2::eMemoryWrite,.dstStageMask=vk::PipelineStageFlagBits2::eTransfer,
            .dstAccessMask=vk::AccessFlagBits2::eTransferRead};
        cmd->pipelineBarrier2({.memoryBarrierCount=1,.pMemoryBarriers=&ready});
        cmd->copyImageToBuffer(image,vk::ImageLayout::eGeneral,output.buffer,
            vk::BufferImageCopy{.imageSubresource={vk::ImageAspectFlagBits::eColor,0,0,1},.imageExtent={w,h,1}});
        Submit(*cmd);
        vmaInvalidateAllocation(allocator,output.allocation,0,VK_WHOLE_SIZE);
        const auto* bytes=static_cast<const std::byte*>(output.mapped);
        return {bytes,bytes+size_t(w)*h*pixel_bytes};
    }
};
float Half(u16 bits) {
    const u32 exp=(bits>>10)&31, mantissa=bits&1023;
    const float sign=bits&0x8000 ? -1.0f : 1.0f;
    if (exp==31) return mantissa ? NAN : sign*INFINITY;
    return sign*std::ldexp(exp ? 1+float(mantissa)/1024 : float(mantissa)/1024,int(exp ? exp : 1)-15);
}
struct Inputs {
    Device& gpu;
    u32 rw,rh,w,h;
    vk::Format color_format;
    InputImage color,depth,motion;
    Inputs(Device& gpu_,u32 rw_,u32 rh_,u32 w_,u32 h_,bool hdr=false)
        : gpu{gpu_},rw{rw_},rh{rh_},w{w_},h{h_},
          color_format{hdr ? vk::Format::eA2B10G10R10UnormPack32 : vk::Format::eR8G8B8A8Srgb},
          color{*gpu.device,gpu.allocator,color_format,w,h,vk::ImageAspectFlagBits::eColor},
          depth{*gpu.device,gpu.allocator,vk::Format::eD32Sfloat,rw,rh,vk::ImageAspectFlagBits::eDepth},
          motion{*gpu.device,gpu.allocator,vk::Format::eR16G16Sfloat,rw,rh,vk::ImageAspectFlagBits::eColor,true} {
        auto cmd=gpu.Begin();
        const std::array images{color.image,depth.image,motion.image};
        for (u32 i=0;i<3;++i) {
            const vk::ImageMemoryBarrier2 barrier{.dstStageMask=vk::PipelineStageFlagBits2::eTransfer,
                .dstAccessMask=vk::AccessFlagBits2::eTransferWrite,.oldLayout=vk::ImageLayout::eUndefined,
                .newLayout=vk::ImageLayout::eGeneral,.image=images[i],
                .subresourceRange={i==1 ? vk::ImageAspectFlagBits::eDepth : vk::ImageAspectFlagBits::eColor,0,1,0,1}};
            cmd->pipelineBarrier2({.imageMemoryBarrierCount=1,.pImageMemoryBarriers=&barrier});
        }
        Buffer upload(gpu.allocator,size_t(w)*h*4);
        auto* pixels=static_cast<unsigned char*>(upload.mapped);
        for (u32 i=0;i<w*h;++i) { pixels[i*4]=128; pixels[i*4+1]=64; pixels[i*4+2]=192; pixels[i*4+3]=255; }
        if (hdr) {
            const auto pq=[](double nits) {
                const double p=std::pow(nits/10000.0,0.1593017578125);
                return uint32_t(std::round(std::pow((0.8359375+18.8515625*p)/(1+18.6875*p),78.84375)*1023));
            };
            const uint32_t pixel=pq(1000) | (pq(500)<<10) | (pq(2000)<<20) | (3u<<30);
            for (u32 i=0;i<w*h;++i) std::memcpy(pixels+i*4,&pixel,4);
        }
        vmaFlushAllocation(gpu.allocator,upload.allocation,0,VK_WHOLE_SIZE);
        cmd->copyBufferToImage(upload.buffer,color.image,vk::ImageLayout::eGeneral,
            vk::BufferImageCopy{.imageSubresource={vk::ImageAspectFlagBits::eColor,0,0,1},.imageExtent={w,h,1}});
        cmd->clearDepthStencilImage(depth.image,vk::ImageLayout::eGeneral,{.depth=.5f},
                                   vk::ImageSubresourceRange{vk::ImageAspectFlagBits::eDepth,0,1,0,1});
        cmd->clearColorImage(motion.image,vk::ImageLayout::eGeneral,
            vk::ClearColorValue{std::array<float,4>{4,-2,0,0}},
            vk::ImageSubresourceRange{vk::ImageAspectFlagBits::eColor,0,1,0,1});
        gpu.Submit(*cmd);
    }
    Vulkan::FrameGenerationSource Source(bool reset=false) {
        Vulkan::FrameGenerationSource source{*depth.view,motion.image,*motion.view,rw,rh,{.25f,-.5f},
                                            {1,0,0,0,0,1,0,0,0,0,1,0},.1f,1.047f,16.666f,reset,true};
        return source;
    }
    void Capture(Vulkan::FrameGeneration& fg,std::shared_ptr<Vulkan::FrameGeneration::Snapshot>& snapshot,bool reset=false) {
        auto cmd=gpu.Begin(); fg.Capture(*cmd,Source(reset),*color.view,w,h,color_format,snapshot);
        gpu.Submit(*cmd);
    }
};
bool Generate(Device& gpu,Vulkan::FrameGeneration& fg,const std::shared_ptr<Vulkan::FrameGeneration::Snapshot>& snapshot) {
    auto cmd=gpu.Begin(); const bool generated=fg.Record(*cmd,snapshot);
    fg.Submitted(gpu.Submit(*cmd)); return generated;
}
void Test(Device& gpu) {
    auto& settings=BbSettings::Get();
    settings.window_focused=true; settings.background_mode=BbSettings::BackgroundRun;
    Vulkan::FrameGeneration fg(gpu.physical,*gpu.device,gpu.allocator,gpu.Submissions());
    Inputs inputs(gpu,64,64,128,128);
    std::shared_ptr<Vulkan::FrameGeneration::Snapshot> snapshot;
    settings.frame_generation=BbSettings::FrameGenerationOff;
    inputs.Capture(fg,snapshot); assert(!snapshot);
    assert(!fg.Record({},snapshot)); assert(settings.frame_generation_active==0);
    settings.frame_generation=BbSettings::FrameGenerationFsr;
    inputs.Capture(fg,snapshot); assert(snapshot);
    const auto colors=gpu.Read(vk::Image(snapshot->color),128,128,8);
    const auto* color=reinterpret_cast<const u16*>(colors.data());
    std::fprintf(stderr,"Captured linear RGB: %.6f %.6f %.6f\n",Half(color[0]),Half(color[1]),Half(color[2]));
    // Allow the implementation's sRGB lookup precision and half-float rounding.
    assert(std::abs(Half(color[0])-.21586f)<.002f);
    assert(std::abs(Half(color[1])-.05127f)<.002f);
    assert(std::abs(Half(color[2])-.52712f)<.002f);
    assert(Half(color[3])==1);
    const auto depths=gpu.Read(vk::Image(snapshot->depth),64,64,4);
    assert(*reinterpret_cast<const float*>(depths.data())==.5f);
    const auto motions=gpu.Read(vk::Image(snapshot->motion),64,64,4);
    const auto* motion=reinterpret_cast<const u16*>(motions.data());
    assert(Half(motion[0])==4 && Half(motion[1])==-2);
    assert(!Generate(gpu,fg,snapshot)); assert(settings.frame_generation_active==0);
    inputs.Capture(fg,snapshot);
    assert(Generate(gpu,fg,snapshot)); assert(settings.frame_generation_active==2);
    const auto generated=gpu.Read(vk::Image(snapshot->generated),128,128,8);
    const auto* output=reinterpret_cast<const u16*>(generated.data());
    unsigned lit=0;
    for (u32 i=0;i<128*128*4;++i) {
        assert(std::isfinite(Half(output[i])));
        if (i%4!=3 && Half(output[i])>.01f) ++lit;
    }
    assert(lit>128*128); // Actual GPU output, rather than just a successful SDK return.
    settings.upscaler=BbSettings::UpscalerOff;
    inputs.Capture(fg,snapshot); assert(!snapshot);
    assert(!fg.Record({},snapshot)); assert(settings.frame_generation_active==0);
    settings.upscaler=BbSettings::UpscalerFsr3;
    inputs.Capture(fg,snapshot); assert(!Generate(gpu,fg,snapshot));
    inputs.Capture(fg,snapshot); assert(Generate(gpu,fg,snapshot));
    gpu.hold_retirement=true;
    inputs.Capture(fg,snapshot); assert(Generate(gpu,fg,snapshot));
    const std::weak_ptr<Vulkan::FrameGeneration::Snapshot> retained=snapshot;
    snapshot.reset(); assert(!retained.expired());
    fg.Record({},snapshot); assert(!retained.expired());
    gpu.hold_retirement=false;
    fg.Record({},snapshot); assert(retained.expired());
    inputs.Capture(fg,snapshot); assert(!Generate(gpu,fg,snapshot));
    inputs.Capture(fg,snapshot); assert(Generate(gpu,fg,snapshot));
    BbBackground::Update(true); BbBackground::Update(false);
    inputs.Capture(fg,snapshot); assert(!Generate(gpu,fg,snapshot));
    for (const auto mode : {BbSettings::Background30,BbSettings::Background60,BbSettings::BackgroundPause}) {
        settings.window_focused=false; settings.background_mode=mode;
        inputs.Capture(fg,snapshot); assert(!snapshot);
        assert(!fg.Record({},snapshot)); assert(settings.frame_generation_active==0);
        settings.window_focused=true;
        inputs.Capture(fg,snapshot); assert(!Generate(gpu,fg,snapshot));
        inputs.Capture(fg,snapshot); assert(Generate(gpu,fg,snapshot));
    }
    Inputs reduced(gpu,256,256,128,128);
    reduced.Capture(fg,snapshot); assert(snapshot->source.render_width==128 && snapshot->source.render_height==128);
    assert(snapshot->source.jitter[0]==.125f && snapshot->source.jitter[1]==-.25f);
    const auto scaled=gpu.Read(vk::Image(snapshot->motion),128,128,4);
    const auto* mv=reinterpret_cast<const u16*>(scaled.data());
    assert(Half(mv[0])==2 && Half(mv[1])==-1);
    assert(!Generate(gpu,fg,snapshot));
    reduced.Capture(fg,snapshot); assert(Generate(gpu,fg,snapshot));
    Inputs resized(gpu,64,64,192,192);
    resized.Capture(fg,snapshot); assert(!Generate(gpu,fg,snapshot));
    resized.Capture(fg,snapshot); assert(Generate(gpu,fg,snapshot));
    Inputs hdr(gpu,64,64,128,128,true);
    hdr.Capture(fg,snapshot); assert(snapshot && snapshot->hdr);
    const auto hdr_colors=gpu.Read(vk::Image(snapshot->color),128,128,8);
    const auto* linear=reinterpret_cast<const u16*>(hdr_colors.data());
    assert(std::abs(Half(linear[0])-12.5f)<.12f);
    assert(std::abs(Half(linear[1])-6.25f)<.08f);
    assert(std::abs(Half(linear[2])-25.0f)<.25f);
    assert(!Generate(gpu,fg,snapshot));
    hdr.Capture(fg,snapshot);assert(Generate(gpu,fg,snapshot));
    const auto hdr_generated=gpu.Read(vk::Image(snapshot->generated),128,128,8);
    const auto* hdr_output=reinterpret_cast<const u16*>(hdr_generated.data());
    unsigned highlights=0;
    for (u32 i=0;i<128*128*4;++i) {
        assert(std::isfinite(Half(hdr_output[i])));
        if (i%4!=3 && Half(hdr_output[i])>1.0f) ++highlights;
    }
    assert(highlights>128*128);
    const auto hdr_encoded=gpu.Read(snapshot->PresentImage(),128,128,8);
    const auto* pq=reinterpret_cast<const u16*>(hdr_encoded.data());
    assert(std::abs(Half(pq[0])-.751827f)<.01f);
    assert(std::abs(Half(pq[1])-.676585f)<.01f);
    assert(std::abs(Half(pq[2])-.827425f)<.01f);
    inputs.Capture(fg,snapshot);assert(!snapshot->hdr && !Generate(gpu,fg,snapshot));
    inputs.Capture(fg,snapshot);assert(Generate(gpu,fg,snapshot));
    std::puts("PASS: HDR10 500/1000/2000-nit decode, FI/OF highlights above SDR white, PQ re-encoding, HDR-to-SDR history reset.");
    settings.frame_generation=BbSettings::FrameGenerationNvidia;
    for (auto* input : {&inputs,&hdr,&reduced}) {
        input->Capture(fg,snapshot);
        assert(snapshot && snapshot->nvidia_input_only);
        assert(!vk::Image(snapshot->generated) && !vk::Image(snapshot->encoded));
        const auto depth_copy=gpu.Read(vk::Image(snapshot->depth),snapshot->source.render_width,snapshot->source.render_height,4);
        const auto motion_copy=gpu.Read(vk::Image(snapshot->motion),snapshot->source.render_width,snapshot->source.render_height,4);
        assert(*reinterpret_cast<const float*>(depth_copy.data())==.5f);
        const auto* mv_copy=reinterpret_cast<const u16*>(motion_copy.data());
        const float scale=float(snapshot->source.render_width)/input->rw;
        assert(Half(mv_copy[0])==4*scale && Half(mv_copy[1])==-2*scale);
    }
    settings.frame_generation=BbSettings::FrameGenerationFsr;
    inputs.Capture(fg,snapshot);
    assert(snapshot && !snapshot->nvidia_input_only && vk::Image(snapshot->generated));
    std::puts("PASS: NVIDIA depth/motion capture in SDR/HDR with no unused full-resolution color/interpolation images; switching back to FSR restores its resources.");
    settings.frame_generation=BbSettings::FrameGenerationOff;
    inputs.Capture(fg,snapshot); assert(!snapshot); assert(!fg.Record({},snapshot));
    settings.frame_generation=BbSettings::FrameGenerationFsr;
    inputs.Capture(fg,snapshot); assert(!Generate(gpu,fg,snapshot));
    fg.Reset();
    snapshot.reset();
    assert(!settings.frame_generation_problem.load());
    assert(gpu.wait_calls>0);
}
} // namespace
int main() {
    try {
        { Device gpu; if (!gpu.Create()) { std::puts("SKIP: Vulkan GPU and current Khronos validation layer required."); return 77; }
          Test(gpu); }
        assert(validation_errors==0);
        std::printf("Frame Generation integration: GPU color/depth/motion copies, real FI/OF output, history reset, queue lifetime, resize and background modes passed; validation errors=%u, warnings=%u.\n",
                    validation_errors,validation_warnings);
    } catch (const std::exception& error) {
        std::fprintf(stderr,"Frame Generation test failed: %s\n",error.what()); return 1;
    }
}
