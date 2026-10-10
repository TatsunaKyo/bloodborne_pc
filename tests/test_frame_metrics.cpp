// SPDX-License-Identifier: GPL-2.0-or-later
#include "bbport_frame_metrics.h"
#include "bbport_latency.h"
#include <array>
#include <cassert>
#include <cmath>
#include <cstdio>
int main() {
    using C=BbFrameMetrics::Counter;
    C counter;C::Clock::time_point now{};counter.Reset(now);
    // 65 real frames produce 130 output frames: neither the 75 real cap nor
    // selecting 2x is a substitute for the SDK's actual presentation counter.
    for(int i=1;i<=65;++i) {
        counter.Output(i%2 ? 0 : 4);
        if(i==65) counter.Output(2);
        if(counter.Present(true,now+std::chrono::microseconds(i*1000000LL/65))) {
            const auto sample=counter.Get();
            assert(std::abs(sample.real_fps-65)<0.1f);
            assert(sample.output_fps>120 && sample.output_fps<135);
            assert(sample.multiplier==2);
        }
    }
    counter.Reset(now);
    for(int i=1;i<=75;++i) {
        counter.Output(1);
        counter.Present(true,now+std::chrono::microseconds(i*1000000LL/75));
    }
    assert(counter.Get().multiplier==1 && std::abs(counter.Get().output_fps-75)<0.1f);
    // A long focus pause must invalidate stale measurements.
    assert(!counter.Present(true,now+std::chrono::seconds(4)) && !counter.Valid());
    counter.Reset(now);
    for(int i=1;i<=90;++i) counter.Present(false,now+std::chrono::microseconds(i*1000000LL/90));
    assert(std::abs(counter.Get().output_fps-90)<0.1f && counter.Get().multiplier==1);
    struct Report { uint64_t frameID,simStartTime,gpuRenderEndTime; };
    std::array<Report,7> reports{{{3,1000,23000},{2,1000,13000},{4,0,9000},
        {5,10000,9000},{6,1000,2000000},{7,10000,43500},{1,10,20000}}};
    const auto valid=BbLatency::Latest(reports,3);
    assert(valid && valid->frame==7 && std::abs(valid->milliseconds-33.5f)<0.001f);
    assert(!BbLatency::Latest(reports,7));
    std::puts("PASS: delayed/zero SDK counts, confirmed output vs real FPS, inactive FG, pause resets; completed Reflex reports, invalid/stale/out-of-order reports and real PC latency.");
}
