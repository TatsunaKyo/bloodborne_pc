// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <algorithm>
#include <condition_variable>
#include <deque>
#include <functional>
#include <mutex>
#include <thread>
#include <vector>

namespace Common {

// Adapt demanded-pipeline priority from andrecabralgit to the existing compiler queue.
// A draw can claim its queued build instead of waiting behind unrelated preloads.
class PipelineBuildQueue {
public:
    explicit PipelineBuildQueue(unsigned count) {
        for (unsigned i = 0; i < count; ++i) workers.emplace_back([this] {
            for (;;) {
                Job job;
                {
                    std::unique_lock lock(mutex);
                    changed.wait(lock, [this] { return stopping || !jobs.empty(); });
                    if (jobs.empty()) return;
                    job = std::move(jobs.front());
                    jobs.pop_front();
                    ++active;
                }
                Execute(std::move(job));
            }
        });
    }

    ~PipelineBuildQueue() { Stop(); }

    bool Submit(std::function<void()> run, const void* owner = nullptr) {
        std::scoped_lock lock(mutex);
        if (stopping || jobs.size() >= 128) return false;
        jobs.push_back({owner, std::move(run)});
        changed.notify_one();
        return true;
    }

    bool RunPending(const void* owner) {
        if (!owner) return false;
        Job job;
        {
            std::scoped_lock lock(mutex);
            const auto it = std::find_if(jobs.begin(), jobs.end(),
                [owner](const Job& pending) { return pending.owner == owner; });
            if (it == jobs.end()) return false;
            job = std::move(*it);
            jobs.erase(it);
            ++active;
        }
        Execute(std::move(job));
        return true;
    }

    void Drain() {
        std::unique_lock lock(mutex);
        idle.wait(lock, [this] { return jobs.empty() && !active; });
    }

    void Stop() {
        {
            std::scoped_lock lock(mutex);
            stopping = true;
        }
        changed.notify_all();
        for (auto& worker : workers) if (worker.joinable()) worker.join();
        Drain(); // Includes jobs claimed by the draw thread.
    }

private:
    struct Job {
        const void* owner{};
        std::function<void()> run;
    };

    void Complete() {
        std::scoped_lock lock(mutex);
        --active;
        if (jobs.empty() && !active) idle.notify_all();
    }

    void Execute(Job job) {
        try { job.run(); }
        catch (...) { Complete(); throw; }
        Complete();
    }

    std::mutex mutex;
    std::condition_variable changed, idle;
    bool stopping = false;
    size_t active = 0;
    std::deque<Job> jobs;
    std::vector<std::thread> workers;
};

} // namespace Common
