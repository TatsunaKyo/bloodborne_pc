// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <cstdint>
namespace Vulkan::QueuePlan {
// Same-family queues need no ownership transfers. Isolate NVIDIA presentation
// waits from guest rendering when a second graphics queue is available.
constexpr uint32_t PresentIndex(uint32_t vendor,uint32_t available) {
    return vendor==0x10de && available>=2 ? 1 : 0;
}
}
