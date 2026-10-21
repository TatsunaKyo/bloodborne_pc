// SPDX-License-Identifier: GPL-2.0-or-later
// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
#pragma once
#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <cstring>
#include <vector>

// Opt-in CPU flight recorder. It observes the existing renderer; it does not
// change queue ownership, GPU barriers, quality, frame caps or shader policy.
namespace BbHitch::Trace {
using Clock = std::chrono::steady_clock;
inline bool Enabled() {
    static const bool enabled = [] {
        const char* value = std::getenv("BB_HITCH_TRACE");
        return value && value[0] == '1';
    }();
    return enabled;
}
inline std::atomic<uint32_t> next_thread{1};
inline thread_local uint32_t thread_id{};
inline thread_local uint32_t native_thread_id{};
inline std::atomic<uint32_t (*)()> native_thread_provider{};
inline thread_local const char* role = "other";
inline void SetRole(const char* name) { role = name; }
struct Event {
    const char* stage{};
    const char* role{};
    Clock::time_point start{}, end{};
    uint32_t thread{};
    uint64_t address{}, bytes{}; // optional resource metadata; no memory contents
    uint64_t id{}, dependency{};
    uint32_t native_thread{};
};
using Exporter = void (*)(const char*, Clock::time_point, Clock::time_point,
                         std::vector<Event>, uint64_t, unsigned, bool);
inline std::atomic<Exporter> exporter{};
void InstallExporter();
void FlushExporter();
struct Slot { std::atomic_flag busy = ATOMIC_FLAG_INIT; Event event; };
inline constexpr size_t Capacity = 65536;
inline std::array<Slot, Capacity> journal;
inline std::atomic<uint64_t> writes{}, lost{};
inline void Record(const char* stage, Clock::time_point start, Clock::time_point end,
                   uint64_t address = 0, uint64_t bytes = 0, uint64_t id = 0, uint64_t dependency = 0) {
    if (!Enabled()) return;
    if (!thread_id) thread_id = next_thread.fetch_add(1, std::memory_order_relaxed);
    if (!native_thread_id) {
        if (auto provider = native_thread_provider.load(std::memory_order_acquire)) native_thread_id = provider();
    }
    auto& slot = journal[writes.fetch_add(1, std::memory_order_relaxed) % Capacity];
    if (slot.busy.test_and_set(std::memory_order_acquire)) {
        lost.fetch_add(1, std::memory_order_relaxed);
        return;
    }
    slot.event = {stage, role, start, end, thread_id, address, bytes, id, dependency, native_thread_id};
    slot.busy.clear(std::memory_order_release);
}
inline void Point(const char* stage, uint64_t address = 0, uint64_t bytes = 0,
                  uint64_t id = 0, uint64_t dependency = 0) {
    if (!Enabled()) return;
    const auto now = Clock::now();
    Record(stage, now, now, address, bytes, id, dependency);
}
struct Scope {
    const char* stage;
    Clock::time_point start;
    uint64_t address, bytes, id, dependency;
    explicit Scope(const char* name, uint64_t address_ = 0, uint64_t bytes_ = 0,
                   uint64_t id_ = 0, uint64_t dependency_ = 0)
        : stage{Enabled() ? name : nullptr},
          start{stage ? Clock::now() : Clock::time_point{}}, address{address_}, bytes{bytes_},
          id{id_}, dependency{dependency_} {}
    ~Scope() { if (stage) Record(stage, start, Clock::now(), address, bytes, id, dependency); }
};
struct Summary {
    const char* stage{};
    const char* role{};
    uint32_t thread{};
    uint64_t count{};
    double total{}, peak{};
    uint64_t bytes{}, min_address{UINT64_MAX}, max_address{};
};
inline double Overlap(const Event& e, Clock::time_point begin, Clock::time_point end) {
    if (!e.stage || e.start == Clock::time_point{} || e.end < e.start || end <= begin) return 0;
    const auto first = std::max(e.start, begin), last = std::min(e.end, end);
    return last > first ? std::chrono::duration<double, std::milli>(last-first).count() : 0;
}
template <size_t N>
inline bool Accumulate(std::array<Summary, N>& rows, const Event& event,
                       Clock::time_point begin, Clock::time_point end) {
    const double ms = Overlap(event, begin, end);
    if (!ms) return true;
    for (auto& row : rows) {
        if (!row.stage || (row.stage == event.stage && row.thread == event.thread)) {
            if (!row.stage) row = {event.stage, event.role, event.thread};
            ++row.count; row.total += ms; row.peak = std::max(row.peak, ms);
            row.bytes += event.bytes;
            if (event.bytes) {
                row.min_address = std::min(row.min_address, event.address);
                row.max_address = std::max(row.max_address, event.address);
            }
            return true;
        }
    }
    return false;
}
inline void Report(const char* phase, Clock::time_point begin, Clock::time_point end) {
    if (!Enabled() || end <= begin || begin == Clock::time_point{}) return;
    std::array<Summary, 256> rows{};
    auto output = exporter.load(std::memory_order_acquire);
    std::vector<Event> evidence;
    if (output) evidence.reserve(16384);
    bool truncated = false;
    const auto before = writes.load(std::memory_order_relaxed);
    Clock::time_point oldest{};
    unsigned collisions = 0, omitted = 0;
    for (auto& slot : journal) {
        if (slot.busy.test_and_set(std::memory_order_acquire)) { ++collisions; continue; }
        const auto event = slot.event;
        slot.busy.clear(std::memory_order_release);
        if (event.stage && (oldest == Clock::time_point{} || event.start < oldest)) oldest = event.start;
        if (output && event.stage && event.end >= begin && event.start <= end) {
            bool relevant = event.bytes || event.id || event.dependency;
            for (const char* name : {"shader/pipeline compile", "draw pipe drain", "host copies drain",
                                     "GPU timeline wait", "Reflex sleep", "queue present + FG state"})
                relevant |= std::strcmp(event.stage, name) == 0;
            if (relevant) {
                if (evidence.size() < 16384) evidence.push_back(event);
                else truncated = true;
            }
        }
        if (!Accumulate(rows, event, begin, end)) ++omitted;
    }
    std::sort(rows.begin(), rows.end(), [](const auto& a, const auto& b) { return a.total > b.total; });
    const auto after = writes.load(std::memory_order_relaxed);
    if (output) output(phase, begin, end, std::move(evidence), lost.load(std::memory_order_relaxed),
                       collisions, truncated || (before > Capacity && oldest != Clock::time_point{} && oldest > begin));
    std::printf("Frame trace %s: %.3f ms window; inclusive nested spans, not additive; "
                "ring=%llu, overwritten=%llu, lost=%llu, read collisions=%u, category overflow=%u, "
                "window prefix may be missing=%u\n", phase,
        std::chrono::duration<double,std::milli>(end-begin).count(),
        static_cast<unsigned long long>(std::min<uint64_t>(after, Capacity)),
        static_cast<unsigned long long>(after > Capacity ? after-Capacity : 0),
        static_cast<unsigned long long>(lost.load(std::memory_order_relaxed)), collisions, omitted,
        unsigned(before > Capacity && oldest != Clock::time_point{} && oldest > begin));
    for (size_t i = 0; i < std::min<size_t>(16, rows.size()) && rows[i].stage; ++i) {
        const auto& row = rows[i];
        std::printf("  CPU thread %u (%s): %s calls=%llu total=%.3f ms peak=%.3f ms\n",
            row.thread, row.role, row.stage, static_cast<unsigned long long>(row.count), row.total, row.peak);
    }
    for (const auto& row : rows) {
        if (!row.stage || !row.bytes) continue;
        std::printf("  Resource trace thread %u (%s): %s calls=%llu bytes=%llu "
                    "total=%.3f ms peak=%.3f ms start-addresses=%#llx..%#llx "
                    "(whole-operation bytes for spans touching this window)\n",
            row.thread, row.role, row.stage, static_cast<unsigned long long>(row.count),
            static_cast<unsigned long long>(row.bytes), row.total, row.peak,
            static_cast<unsigned long long>(row.min_address),
            static_cast<unsigned long long>(row.max_address));
    }
}
}
