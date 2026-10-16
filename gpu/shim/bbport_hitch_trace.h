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
inline thread_local const char* role = "other";
inline void SetRole(const char* name) { role = name; }
struct Event {
    const char* stage{};
    const char* role{};
    Clock::time_point start{}, end{};
    uint32_t thread{};
};
struct Slot { std::atomic_flag busy = ATOMIC_FLAG_INIT; Event event; };
inline constexpr size_t Capacity = 65536;
inline std::array<Slot, Capacity> journal;
inline std::atomic<uint64_t> writes{}, lost{};
inline void Record(const char* stage, Clock::time_point start, Clock::time_point end) {
    if (!Enabled()) return;
    if (!thread_id) thread_id = next_thread.fetch_add(1, std::memory_order_relaxed);
    auto& slot = journal[writes.fetch_add(1, std::memory_order_relaxed) % Capacity];
    if (slot.busy.test_and_set(std::memory_order_acquire)) {
        lost.fetch_add(1, std::memory_order_relaxed);
        return;
    }
    slot.event = {stage, role, start, end, thread_id};
    slot.busy.clear(std::memory_order_release);
}
struct Scope {
    const char* stage;
    Clock::time_point start;
    explicit Scope(const char* name) : stage{Enabled() ? name : nullptr},
        start{stage ? Clock::now() : Clock::time_point{}} {}
    ~Scope() { if (stage) Record(stage, start, Clock::now()); }
};
struct Summary {
    const char* stage{};
    const char* role{};
    uint32_t thread{};
    uint64_t count{};
    double total{}, peak{};
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
            return true;
        }
    }
    return false;
}
inline void Report(const char* phase, Clock::time_point begin, Clock::time_point end) {
    if (!Enabled() || end <= begin || begin == Clock::time_point{}) return;
    std::array<Summary, 256> rows{};
    const auto before = writes.load(std::memory_order_relaxed);
    Clock::time_point oldest{};
    unsigned collisions = 0, omitted = 0;
    for (auto& slot : journal) {
        if (slot.busy.test_and_set(std::memory_order_acquire)) { ++collisions; continue; }
        const auto event = slot.event;
        slot.busy.clear(std::memory_order_release);
        if (event.stage && (oldest == Clock::time_point{} || event.start < oldest)) oldest = event.start;
        if (!Accumulate(rows, event, begin, end)) ++omitted;
    }
    std::sort(rows.begin(), rows.end(), [](const auto& a, const auto& b) { return a.total > b.total; });
    const auto after = writes.load(std::memory_order_relaxed);
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
}
}
