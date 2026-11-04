// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <cstring>
#include <vector>
#include <vulkan/vulkan.h>

// Used by both the launcher probe and renderer, independently of provider files.
inline const char* Fsr411VulkanRequirement(VkPhysicalDevice device,
    PFN_vkGetPhysicalDeviceProperties get_properties,
    PFN_vkEnumerateDeviceExtensionProperties enumerate_extensions,
    PFN_vkGetPhysicalDeviceFeatures2 get_features) {
    VkPhysicalDeviceProperties props{};
    get_properties(device, &props);
    if (props.apiVersion < VK_API_VERSION_1_3) return "Vulkan 1.3";
    uint32_t count{};
    if (enumerate_extensions(device, nullptr, &count, nullptr) != VK_SUCCESS)
        return "Vulkan extension query";
    std::vector<VkExtensionProperties> extensions(count);
    if (enumerate_extensions(device, nullptr, &count, extensions.data()) != VK_SUCCESS)
        return "Vulkan extension query";
    const auto has = [&](const char* name) {
        for (const auto& e : extensions) if (!std::strcmp(e.extensionName, name)) return true;
        return false;
    };
    for (const char* name : {VK_KHR_COMPUTE_SHADER_DERIVATIVES_EXTENSION_NAME,
             VK_EXT_MUTABLE_DESCRIPTOR_TYPE_EXTENSION_NAME, VK_EXT_DESCRIPTOR_BUFFER_EXTENSION_NAME})
        if (!has(name)) return name;
    VkPhysicalDeviceDescriptorBufferFeaturesEXT descriptors{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_DESCRIPTOR_BUFFER_FEATURES_EXT};
    VkPhysicalDeviceMutableDescriptorTypeFeaturesEXT mutable_type{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_MUTABLE_DESCRIPTOR_TYPE_FEATURES_EXT, &descriptors};
    VkPhysicalDeviceComputeShaderDerivativesFeaturesKHR derivatives{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_COMPUTE_SHADER_DERIVATIVES_FEATURES_KHR, &mutable_type};
    VkPhysicalDeviceVulkan13Features v13{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_3_FEATURES, &derivatives};
    VkPhysicalDeviceVulkan12Features v12{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_2_FEATURES, &v13};
    VkPhysicalDeviceFeatures2 f{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2, &v12};
    get_features(device, &f);
#define BB_REQUIRE_FSR411(field) if (!(field)) return #field
    BB_REQUIRE_FSR411(f.features.shaderInt16);
    BB_REQUIRE_FSR411(f.features.shaderStorageImageReadWithoutFormat);
    BB_REQUIRE_FSR411(f.features.shaderStorageImageWriteWithoutFormat);
    BB_REQUIRE_FSR411(v12.shaderFloat16);
    BB_REQUIRE_FSR411(v12.shaderInt8);
    BB_REQUIRE_FSR411(v12.storageBuffer8BitAccess);
    BB_REQUIRE_FSR411(v12.runtimeDescriptorArray);
    BB_REQUIRE_FSR411(v12.descriptorBindingVariableDescriptorCount);
    BB_REQUIRE_FSR411(v12.bufferDeviceAddress);
    BB_REQUIRE_FSR411(v13.synchronization2);
    BB_REQUIRE_FSR411(v13.shaderIntegerDotProduct);
    BB_REQUIRE_FSR411(derivatives.computeDerivativeGroupLinear);
    BB_REQUIRE_FSR411(mutable_type.mutableDescriptorType);
    BB_REQUIRE_FSR411(descriptors.descriptorBuffer);
#undef BB_REQUIRE_FSR411
    return nullptr;
}
