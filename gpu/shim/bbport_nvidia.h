// SPDX-License-Identifier: GPL-2.0-or-later
// TatsunaKyo revision: optional Streamline Vulkan FG and independent Reflex.
#pragma once
#include <cstdint>
#include <functional>
namespace vk {
class PhysicalDevice;class Device;class CommandBuffer;class Image;class ImageView;
enum class Format;
}
namespace Vulkan { struct Frame; class Scheduler; }
namespace BbNvidia {
void* VulkanLoader(void* native);
void BindDevice(vk::PhysicalDevice physical, vk::Device device);
void Shutdown();
void BeginRender();
void QueueFlip(int index, int64_t argument);
void CancelFlip(int index, int64_t argument);
void NextSimulation();
void FinishRender(Vulkan::Frame* frame, int index, int64_t argument);
void BeforePresent(Vulkan::Frame* frame, vk::CommandBuffer command,
                   vk::Image image, vk::ImageView view, vk::Format format,
                   uint32_t buffers, bool game_frame, Vulkan::Scheduler& scheduler,
                   uint32_t output_width, uint32_t output_height);
bool Present(Vulkan::Frame* frame,const std::function<bool()>& present);
void WaitForInputs(Vulkan::Frame* frame);
void BeforeSwapchainChange();
}
