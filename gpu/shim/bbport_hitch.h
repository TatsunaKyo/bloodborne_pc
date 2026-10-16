// SPDX-License-Identifier: GPL-2.0-or-later
// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
#pragma once
#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdint>
#include <mutex>

// Bounded CPU wait journal. Normal frames write no log and allocate no memory.
// A slow real-frame interval prints recent completed waits, not an invented GPU
// diagnosis. An in-flight wait can appear in the following report instead.
namespace BbHitch {
using Clock=std::chrono::steady_clock;
struct FramePath {
    uint64_t id{};
    Clock::time_point submitted{},gpu_flip{},prepared{},present_enter{},acquired{},enqueued{},returned{};
    double submit_interval{},gpu_interval{};
};
// Fixed storage joins a guest submission to its later GPU-thread flip, including
// repeated flip arguments and delayed frames. This is CPU chronology, not GPU time.
class SubmissionTracker {
public:
    uint64_t Queue(int index,int64_t argument,Clock::time_point now=Clock::now()) {
        std::scoped_lock lock{mutex};
        auto* slot=&pending[0];
        for(auto& entry:pending) {
            if(!entry.active){slot=&entry;break;}
            if(entry.path.id<slot->path.id)slot=&entry;
        }
        FramePath path{};path.id=++serial;path.submitted=now;
        if(previous_submit!=Clock::time_point{})path.submit_interval=Milliseconds(previous_submit,now);
        previous_submit=now;*slot={true,index,argument,path};return path.id;
    }
    void Cancel(uint64_t id) {
        std::scoped_lock lock{mutex};
        for(auto& entry:pending)if(entry.active && entry.path.id==id)entry.active=false;
    }
    FramePath Take(int index,int64_t argument,Clock::time_point now=Clock::now()) {
        std::scoped_lock lock{mutex};
        Pending* found=nullptr;
        for(auto& entry:pending)
            if(entry.active && entry.index==index && entry.argument==argument &&
               (!found || entry.path.id<found->path.id))found=&entry;
        FramePath path{};
        if(found){path=found->path;found->active=false;}
        path.gpu_flip=now;
        if(previous_gpu!=Clock::time_point{})path.gpu_interval=Milliseconds(previous_gpu,now);
        previous_gpu=now;return path;
    }
    static double Milliseconds(Clock::time_point start,Clock::time_point end) {
        return start!=Clock::time_point{} && end>=start ?
            std::chrono::duration<double,std::milli>(end-start).count() : 0.0;
    }
private:
    struct Pending {bool active{};int index{};int64_t argument{};FramePath path;};
    std::mutex mutex;
    std::array<Pending,64> pending{};
    uint64_t serial{};
    Clock::time_point previous_submit{},previous_gpu{};
};
inline SubmissionTracker submissions;
// Written and reported only by the presentation thread, after its frame completes.
inline FramePath completed_path;
inline void CompletePath(const FramePath& path){completed_path=path;}
struct Event {const char* stage{}; Clock::time_point end{}; double ms{}; Clock::time_point start{};};
inline double Overlap(const Event& event,Clock::time_point begin,Clock::time_point end) {
    if (!event.stage || event.start==Clock::time_point{} || event.end<event.start || end<=begin) return 0;
    const auto first=std::max(event.start,begin),last=std::min(event.end,end);
    return last>first ? std::chrono::duration<double,std::milli>(last-first).count() : 0;
}
struct WindowSpan {const Event* event{};double overlap{};};
inline std::array<WindowSpan,4> SelectWindow(const std::array<Event,128>& events,unsigned count,
                                           Clock::time_point begin,Clock::time_point end) {
    std::array<WindowSpan,4> selected{};
    for(unsigned i=0;i<count;++i) {
        const auto& event=events[i];const double overlap=Overlap(event,begin,end);
        if(overlap<=0)continue;
        auto* slot=&selected.back();
        for(auto& entry:selected)if(entry.event && entry.event->stage==event.stage){slot=&entry;break;}
        if(overlap<=slot->overlap)continue;
        *slot={&event,overlap};
        std::sort(selected.begin(),selected.end(),[](const auto& a,const auto& b){return a.overlap>b.overlap;});
    }
    return selected;
}
inline void ReportWindow(const char* label,const std::array<Event,128>& events,unsigned count,
                         Clock::time_point begin,Clock::time_point end) {
    if(SubmissionTracker::Milliseconds(begin,end)<1.0)return;
    const auto selected=SelectWindow(events,count,begin,end);
    if(!selected[0].event)return;
    std::printf("Frame hitch %s CPU overlaps (concurrent/nested, not additive):",label);
    for(const auto& span:selected)if(span.event) {
        const auto& e=*span.event;
        std::printf(" %s span=%.2fms overlap=%.2fms;",e.stage,e.ms,span.overlap);
    }
    std::printf("\n");
}
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
    slot.event={stage,end,ms,start};
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
            if(events[j].ms>peak)peak=events[j].ms;
            ++calls;
        }
        std::printf(" %s=%.2fms/%u;",events[i].stage,peak,calls);
    }
    std::printf("\n");
    if(completed_path.gpu_flip!=Clock::time_point{}) {
        const auto& p=completed_path;
        const auto ms=SubmissionTracker::Milliseconds;
        std::printf("Frame hitch CPU path: submission #%llu; guest submit interval=%.2f ms, "
            "GPU-thread flip interval=%.2f ms; submit->flip=%.2f ms, preparation=%.2f ms, "
            "prepared->present=%.2f ms, acquire=%.2f ms, setup+enqueue=%.2f ms, "
            "present+SDK state=%.2f ms (CPU timestamps; missing submission is #0)\n",
            static_cast<unsigned long long>(p.id),p.submit_interval,p.gpu_interval,
            ms(p.submitted,p.gpu_flip),ms(p.gpu_flip,p.prepared),ms(p.prepared,p.present_enter),
            ms(p.present_enter,p.acquired),ms(p.acquired,p.enqueued),ms(p.enqueued,p.returned));
        ReportWindow("before flip",events,count,p.submitted,p.gpu_flip);
        ReportWindow("preparation",events,count,p.gpu_flip,p.prepared);
    }
}
}
