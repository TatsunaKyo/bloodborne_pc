// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <array>
#include <atomic>
#include <condition_variable>
#include <cstdint>
#include <mutex>
#include <limits>
#include <thread>
#include "bbport_hitch_trace.h"

namespace BbPageWatch {
// Only permission revocations are queued. Grants and host map changes first
// drain an issued sequence. The apply callback must never acquire guest VMA,
// tracker or GPU locks: callers can hold those locks while waiting for it.
template <size_t Capacity = 2048>
class Queue {
public:
    using Apply = void (*)(uintptr_t, uint64_t, uint32_t);
    explicit Queue(Apply apply_) : apply{apply_}, worker{[this] { Run(); }} {}
    Queue(const Queue&) = delete;
    ~Queue() {
        Wait();
        { std::scoped_lock lock{mutex}; stopping = true; }
        available.notify_one();
        worker.join();
    }
    uint64_t Push(uintptr_t address, uint64_t bytes, uint32_t protection, uintptr_t domain = 0) {
        std::unique_lock lock{mutex};
        space.wait(lock, [this] { return used < Capacity; });
        const uint64_t sequence = issued.load(std::memory_order_relaxed) + 1;
        jobs[(head + used) % Capacity] = {address, bytes, protection, sequence, domain, false};
        ++used;
        issued.store(sequence, std::memory_order_release);
        lock.unlock(); available.notify_one();
        return sequence;
    }
    uint64_t Seal() {
        std::scoped_lock lock{mutex};
        if (used) jobs[(head + used - 1) % Capacity].sealed = true;
        return issued.load(std::memory_order_acquire);
    }
    void Wait() { Wait(Seal()); }
    void Wait(uint64_t sequence) {
        if (complete.load(std::memory_order_acquire) >= sequence) return;
        BbHitch::Trace::Scope trace{"page protection dependency"};
        std::unique_lock lock{mutex};
        finished.wait(lock, [this, sequence] {
            if (complete.load(std::memory_order_acquire) >= sequence) return true;
            wake_at = std::min(wake_at, sequence);
            return false;
        });
    }
    uint64_t Issued() const { return issued.load(std::memory_order_acquire); }
    uint64_t Complete() const { return complete.load(std::memory_order_acquire); }
private:
    struct Job {
        uintptr_t address; uint64_t bytes; uint32_t protection;
        uint64_t sequence; uintptr_t domain; bool sealed;
    };
    void Run() {
        BbHitch::Trace::SetRole("page protection");
        for (;;) {
            std::array<Job, 64> batch{};
            size_t count = 0;
            uint64_t sequence = 0;
            {
                std::unique_lock lock{mutex};
                available.wait(lock, [this] { return used || stopping; });
                if (!used && stopping) return;
                do {
                    auto& job = batch[count++] = jobs[head];
                    head = (head + 1) % Capacity; --used;
                    sequence = job.sequence;
                    if (job.sealed) break; // never merge across a captured dependency
                } while (used && count < batch.size());
            }
            space.notify_all();
            // Domains identify one committed Windows mapping view. Permission
            // segments have already been clipped to guest permissions. Tighten
            // only; a grant/remap drains the queue before changing this domain.
            bool sortable = true;
            for (size_t i = 0; i < count; ++i) sortable &= batch[i].domain != 0;
            if (sortable) {
                std::sort(batch.begin(), batch.begin() + count, [](const Job& a, const Job& b) {
                    if (a.domain != b.domain) return a.domain < b.domain;
                    if (a.protection != b.protection) return a.protection < b.protection;
                    return a.address < b.address;
                });
            }
            for (size_t i = 0; i < count; ++i) {
                auto job = batch[i];
                while (sortable && i + 1 < count && batch[i+1].domain == job.domain &&
                       batch[i+1].protection == job.protection &&
                       batch[i+1].address <= job.address + job.bytes) {
                    const auto& next = batch[++i];
                    job.bytes = std::max(job.address + job.bytes, next.address + next.bytes) - job.address;
                }
                BbHitch::Trace::Scope trace{"host page protection", job.address, job.bytes};
                apply(job.address, job.bytes, job.protection);
            }
            bool wake = false;
            {
                std::scoped_lock lock{mutex};
                complete.store(sequence, std::memory_order_release);
                // Do not wake all snapshot/fault waiters on every small job.
                // Waiters register the next sequence they actually depend on.
                if (sequence >= wake_at) {
                    wake_at = std::numeric_limits<uint64_t>::max();
                    wake = true;
                }
            }
            if (wake) finished.notify_all();
        }
    }
    Apply apply;
    std::mutex mutex;
    std::condition_variable available, space, finished;
    std::array<Job, Capacity> jobs{};
    size_t head{}, used{};
    bool stopping{};
    uint64_t wake_at = std::numeric_limits<uint64_t>::max();
    std::atomic<uint64_t> issued{}, complete{};
    std::thread worker;
};
struct Ticket {
    Queue<>* queue{};
    uint64_t sequence{};
    void Wait() const { if (queue) queue->Wait(sequence); }
};
inline std::atomic<Queue<>*> installed_queue{};
inline Ticket Capture() {
    auto* queue = installed_queue.load(std::memory_order_acquire);
    return {queue, queue ? queue->Seal() : 0};
}
void Install();
} // namespace BbPageWatch
