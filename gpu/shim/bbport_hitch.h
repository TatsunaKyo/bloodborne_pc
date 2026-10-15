// SPDX-License-Identifier: GPL-2.0-or-later
// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
#pragma once
#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cstdio>

// Bounded CPU wait journal. Normal frames write no log and allocate no memory.
// A slow real-frame interval prints recent completed waits, not an invented GPU
// diagnosis. An in-flight wait can appear in the following report instead.
namespace BbHitch {
using Clock=std::chrono::steady_clock;
struct Event {const char* stage{}; Clock::time_point end{}; double ms{};};
struct Slot {std::atomic_flag busy=ATOMIC_FLAG_INIT; Event event;};
inline std::array<Slot,128> journal;
inline std::atomic<unsigned> next{};
inline std::atomic_flag cadence_busy=ATOMIC_FLAG_INIT;
inline std::array<double,512> cadence;
inline unsigned cadence_cursor{},cadence_used{};
inline void TrackCadence(double ms) {
    if (cadence_busy.test_and_set(std::memory_order_acquire)) return;
    cadence[cadence_cursor++%cadence.size()]=ms;
    cadence_used=std::min<unsigned>(cadence_used+1,cadence.size());
    cadence_busy.clear(std::memory_order_release);
}
inline void ReportCadence(float sdk_output_fps) {
    // The diagnostic observer calls this, never the presentation thread.
    std::array<double,512> values{};unsigned count;
    if (cadence_busy.test_and_set(std::memory_order_acquire)) return;
    values=cadence;count=cadence_used;
    cadence_busy.clear(std::memory_order_release);
    if (count<8) return;
    std::sort(values.begin(),values.begin()+count);
    double total=0;for(unsigned i=0;i<count;++i)total+=values[i];
    std::printf("Frame cadence: %u recent real intervals, mean %.3f fps, median %.3f ms, "
                "p95 %.3f ms, p99 %.3f ms, max %.3f ms; latest SDK output %.3f fps\n",
        count,1000.0*count/total,values[count/2],values[(count-1)*95/100],
        values[(count-1)*99/100],values[count-1],sdk_output_fps);
}
inline void Record(const char* stage, Clock::time_point start, Clock::time_point end=Clock::now()) {
    const double ms=std::chrono::duration<double,std::milli>(end-start).count();
    if (ms<1.0) return;
    auto& slot=journal[next.fetch_add(1,std::memory_order_relaxed)%journal.size()];
    if (slot.busy.test_and_set(std::memory_order_acquire)) return;
    slot.event={stage,end,ms};
    slot.busy.clear(std::memory_order_release);
}
struct Scope {
    const char* stage;
    Clock::time_point start{Clock::now()};
    ~Scope(){Record(stage,start);}
};
class FrameGate {
public:
    bool Push(double ms) {
        bool slow=false;
        if (ms>=25.0 && used>=8) {
            auto sorted=intervals;
            std::sort(sorted.begin(),sorted.begin()+used);
            slow=ms>sorted[used/2]*1.5;
        }
        intervals[cursor++%intervals.size()]=ms;
        used=std::min<unsigned>(used+1,intervals.size());
        return slow;
    }
    void Reset(){used=cursor=0;}
private:
    std::array<double,32> intervals{};
    unsigned used{},cursor{};
};
inline void Present(bool real, bool presented, bool focused) {
    // Called only on the presentation thread, outside the ImGui lock.
    static Clock::time_point previous{}, last_report{};
    static FrameGate gate;
    const auto now=Clock::now();
    if (!presented || !focused) {previous={};gate.Reset();return;}
    if (!real) return;
    const auto old=previous;previous=now;
    if (old==Clock::time_point{}) return;
    const double ms=std::chrono::duration<double,std::milli>(now-old).count();
    TrackCadence(ms);
    if (!gate.Push(ms) || now-last_report<std::chrono::seconds(1)) return;
    last_report=now;
    std::array<Event,128> events{};unsigned count=0;
    for (auto& slot:journal) {
        if (slot.busy.test_and_set(std::memory_order_acquire)) continue;
        const auto e=slot.event;slot.busy.clear(std::memory_order_release);
        if (e.stage && e.end<=now && now-e.end<std::chrono::milliseconds(250)) events[count++]=e;
    }
    // One line per slow stage category avoids expanding normal Reflex sleeps.
    std::printf("Frame hitch: real interval %.2f ms; recent CPU spans (overlap, not additive):",ms);
    for (unsigned i=0;i<count;++i) {
        bool earlier=false;for(unsigned j=0;j<i;++j) earlier|=events[j].stage==events[i].stage;
        if (earlier) continue;
        double peak=0;unsigned calls=0;
        for(unsigned j=i;j<count;++j) if(events[j].stage==events[i].stage) {
            if(events[j].ms>peak)peak=events[j].ms;++calls;
        }
        std::printf(" %s=%.2fms/%u;",events[i].stage,peak,calls);
    }
    std::printf("\n");
}
}
