// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <array>
#include <atomic>
#include <deque>
#include <functional>
#include <memory>
#include "common/types.h"
#include "video_core/renderer_vulkan/vk_common.h"

VK_DEFINE_HANDLE(VmaAllocation)
VK_DEFINE_HANDLE(VmaAllocator)

struct FfxVkFsr3_3_1_6FrameGenerationContext;
namespace Vulkan {

// Immutable camera values captured before the display pass advances camera history.
struct FrameGenerationSource {
    vk::ImageView depth_view;
    vk::Image motion_image;
    vk::ImageView motion_view;
    u32 render_width{}, render_height{};
    std::array<float, 2> jitter{};
    std::array<float, 12> inverse_view{};
    float near_plane{}, vertical_fov{}, frame_ms{16.666f};
    bool reset{}, valid{};
    std::array<float,12> view{}, previous_view{}, previous_inverse_view{};
    std::array<float,4> projection{}, previous_projection{};
};

class FrameGeneration {
public:
    // Submission callbacks keep resource retirement tied to the queue that
    // actually runs FI/OF, including when tested on a headless Vulkan device.
    struct Submissions {
        std::function<void()> wait_submitted;
        std::function<void(u64)> wait;
        std::function<bool(u64)> is_free;
    };
    struct Image {
        VmaAllocator allocator{};
        VmaAllocation allocation{};
        vk::Image image{};
        Image() = default;
        ~Image();
        Image(const Image&) = delete;
        Image& operator=(const Image&) = delete;
        bool Create(VmaAllocator allocator, vk::Format format, u32 width, u32 height);
        operator vk::Image() const { return image; }
    };
    struct Snapshot {
        FrameGenerationSource source;
        u32 width{}, height{};
        bool hdr{}, nvidia_input_only{};
        Image color, depth, motion, generated, encoded;
        vk::UniqueImageView color_view, depth_view, motion_view, generated_view, encoded_view;
        vk::Image PresentImage() const { return hdr ? vk::Image(encoded) : vk::Image(generated); }
    };
    FrameGeneration(vk::PhysicalDevice physical, vk::Device device,
                    VmaAllocator allocator, Submissions submissions);
    ~FrameGeneration();
    // Draw queue: copy per-frame depth/motion and decode SDR sRGB or HDR10 PQ
    // frame into stable linear color. Snapshot ownership follows the final fence.
    void Capture(vk::CommandBuffer cmdbuf, const FrameGenerationSource& source,
                 vk::ImageView color_view, u32 width, u32 height, vk::Format format,
                 std::shared_ptr<Snapshot>& snapshot);
    // Present queue: record the real FI/OF prepare and dispatch. False still
    // permits a history-seeding dispatch, but suppresses the first generated frame.
    bool Record(vk::CommandBuffer cmdbuf, const std::shared_ptr<Snapshot>& snapshot);
    void Submitted(u64 tick);
    void Invalidate();
    void Reset();
private:
    bool EnsureCopyPipeline();
    void RetireCompleted();
    const vk::PhysicalDevice physical;
    const vk::Device device;
    const VmaAllocator allocator;
    Submissions submissions;
    vk::UniqueDescriptorSetLayout copy_descriptors;
    vk::UniquePipelineLayout copy_layout;
    vk::UniquePipeline copy_pipeline;
    FfxVkFsr3_3_1_6FrameGenerationContext* context{};
    u32 render_width{}, render_height{}, width{}, height{};
    u64 frame_id{}, paused_ns{};
    bool history{}, context_hdr{};
    std::atomic<bool> failed{false};
    struct Pending {
        u64 id{}, tick{};
        std::shared_ptr<Snapshot> snapshot;
    };
    std::deque<Pending> pending;
    Pending recording;
};
} // namespace Vulkan
