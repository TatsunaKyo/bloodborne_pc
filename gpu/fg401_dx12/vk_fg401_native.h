// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#ifdef _WIN32
#include "video_core/renderer_vulkan/vk_fsr4.h"
#include <memory>
#include <string>
namespace Vulkan {
class Instance;
class Scheduler;
class Fg401Native {
  public:
    Fg401Native(const Instance &instance, Scheduler &scheduler, bool overlap = false);
    ~Fg401Native();
    bool Record(Fsr4Upscaler::Frame &frame, bool asynchronous);
    bool RecordOverlap(Fsr4Upscaler::Frame &frame, Scheduler &completion);
    // Returns ownership and submits the completion queue, without blocking the
    // draw queue.
    void FlushOverlap(Scheduler &completion);
    void SetWorldCamera(const std::array<float, 12> &inverse_view);
    /// Return the shared result to DX12 after the last consumer; a no-op for
    /// buffer output.
    void ReleaseOutput(vk::CommandBuffer command);
    const std::string &Error() const;

  private:
    struct Impl;
    std::unique_ptr<Impl> impl;
};
} // namespace Vulkan
#endif
