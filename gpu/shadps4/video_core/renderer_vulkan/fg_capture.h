// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <optional>

namespace BbCapture {
// Diagnostic readbacks share a fixed budget. A normal session never arms this.
class FrameGenerationRequest {
public:
    static constexpr uint64_t Budget = 256ull * 1024 * 1024;
    struct Frame { uint32_t index, count; uint64_t bytes; };
    std::optional<Frame> Poll(const char* trigger, uint32_t rw, uint32_t rh,
                              uint32_t ow, uint32_t oh) {
        if (!trigger || !*trigger || !rw || !rh || !ow || !oh ||
            rw > 32768 || rh > 32768 || ow > 32768 || oh > 32768) return {};
        const uint64_t bytes = uint64_t(rw) * rh * 8 + uint64_t(ow) * oh * 4;
        if (!remaining) {
            if (finished || std::remove(trigger) != 0) return {};
            count = uint32_t(std::min<uint64_t>(4, Budget / bytes));
            remaining = count;
            if (!count) {
                finished = true;
                std::puts("NVIDIA FG capture: one frame exceeds the 256 MiB readback budget.");
                return {};
            }
        }
        if (bytes > Budget - reserved) {
            remaining = 0; finished = true;
            std::puts("NVIDIA FG capture: dimensions changed beyond the readback budget.");
            return {};
        }
        reserved += bytes;
        const auto result = Frame{count - remaining, count, bytes};
        if (!--remaining) finished = true;
        return result;
    }
private:
    uint32_t count{}, remaining{};
    uint64_t reserved{};
    bool finished{};
};

struct FrameGenerationCamera {
    std::array<float,16> view_to_clip{}, clip_to_view{}, clip_to_previous{}, previous_to_clip{};
    std::array<float,2> motion_scale{};
    bool reset{};
};
} // namespace BbCapture
