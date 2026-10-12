// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
// SPDX-License-Identifier: GPL-2.0-or-later
#include "bbport_frametime.h"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <deque>

int main() {
    using H = BbFrameMetrics::RealFrameHistory;
    using namespace std::chrono_literals;
    unsigned cases = 0;
    for (unsigned fps : {30u, 60u, 65u, 75u, 90u, 120u}) {
        H history;
        auto now = H::Clock::time_point{};
        const auto period = std::chrono::nanoseconds(1'000'000'000 / fps);
        std::deque<float> reference;
        assert(!history.Present(now) && !history.Size());
        for (unsigned frame = 0; frame < 1024; ++frame) {
            auto interval = period + std::chrono::microseconds(int(frame % 5) * 100 - 200);
            if (frame == 123 || frame == 700) interval += 80ms;
            now += interval;
            assert(history.Present(now));
            reference.push_back(std::chrono::duration<float, std::milli>(interval).count());
            if (reference.size() > H::Capacity) reference.pop_front();
            assert(history.Size() == reference.size());
            float peak = 0;
            for (unsigned i = 0; i < reference.size(); ++i) {
                assert(std::abs(history.At(i) - reference[i]) < 0.0001f);
                peak = std::max(peak, reference[i]);
            }
            assert(history.Latest() == reference.back() && history.Peak() == peak);
            assert(history.PlotCeiling() >= peak);
            assert(!history.Present(now) && !history.Present(now - 1ms));
            ++cases;
        }
        now += 2s;
        assert(!history.Present(now) && history.Size() == 0);
        now += period;
        assert(history.Present(now) && history.Size() == 1);
        history.Reset();
        assert(!history.Size() && !history.Latest() && !history.Peak());
        assert(!history.Present(now + 5s));
    }
    std::printf("Frametime history: PASS (%u raw intervals; FIFO wrap, visible hitches, peaks, duplicate/backward clocks and pause resets)\n", cases);
}
