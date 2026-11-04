// SPDX-License-Identifier: GPL-2.0-or-later
// A simulated driver exercises the same feature gate as the probe and renderer.
#include "fsr411_vulkan_support.h"
#include <cassert>
#include <cstdio>
#include <string>

static uint32_t api = VK_API_VERSION_1_3;
static int absent_extension = -1, absent_feature = -1;
static bool enumeration_error{};
static const char* names[] = {VK_KHR_COMPUTE_SHADER_DERIVATIVES_EXTENSION_NAME,
    VK_EXT_MUTABLE_DESCRIPTOR_TYPE_EXTENSION_NAME, VK_EXT_DESCRIPTOR_BUFFER_EXTENSION_NAME};

static VKAPI_ATTR void VKAPI_CALL Properties(VkPhysicalDevice, VkPhysicalDeviceProperties* p) {
    p->apiVersion = api;
}
static VKAPI_ATTR VkResult VKAPI_CALL Extensions(VkPhysicalDevice, const char*, uint32_t* n,
                                                VkExtensionProperties* out) {
    if (enumeration_error) return VK_ERROR_INITIALIZATION_FAILED;
    if (!out) { *n = 3; return VK_SUCCESS; }
    for (int i = 0; i < 3; ++i) std::strcpy(out[i].extensionName, i == absent_extension ? "other" : names[i]);
    return VK_SUCCESS;
}
static VKAPI_ATTR void VKAPI_CALL Features(VkPhysicalDevice, VkPhysicalDeviceFeatures2* f) {
    auto* v12 = static_cast<VkPhysicalDeviceVulkan12Features*>(f->pNext);
    auto* v13 = static_cast<VkPhysicalDeviceVulkan13Features*>(v12->pNext);
    auto* derivatives = static_cast<VkPhysicalDeviceComputeShaderDerivativesFeaturesKHR*>(v13->pNext);
    auto* mut = static_cast<VkPhysicalDeviceMutableDescriptorTypeFeaturesEXT*>(derivatives->pNext);
    auto* desc = static_cast<VkPhysicalDeviceDescriptorBufferFeaturesEXT*>(mut->pNext);
    VkBool32* flags[] = {&f->features.shaderInt16, &f->features.shaderStorageImageReadWithoutFormat,
        &f->features.shaderStorageImageWriteWithoutFormat, &v12->shaderFloat16, &v12->shaderInt8,
        &v12->storageBuffer8BitAccess, &v12->runtimeDescriptorArray,
        &v12->descriptorBindingVariableDescriptorCount, &v12->bufferDeviceAddress,
        &v13->synchronization2, &v13->shaderIntegerDotProduct,
        &derivatives->computeDerivativeGroupLinear, &mut->mutableDescriptorType, &desc->descriptorBuffer};
    for (int i = 0; i < 14; ++i) *flags[i] = i == absent_feature ? VK_FALSE : VK_TRUE;
}
static const char* Check() {
    return Fsr411VulkanRequirement(VK_NULL_HANDLE, Properties, Extensions, Features);
}
int main() {
    assert(!Check());
    api = VK_API_VERSION_1_2;
    assert(std::string(Check()) == "Vulkan 1.3");
    api = VK_API_VERSION_1_3;
    for (int i = 0; i < 3; ++i) {
        absent_extension = i;
        assert(std::string(Check()) == names[i]);
    }
    absent_extension = -1;
    for (int i = 0; i < 14; ++i) {
        absent_feature = i;
        assert(Check());
    }
    absent_feature = -1;
    enumeration_error = true;
    assert(std::string(Check()) == "Vulkan extension query");
    enumeration_error = false;
    assert(!Check());
    std::puts("FSR 4.1.1: Vulkan 1.3, 3 extensions and 14 feature gates PASS");
}
