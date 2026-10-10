// SPDX-License-Identifier: GPL-2.0-or-later
// Test the production adapter against an injected SDK contract, without a fake DLL.
#include "video_core/renderer_vulkan/vk_xess.h"
#include "bbport_settings.h"
#include "video_core/renderer_vulkan/scene_resolution.h"
#include <cassert>
#include <cstdio>
#include <cstring>
VULKAN_HPP_DEFAULT_DISPATCH_LOADER_DYNAMIC_STORAGE
using Vulkan::Xess;
namespace SceneResolution = Vulkan::SceneResolution;
namespace {
const char* instance_name="VK_KHR_get_physical_device_properties2";
const char* device_name="VK_KHR_push_descriptor";
bool absent{},fail_execute{};
unsigned created{},destroyed{},barriers{},executes{};
xess_vk_init_params_t init_params{};
xess_vk_execute_params_t execute_params{};
VKAPI_ATTR VkResult VKAPI_CALL InstanceExt(const char*,uint32_t* count,VkExtensionProperties* properties) {
    if(!properties){*count=1;return VK_SUCCESS;}
    std::strcpy(properties->extensionName,instance_name);return VK_SUCCESS;
}
VKAPI_ATTR VkResult VKAPI_CALL DeviceExt(VkPhysicalDevice,const char*,uint32_t* count,VkExtensionProperties* properties) {
    if(!properties){*count=absent ? 0 : 1;return VK_SUCCESS;}
    std::strcpy(properties->extensionName,device_name);return VK_SUCCESS;
}
VKAPI_ATTR void VKAPI_CALL Barrier(VkCommandBuffer,const VkDependencyInfo* info) {
    assert(info->imageMemoryBarrierCount==3);
    for(unsigned i=0;i<3;++i) {
        const auto& b=info->pImageMemoryBarriers[i];
        assert(b.oldLayout==(barriers%2 ? VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL : VK_IMAGE_LAYOUT_GENERAL));
        assert(b.newLayout==(barriers%2 ? VK_IMAGE_LAYOUT_GENERAL : VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL));
        assert(b.subresourceRange.aspectMask==(i==1 ? VK_IMAGE_ASPECT_DEPTH_BIT : VK_IMAGE_ASPECT_COLOR_BIT));
    }
    ++barriers;
}
xess_result_t Instance(uint32_t* count,const char* const** names,uint32_t* version) {
    *count=1;*names=&instance_name;*version=VK_API_VERSION_1_1;return XESS_RESULT_SUCCESS;
}
xess_result_t Device(VkInstance,VkPhysicalDevice,uint32_t* count,const char* const** names) {
    *count=1;*names=&device_name;return XESS_RESULT_SUCCESS;
}
xess_result_t Features(VkInstance,VkPhysicalDevice,void**) {return XESS_RESULT_SUCCESS;}
xess_result_t Create(VkInstance,VkPhysicalDevice,VkDevice,xess_context_handle_t* out) {
    *out=reinterpret_cast<xess_context_handle_t>(uintptr_t(++created));return XESS_RESULT_SUCCESS;
}
xess_result_t Init(xess_context_handle_t,const xess_vk_init_params_t* input) {
    init_params=*input;return XESS_RESULT_SUCCESS;
}
xess_result_t Velocity(xess_context_handle_t,float x,float y) {assert(x==1 && y==1);return XESS_RESULT_SUCCESS;}
xess_result_t Execute(xess_context_handle_t,VkCommandBuffer,const xess_vk_execute_params_t* input) {
    execute_params=*input;++executes;
    return fail_execute ? XESS_RESULT_ERROR_DEVICE : XESS_RESULT_SUCCESS;
}
xess_result_t Destroy(xess_context_handle_t) {++destroyed;return XESS_RESULT_SUCCESS;}
void Prepare(Xess& xess) {
    std::vector<const char*> extensions{instance_name};
    xess.AppendInstanceExtensions(extensions,VK_API_VERSION_1_3);assert(extensions.size()==1);
    xess.AppendDeviceExtensions(vk::Instance{},vk::PhysicalDevice{(VkPhysicalDevice)1},extensions);
    void* features=nullptr;
    if(!absent) {
        assert(extensions.size()==2 && xess.PrepareDeviceFeatures({},vk::PhysicalDevice{(VkPhysicalDevice)1},features));
        xess.Initialize({},vk::PhysicalDevice{(VkPhysicalDevice)1},vk::Device{(VkDevice)1});
        assert(xess.Available());
    }
}
}
int main() {
    VULKAN_HPP_DEFAULT_DISPATCHER.vkEnumerateInstanceExtensionProperties=InstanceExt;
    VULKAN_HPP_DEFAULT_DISPATCHER.vkEnumerateDeviceExtensionProperties=DeviceExt;
    VULKAN_HPP_DEFAULT_DISPATCHER.vkCmdPipelineBarrier2=Barrier;
    Xess::Api api{Instance,Device,Features,Create,Init,Execute,Velocity,Destroy};
    {
        Xess xess(api);Prepare(xess);
        for(bool hdr : {false,true}) {
            const Xess::FeatureDesc desc{64,64,128,128,hdr};
            assert(xess.CreateFeature(desc) && xess.HasFeature(desc));
            assert(init_params.outputResolution.x==128 && init_params.qualitySetting==XESS_QUALITY_SETTING_BALANCED);
            assert(init_params.initFlags==(hdr ? XESS_INIT_FLAG_ENABLE_AUTOEXPOSURE : XESS_INIT_FLAG_LDR_INPUT_COLOR));
            Xess::Frame frame{};
            frame.color={vk::Image{(VkImage)1},vk::ImageView{(VkImageView)1},vk::Format::eR16G16B16A16Sfloat,vk::ImageAspectFlagBits::eColor,64,64};
            frame.depth={vk::Image{(VkImage)2},vk::ImageView{(VkImageView)2},vk::Format::eD32SfloatS8Uint,vk::ImageAspectFlagBits::eDepth,64,64};
            frame.motion={vk::Image{(VkImage)3},vk::ImageView{(VkImageView)3},vk::Format::eR16G16Sfloat,vk::ImageAspectFlagBits::eColor,64,64};
            frame.output={vk::Image{(VkImage)4},vk::ImageView{(VkImageView)4},vk::Format::eR16G16B16A16Sfloat,vk::ImageAspectFlagBits::eColor,128,128};
            frame.jitter_x=.25f;frame.jitter_y=-.125f;frame.reset=true;
            assert(xess.Evaluate(vk::CommandBuffer{(VkCommandBuffer)1},frame));
            assert(execute_params.inputWidth==64 && execute_params.inputHeight==64 && execute_params.resetHistory==1);
            assert(execute_params.colorTexture.format==VK_FORMAT_R16G16B16A16_SFLOAT && execute_params.depthTexture.subresourceRange.aspectMask==VK_IMAGE_ASPECT_DEPTH_BIT);
            assert(execute_params.jitterOffsetX==.25f && execute_params.jitterOffsetY==-.125f && execute_params.exposureScale==1.0f);
            xess.ReleaseFeature();assert(!xess.HasFeature(desc));
        }
        assert(created==destroyed && barriers==4 && executes==2);
        constexpr xess_quality_settings_t modes[] = {
            XESS_QUALITY_SETTING_AA, XESS_QUALITY_SETTING_ULTRA_QUALITY_PLUS,
            XESS_QUALITY_SETTING_ULTRA_QUALITY, XESS_QUALITY_SETTING_QUALITY,
            XESS_QUALITY_SETTING_BALANCED, XESS_QUALITY_SETTING_PERFORMANCE,
            XESS_QUALITY_SETTING_ULTRA_PERFORMANCE};
        for (bool hdr : {false,true}) {
            for (int output=0; output<BbSettings::OutputCount; ++output) {
                for (int selected=0; selected<BbSettings::XessPresetCount; ++selected) {
                    const uint32_t width=BbSettings::OutputWidths[output], height=BbSettings::OutputHeights[output];
                    const auto input=SceneResolution::ForScale(BbSettings::XessPresetScale(selected),{width,height});
                    const Xess::FeatureDesc desc{input.width,input.height,width,height,hdr};
                    assert(xess.CreateFeature(desc) && xess.HasFeature(desc));
                    assert(init_params.qualitySetting==modes[selected]);
                    assert(init_params.outputResolution.x==width && init_params.outputResolution.y==height);
                    assert(init_params.initFlags==(hdr ? XESS_INIT_FLAG_ENABLE_AUTOEXPOSURE : XESS_INIT_FLAG_LDR_INPUT_COLOR));
                    xess.ReleaseFeature();
                }
            }
        }
        assert(created==destroyed);
        assert(xess.CreateFeature({64,64,128,128,false}));
        fail_execute=true;Xess::Frame frame{};
        frame.depth.aspect=vk::ImageAspectFlagBits::eDepth;frame.color.aspect=frame.motion.aspect=vk::ImageAspectFlagBits::eColor;
        assert(!xess.Evaluate(vk::CommandBuffer{(VkCommandBuffer)1},frame));
        assert(!xess.Available() && xess.Problem() && barriers==6);
    }
    assert(created==destroyed);
    absent=true;Xess unsupported(api);Prepare(unsupported);assert(!unsupported.Available() && unsupported.Problem());
    std::puts("PASS: seven XeSS quality modes at all four output sizes in SDR/HDR, extension/features negotiation, unsupported-device fallback, pixel motion scale, jitter/reset, FP16 input, depth aspect, barriers restored on SDK failure, context recreation and destruction.");
}
