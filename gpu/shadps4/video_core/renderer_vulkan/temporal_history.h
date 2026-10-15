// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <array>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <optional>
#include <span>

namespace Vulkan::Motion {

struct CameraSample {
    std::array<float, 12> view{};     // world to view, 3x4 rows
    std::array<float, 12> inv_view{}; // view to world, 3x4 rows
    std::array<float, 4> proj{};      // x/y scale, depth scale/offset
    bool valid = false;
};

struct SceneCamera {
    CameraSample camera;
    std::array<uint32_t,2> size;
};
// Decode the exact scene-constant snapshot bound by this draw, never later guest data.
inline std::optional<SceneCamera> DecodeSceneCamera(std::span<const float> data,
                                                  float viewport_x = 1.0f,
                                                  float viewport_y = -1.0f) {
    if (data.size() < 216 || data[0] != 3000.0f || !std::isfinite(data[1]) ||
        !(data[4] >= 64.0f && data[4] <= 32768.0f && data[5] >= 64.0f && data[5] <= 32768.0f) ||
        std::abs(data[1]*data[0]-1.0f) > 1e-3f) return std::nullopt;
    SceneCamera result;
    std::copy_n(data.begin()+8,12,result.camera.view.begin());
    std::copy_n(data.begin()+180,12,result.camera.inv_view.begin());
    if (!std::isfinite(viewport_x) || !std::isfinite(viewport_y) ||
        viewport_x == 0 || viewport_y == 0) return std::nullopt;
    // Motion/TAA/SL use screen clip coordinates (+x right, +y up). The
    // guest viewport, not the projection buffer alone, determines their sign.
    result.camera.proj = {std::copysign(1.0f,viewport_x)*data[52],
                         -std::copysign(1.0f,viewport_y)*data[57],data[62],data[63]};
    result.size = {uint32_t(data[4]),uint32_t(data[5])};
    return result;
}

inline bool ValidCamera(const CameraSample& sample) {
    const auto finite = [](const auto& values) {
        return std::all_of(values.begin(), values.end(), [](float v) { return std::isfinite(v); });
    };
    if (!finite(sample.view) || !finite(sample.inv_view) || !finite(sample.proj) ||
        sample.proj[0] == 0 || sample.proj[1] == 0 || sample.proj[2] == 0) {
        return false;
    }
    for (int axis = 0; axis < 3; ++axis) {
        float length = 0;
        for (int row = 0; row < 3; ++row) {
            const float v = sample.inv_view[row * 4 + axis];
            length += v * v;
        }
        if (length < 0.25f || length > 4.0f) return false;
    }
    return true;
}

// Conservative discontinuity detection: ordinary motion, jitter and gradual FOV changes
// keep history. Teleports (10 world units), turns over 100 degrees in one frame and abrupt
// projection changes discard it. Resolution/provider changes use Invalidate separately.
inline bool CameraDiscontinuity(const CameraSample& previous, const CameraSample& current) {
    if (!previous.valid) return true;
    float distance_squared = 0, trace = 0;
    for (int row = 0; row < 3; ++row) {
        const float delta = current.inv_view[row * 4 + 3] - previous.inv_view[row * 4 + 3];
        distance_squared += delta * delta;
    }
    if (distance_squared >= 100.0f) return true;
    for (int axis = 0; axis < 3; ++axis) {
        float dot = 0, old_length = 0, new_length = 0;
        for (int row = 0; row < 3; ++row) {
            const float a = previous.inv_view[row * 4 + axis];
            const float b = current.inv_view[row * 4 + axis];
            dot += a * b;
            old_length += a * a;
            new_length += b * b;
        }
        trace += dot / std::sqrt(old_length * new_length);
    }
    if ((trace - 1.0f) * 0.5f < -0.17364818f) return true; // cos(100 degrees)
    for (int axis = 0; axis < 4; ++axis) {
        const float a = previous.proj[axis], b = current.proj[axis];
        if (std::abs(a - b) > 0.2f * std::max({std::abs(a), std::abs(b), 1.0e-4f})) return true;
    }
    return false;
}

class CameraHistory {
public:
    CameraSample current, previous;

    bool Capture(CameraSample sample, bool resized = false) {
        if (captured) return false;
        if (!ValidCamera(sample)) {
            Invalidate();
            return false;
        }
        sample.valid = true;
        previous = completed;
        current = sample;
        reset = forced_reset || resized || CameraDiscontinuity(previous, current);
        if (reset) previous = current; // zero velocity; do not reuse the preceding scene
        captured = true;
        return true;
    }
    void Invalidate() noexcept {
        current.valid = previous.valid = completed.valid = false;
        captured = false;
        forced_reset = true;
        reset = true;
    }
    // A different G-buffer depth/viewport starts another candidate camera.
    // Every candidate compares with the previous COMPLETED frame, never with
    // an auxiliary camera captured earlier in this frame.
    void BeginPass() noexcept {
        captured = false;
        current.valid = previous.valid = false;
        reset = forced_reset;
    }
    void EndFrame() noexcept {
        if (!captured) Invalidate();
        else completed = current;
        captured = false;
        forced_reset = false;
        reset = false; // a missing/invalid camera will request reset on its next capture
    }
    bool NeedsCamera() const noexcept { return !captured; }
    bool Reset() const noexcept { return reset; }

private:
    CameraSample completed;
    bool captured = false;
    bool forced_reset = true;
    bool reset = true;
};

// Scene samplers ask for this bias on many draws; only changed dimensions need log2.
class MipBiasCache {
public:
    float Get(uint32_t render, uint32_t output) {
        if (render != render_width || output != output_width) {
            render_width = render;
            output_width = output;
            value = render && render < output ? std::log2(float(render) / float(output)) : 0.0f;
        }
        return value;
    }
private:
    uint32_t render_width = 0, output_width = 0;
    float value = 0;
};

} // namespace Vulkan::Motion
