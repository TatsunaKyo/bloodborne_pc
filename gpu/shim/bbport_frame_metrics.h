// SPDX-License-Identifier: GPL-2.0-or-later
// TatsunaKyo revision: count presented frames, including SDK-confirmed NVIDIA output.
#pragma once
#include <chrono>
#include <cstdint>

namespace BbFrameMetrics {
class Counter {
public:
    using Clock=std::chrono::steady_clock;
    struct Sample { float real_fps{}, output_fps{}; unsigned multiplier{1}; };
    void Reset(Clock::time_point now=Clock::now()) {
        started=now;real=output=0;last={};valid=false;
    }
    // NVIDIA's counter is consumed by GetState: include every query, including
    // zeros and delayed batches. Never substitute the selected multiplier.
    void Output(uint32_t count) { output+=count; }
    bool Present(bool nvidia,Clock::time_point now=Clock::now()) {
        ++real;if (!nvidia) ++output;
        const float elapsed=std::chrono::duration<float>(now-started).count();
        if (elapsed<0.5f) return false;
        if (elapsed>2.0f) { Reset(now);return false; }
        last={float(real)/elapsed,float(output)/elapsed,
              unsigned(output>real ? (output+real/2)/real : 1)};
        valid=true;real=output=0;started=now;return true;
    }
    const Sample& Get() const { return last; }
    bool Valid() const { return valid; }
private:
    Clock::time_point started{Clock::now()};
    uint64_t real{},output{};
    Sample last{};
    bool valid{};
};
}
