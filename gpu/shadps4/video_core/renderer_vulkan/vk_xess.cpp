// SPDX-License-Identifier: GPL-2.0-or-later
#include "video_core/renderer_vulkan/vk_xess.h"
#include "bbport_settings.h"
#include <algorithm>
#include <array>
#include <cstdio>
#include <cstdlib>
#include <deque>
#include <filesystem>
#include <optional>
#include <string_view>
#ifdef _WIN32
#include <windows.h>
#endif

namespace Vulkan {
struct Xess::Impl {
    Api api;
    bool eligible{true},instance_ready{},extensions_ready{},features_ready{},ready{};
    vk::Instance instance;
    vk::PhysicalDevice physical;
    vk::Device device;
    xess_context_handle_t context{};
    std::optional<FeatureDesc> feature;
    std::vector<std::string> instance_names,device_names;
    // Menu readers can still hold an older message; retain its storage.
    std::deque<std::string> problems;
    void Disable(std::string message) {
        eligible=ready=false;problems.push_back(std::move(message));
        BbSettings::Get().xess_supported=false;
        BbSettings::Get().xess_problem=problems.back().c_str();
        std::printf("XeSS: %s\n",problems.back().c_str());
    }
    bool Check(xess_result_t result,const char* operation) {
        if (result>=0) return true;
        Disable(std::string{operation}+" failed ("+std::to_string(int(result))+"), using FSR 3.1.");
        return false;
    }
};
namespace {
bool Extensions(const char* const* names,u32 count,
                const std::vector<vk::ExtensionProperties>& available,
                std::vector<std::string>& storage,std::vector<const char*>& enabled) {
    storage.clear();
    for (u32 i=0;i<count;++i) {
        if (!names || !names[i] || std::ranges::none_of(available,[&](const auto& e) {
                return std::string_view{e.extensionName.data()}==names[i]; })) return false;
        storage.emplace_back(names[i]);
    }
    for (const auto& name:storage)
        if (std::ranges::none_of(enabled,[&](const char* current) {return name==current;}))
            enabled.push_back(name.c_str());
    return true;
}
xess_vk_image_view_info Image(const Xess::Resource& r) {
    return {VkImageView(r.view),VkImage(r.image),{VkImageAspectFlags(r.aspect),0,1,0,1},
            VkFormat(r.format),r.width,r.height};
}
}
Xess* Xess::Get() {
#ifdef _WIN32
    static Xess* const xess=[]() -> Xess* {
        if (const char* value=std::getenv("BB_XESS");value && value[0]=='0') return nullptr;
        wchar_t executable[32768]{};GetModuleFileNameW(nullptr,executable,32768);
        const auto path=std::filesystem::path{executable}.parent_path()/L"xess"/L"libxess.dll";
        if (!std::filesystem::is_regular_file(path)) return nullptr;
        const HMODULE module=LoadLibraryExW(path.c_str(),nullptr,
            LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
        if (!module) return nullptr;
        Api api;
#define IMPORT(field,name) api.field=reinterpret_cast<decltype(api.field)>(GetProcAddress(module,name))
        IMPORT(instance_extensions,"xessVKGetRequiredInstanceExtensions");
        IMPORT(device_extensions,"xessVKGetRequiredDeviceExtensions");
        IMPORT(device_features,"xessVKGetRequiredDeviceFeatures");IMPORT(create,"xessVKCreateContext");
        IMPORT(init,"xessVKInit");IMPORT(execute,"xessVKExecute");
        IMPORT(velocity,"xessSetVelocityScale");IMPORT(destroy,"xessDestroyContext");
#undef IMPORT
        if (!api.instance_extensions || !api.device_extensions || !api.device_features ||
            !api.create || !api.init || !api.execute || !api.velocity || !api.destroy) {
            FreeLibrary(module);return nullptr;
        }
        // Keep the library loaded while Vulkan device/SDK-owned chains exist.
        auto* value=new Xess(api);
        std::atexit([] { if (auto* value=Get()) value->Shutdown(); });
        return value;
    }();
    return xess;
#else
    return nullptr;
#endif
}
Xess::Xess(Api api):impl{std::make_unique<Impl>()} {impl->api=api;}
Xess::~Xess() {Shutdown();}
void Xess::AppendInstanceExtensions(std::vector<const char*>& enabled,u32 api_version) {
    if (!impl->eligible) return;
    u32 count{},minimum{};const char* const* names{};
    if (!impl->Check(impl->api.instance_extensions(&count,&names,&minimum),"instance query")) return;
    const auto [result,available]=vk::enumerateInstanceExtensionProperties();
    if (result!=vk::Result::eSuccess || api_version<minimum ||
        !Extensions(names,count,available,impl->instance_names,enabled)) {
        impl->Disable("Required Vulkan instance extensions/version are unavailable.");return;
    }
    impl->instance_ready=true;
}
void Xess::AppendDeviceExtensions(vk::Instance instance,vk::PhysicalDevice physical,
                                  std::vector<const char*>& enabled) {
    if (!impl->eligible || !impl->instance_ready) return;
    u32 count{};const char* const* names{};
    if (!impl->Check(impl->api.device_extensions(VkInstance(instance),VkPhysicalDevice(physical),
                                               &count,&names),"device query")) return;
    const auto [result,available]=physical.enumerateDeviceExtensionProperties();
    if (result!=vk::Result::eSuccess || !Extensions(names,count,available,impl->device_names,enabled)) {
        impl->Disable("Required Vulkan device extensions are unavailable on this GPU.");return;
    }
    impl->extensions_ready=true;
}
bool Xess::PrepareDeviceFeatures(vk::Instance instance,vk::PhysicalDevice physical,void*& chain) {
    if (!impl->eligible || !impl->extensions_ready) return false;
    // The caller passes a COPY of its feature chain. Failed queries cannot
    // change the device configuration used by the rest of the renderer.
    impl->features_ready=impl->Check(impl->api.device_features(VkInstance(instance),
        VkPhysicalDevice(physical),&chain),"feature query");
    return impl->features_ready;
}
void Xess::Initialize(vk::Instance instance,vk::PhysicalDevice physical,vk::Device device) {
    impl->instance=instance;impl->physical=physical;impl->device=device;
    impl->ready=impl->eligible && impl->instance_ready && impl->features_ready;
    BbSettings::Get().xess_supported=impl->ready;
}
void Xess::Shutdown() {ReleaseFeature();impl->ready=false;impl->device=nullptr;}
bool Xess::Available() const {return impl->ready;}
const char* Xess::Problem() const {return impl->problems.empty() ? nullptr:impl->problems.back().c_str();}
xess_quality_settings_t Xess::QualityForScale(float scale) {
    // Preserve the port's render sizes. Modern XeSS accepts lower-than-default
    // ratios for each mode (1.5 Ultra Quality, 1.7 Quality, 2 Balanced, 3 UP).
    return scale>=2.9f ? XESS_QUALITY_SETTING_ULTRA_PERFORMANCE :
           scale>=1.95f ? XESS_QUALITY_SETTING_BALANCED :
           scale>=1.65f ? XESS_QUALITY_SETTING_QUALITY :
           scale>1.01f ? XESS_QUALITY_SETTING_ULTRA_QUALITY : XESS_QUALITY_SETTING_AA;
}
bool Xess::HasFeature(const FeatureDesc& desc) const {return impl->context && impl->feature==desc;}
bool Xess::CreateFeature(const FeatureDesc& desc) {
    if (!Available() || impl->context) return false;
    if (!impl->Check(impl->api.create(VkInstance(impl->instance),VkPhysicalDevice(impl->physical),
                                    VkDevice(impl->device),&impl->context),"context creation")) return false;
    xess_vk_init_params_t parameters{};
    parameters.outputResolution={desc.output_width,desc.output_height};
    parameters.qualitySetting=QualityForScale(float(desc.output_width)/desc.input_width);
    parameters.initFlags=desc.hdr ? XESS_INIT_FLAG_ENABLE_AUTOEXPOSURE : XESS_INIT_FLAG_LDR_INPUT_COLOR;
    if (!impl->Check(impl->api.init(impl->context,&parameters),"initialization") ||
        !impl->Check(impl->api.velocity(impl->context,1.0f,1.0f),"motion vector scale")) {
        ReleaseFeature();return false;
    }
    impl->feature=desc;BbSettings::Get().xess_problem=nullptr;
    std::printf("XeSS: %ux%u -> %ux%u (%s)\n",desc.input_width,desc.input_height,
                desc.output_width,desc.output_height,desc.hdr ? "linear HDR" : "LDR");
    return true;
}
bool Xess::Evaluate(vk::CommandBuffer command,const Frame& frame) {
    if (!Available() || !impl->context || !impl->feature) return false;
    xess_vk_execute_params_t parameters{};
    parameters.colorTexture=Image(frame.color);parameters.depthTexture=Image(frame.depth);
    parameters.velocityTexture=Image(frame.motion);parameters.outputTexture=Image(frame.output);
    parameters.inputWidth=impl->feature->input_width;parameters.inputHeight=impl->feature->input_height;
    parameters.jitterOffsetX=frame.jitter_x;parameters.jitterOffsetY=frame.jitter_y;
    parameters.exposureScale=1.0f;parameters.resetHistory=frame.reset;
    // The port tracks sampled scene resources in General. XeSS requires all
    // three inputs in shader-read-only; restore them before post/FG capture.
    const vk::ImageMemoryBarrier2 read{.srcStageMask=vk::PipelineStageFlagBits2::eAllCommands,
        .srcAccessMask=vk::AccessFlagBits2::eMemoryWrite,.dstStageMask=vk::PipelineStageFlagBits2::eComputeShader,
        .dstAccessMask=vk::AccessFlagBits2::eShaderRead,.oldLayout=vk::ImageLayout::eGeneral,
        .newLayout=vk::ImageLayout::eShaderReadOnlyOptimal,.image=frame.motion.image,
        .subresourceRange={vk::ImageAspectFlagBits::eColor,0,1,0,1}};
    std::array<vk::ImageMemoryBarrier2,3> reads{read,read,read};
    reads[1].image=frame.depth.image;reads[1].subresourceRange.aspectMask=frame.depth.aspect;
    reads[2].image=frame.color.image;reads[2].subresourceRange.aspectMask=frame.color.aspect;
    command.pipelineBarrier2({.imageMemoryBarrierCount=3,.pImageMemoryBarriers=reads.data()});
    const auto result=impl->api.execute(impl->context,VkCommandBuffer(command),&parameters);
    auto restore=read;restore.srcStageMask=vk::PipelineStageFlagBits2::eComputeShader;
    restore.srcAccessMask=vk::AccessFlagBits2::eShaderRead;
    restore.dstStageMask=vk::PipelineStageFlagBits2::eAllCommands;
    restore.dstAccessMask=vk::AccessFlagBits2::eMemoryRead|vk::AccessFlagBits2::eMemoryWrite;
    restore.oldLayout=vk::ImageLayout::eShaderReadOnlyOptimal;restore.newLayout=vk::ImageLayout::eGeneral;
    for (auto& barrier:reads) {
        const auto image=barrier.image;const auto range=barrier.subresourceRange;
        barrier=restore;barrier.image=image;barrier.subresourceRange=range;
    }
    command.pipelineBarrier2({.imageMemoryBarrierCount=3,.pImageMemoryBarriers=reads.data()});
    return impl->Check(result,"execute");
}
void Xess::ReleaseFeature() {
    if (impl->context) {impl->api.destroy(impl->context);impl->context=nullptr;}
    impl->feature.reset();
}
}
