// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstddef>

namespace BbFrameMetrics {
// Intervals between successful real-frame QueuePresent calls. NVIDIA supplies an
// output count, not individual generated display timestamps; never invent those.
class RealFrameHistory {
public:
    using Clock = std::chrono::steady_clock;
    static constexpr std::size_t Capacity = 240;

    void Reset() { count = next = 0; seeded = false; }
    bool Present(Clock::time_point now = Clock::now()) {
        if (!seeded) { last = now; seeded = true; return false; }
        const float ms = std::chrono::duration<float, std::milli>(now - last).count();
        if (ms <= 0.0f) return false;
        last = now;
        // A suspended/minimized session starts a new trace on return. Ordinary
        // hitches stay visible as raw samples instead of being averaged away.
        if (!std::isfinite(ms) || ms >= 1000.0f) { count = next = 0; return false; }
        values[next] = ms;
        next = (next + 1) % Capacity;
        count = std::min(count + 1, Capacity);
        return true;
    }
    std::size_t Size() const { return count; }
    float At(std::size_t index) const {
        if (index >= count) return 0.0f;
        return values[(next + Capacity - count + index) % Capacity];
    }
    float Latest() const { return count ? At(count - 1) : 0.0f; }
    float Peak() const {
        float peak = 0.0f;
        for (std::size_t i = 0; i < count; ++i) peak = std::max(peak, At(i));
        return peak;
    }
    float PlotCeiling() const { return std::max(33.333f, std::ceil(Peak() / 8.0f) * 8.0f); }

private:
    std::array<float, Capacity> values{};
    std::size_t count{}, next{};
    Clock::time_point last{};
    bool seeded{};
};
} // namespace BbFrameMetrics
