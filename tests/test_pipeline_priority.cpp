// SPDX-License-Identifier: GPL-2.0-or-later
#include "common/pipeline_build_queue.h"
#include <atomic>
#include <cassert>
#include <chrono>
#include <future>
#include <iostream>
using namespace std::chrono_literals;

int main() {
    Common::PipelineBuildQueue queue(1);
    std::promise<void> entered;
    std::atomic_bool release = false;
    assert(queue.Submit([&] { entered.set_value(); release.wait(false); }));
    entered.get_future().wait();
    int owner;
    std::atomic_int count = 0;
    std::promise<void> ready;
    auto result = ready.get_future();
    assert(queue.Submit([&] { ++count; ready.set_value(); }, &owner));
    assert(result.wait_for(5ms) == std::future_status::timeout);
    assert(queue.RunPending(&owner));
    assert(result.wait_for(0ms) == std::future_status::ready && count == 1);
    assert(!queue.RunPending(&owner));
    for (int round = 0; round < 1000; ++round) {
        count = 0;
        assert(queue.Submit([&] { ++count; }, &owner));
        std::thread first([&] { queue.RunPending(&owner); });
        std::thread second([&] { queue.RunPending(&owner); });
        first.join(); second.join();
        assert(count == 1);
    }
    std::promise<void> claimed;
    std::atomic_bool release_claim = false;
    assert(queue.Submit([&] { claimed.set_value(); release_claim.wait(false); }, &owner));
    std::thread draw([&] { assert(queue.RunPending(&owner)); });
    claimed.get_future().wait();
    release = true; release.notify_all();
    auto drained = std::async(std::launch::async, [&] { queue.Drain(); });
    auto stopped = std::async(std::launch::async, [&] { queue.Stop(); });
    assert(drained.wait_for(5ms) == std::future_status::timeout);
    assert(stopped.wait_for(5ms) == std::future_status::timeout);
    release_claim = true; release_claim.notify_all();
    draw.join(); drained.get(); stopped.get();
    assert(!queue.Submit([] {}));
    std::cout << "PASS: demanded build bypasses blocked FIFO; 1000 double-claim races execute once; Drain/Stop wait for claimed work.\n";
}
