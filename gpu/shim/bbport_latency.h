// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <cstdint>
#include <optional>

namespace BbLatency {
struct Sample { uint64_t frame; float milliseconds; };
// Reflex timestamps are microseconds. Use a completed, fresh driver report;
// frame time and interpolated-frame intervals are not latency measurements.
template<class Reports>
std::optional<Sample> Latest(const Reports& reports,uint64_t after) {
    std::optional<Sample> result;
    for (const auto& r : reports) {
        if (r.frameID<=after || !r.simStartTime || r.gpuRenderEndTime<=r.simStartTime)
            continue;
        const uint64_t duration=r.gpuRenderEndTime-r.simStartTime;
        if (duration>1000000 || (result && r.frameID<=result->frame)) continue;
        result=Sample{r.frameID,float(duration)/1000.0f};
    }
    return result;
}
}
