// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <thread>

#ifdef _WIN32
extern "C" void compat_sleep_ns(std::uint64_t ns);
#endif

namespace BbFramePacing {
using Clock = std::chrono::steady_clock;

// A late frame starts a new interval. Catching up missed slots would submit queued
// real frames back to back, also leaving FG with unevenly spaced input frames.
inline Clock::time_point NextFlipDeadline(Clock::time_point previous,
                                          Clock::time_point submitted,
                                          std::chrono::nanoseconds period) {
    return period.count() > 0 ? std::max(previous, submitted) + period : submitted;
}

inline void SleepFor(std::chrono::nanoseconds remaining) {
    if (remaining.count() <= 0) return;
#ifdef _WIN32
    // Reuse the runtime's high-resolution waitable timer instead of a coarse CRT sleep.
    compat_sleep_ns(static_cast<std::uint64_t>(remaining.count()));
#else
    std::this_thread::sleep_for(remaining);
#endif
}

inline void SleepUntil(Clock::time_point deadline) {
    SleepFor(std::chrono::duration_cast<std::chrono::nanoseconds>(deadline - Clock::now()));
}
} // namespace BbFramePacing
