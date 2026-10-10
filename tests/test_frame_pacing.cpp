// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
// SPDX-License-Identifier: GPL-2.0-or-later
#include "bbframe_pacing.h"
#include <cassert>
#include <cstdio>
#include <vector>

using namespace std::chrono_literals;
using BbFramePacing::Clock;
using BbFramePacing::NextFlipDeadline;

static void QueuedFrames(unsigned fps, std::chrono::nanoseconds render_time,
                         std::chrono::nanoseconds stall) {
    const auto period = std::chrono::nanoseconds(1'000'000'000 / fps);
    auto now = Clock::time_point{};
    auto deadline = now;
    std::vector<Clock::time_point> submissions;
    for (unsigned frame = 0; frame < 100; ++frame) {
        if (frame == 20) now += stall;
        now = std::max(now, deadline);
        submissions.push_back(now);
        deadline = NextFlipDeadline(deadline, now, period);
        now += render_time;
    }
    for (unsigned frame = 1; frame < submissions.size(); ++frame) {
        const auto gap = submissions[frame] - submissions[frame - 1];
        assert(gap >= period);
        if (frame != 20) assert(gap == std::max(period, render_time));
    }
}

int main() {
    for (const unsigned fps : {30u, 60u, 65u, 75u, 90u, 120u})
        for (const auto stall : {0ns, 50'000'000ns, 5'000'000'000ns}) {
            QueuedFrames(fps, 1ms, stall);
            QueuedFrames(fps, 25ms, stall);
        }
    // The output cap translates into real-frame pacing without speeding up game logic.
    QueuedFrames(130 / 2, 1ms, 50ms);
    QueuedFrames(225 / 3, 1ms, 50ms);
    const auto origin = Clock::time_point{};
    const auto period = std::chrono::nanoseconds(1'000'000'000 / 90);
    const auto late = origin + 50ms;
    auto next = NextFlipDeadline(origin + period, late, period);
    assert(next == late + period);
    for (unsigned i = 0; i < 3; ++i) {
        const auto following = NextFlipDeadline(next, next, period);
        assert(following - next == period);
        next = following;
    }
    assert(NextFlipDeadline(origin + 1s, late, 0ns) == late);
    const auto resumed = origin + 5s;
    const auto changed_period = std::chrono::nanoseconds(1'000'000'000 / 75);
    assert(NextFlipDeadline(origin, resumed, changed_period) == resumed + changed_period);
    BbFramePacing::SleepFor(0ns);
    BbFramePacing::SleepFor(-1ns);
    BbFramePacing::SleepUntil(Clock::now() - 1ms);
    const auto wake = Clock::now() + 2ms;
    BbFramePacing::SleepUntil(wake);
    assert(Clock::now() >= wake);
    std::puts("frame pacing: queued frames, stalls, real/FG caps, resume and timer waits passed");
}
