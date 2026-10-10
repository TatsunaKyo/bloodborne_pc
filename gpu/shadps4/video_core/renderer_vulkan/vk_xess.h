// SPDX-License-Identifier: GPL-2.0-or-later
// TatsunaKyo revision. Intel XeSS headers/runtime retain Intel's license.
#pragma once
#include <memory>
#include <string>
#include <vector>
#include "video_core/renderer_vulkan/vk_dlss.h"
#include "../../../third_party/xess-headers/xess_vk.h"

namespace Vulkan {
class Xess {
public:
    struct Api {
        decltype(&xessVKGetRequiredInstanceExtensions) instance_extensions{};
        decltype(&xessVKGetRequiredDeviceExtensions) device_extensions{};
        decltype(&xessVKGetRequiredDeviceFeatures) device_features{};
        decltype(&xessVKCreateContext) create{};
        decltype(&xessVKInit) init{};
        decltype(&xessVKExecute) execute{};
        decltype(&xessSetVelocityScale) velocity{};
        decltype(&xessDestroyContext) destroy{};
    };
    static Xess* Get();
    ~Xess();
    void AppendInstanceExtensions(std::vector<const char*>& enabled,u32 api_version);
    void AppendDeviceExtensions(vk::Instance instance,vk::PhysicalDevice physical,
                                std::vector<const char*>& enabled);
    bool PrepareDeviceFeatures(vk::Instance instance,vk::PhysicalDevice physical,void*& chain);
    void Initialize(vk::Instance instance,vk::PhysicalDevice physical,vk::Device device);
    void Shutdown();
    bool Available() const;
    const char* Problem() const;
    using Resource=Dlss::Resource;
    using Frame=Dlss::Frame;
    struct FeatureDesc {
        u32 input_width,input_height,output_width,output_height;
        bool hdr;
        bool operator==(const FeatureDesc&) const=default;
    };
    static xess_quality_settings_t QualityForScale(float scale);
    bool HasFeature(const FeatureDesc& desc) const;
    bool CreateFeature(const FeatureDesc& desc);
    bool Evaluate(vk::CommandBuffer command,const Frame& frame);
    void ReleaseFeature();
#ifdef BB_XESS_TESTING
    explicit Xess(Api api);
#endif
private:
#ifndef BB_XESS_TESTING
    explicit Xess(Api api);
#endif
    struct Impl;
    std::unique_ptr<Impl> impl;
};
}
