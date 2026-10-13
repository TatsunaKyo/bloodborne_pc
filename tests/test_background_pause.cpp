// SPDX-License-Identifier: GPL-2.0-or-later
// Exercise the actual native gate, including activation while all frame workers wait.
#include "bbport_background.h"
#include <atomic>
#include <cassert>
#include <chrono>
#include <thread>
#include <vector>
using namespace std::chrono_literals;

template<class F> void Until(F predicate) {
    const auto deadline = std::chrono::steady_clock::now() + 2s;
    while (!predicate()) {
        assert(std::chrono::steady_clock::now() < deadline);
        std::this_thread::sleep_for(1ms);
    }
}
int main() {
    std::atomic<int> frames{0}, window_events{0};
    std::atomic<bool> activate{false};
    std::vector<std::jthread> workers;
    for (int i = 0; i < 3; ++i) workers.emplace_back([&](std::stop_token stop) {
        while (!stop.stop_requested()) {
            BbBackground::Wait(stop);
            if (!stop.stop_requested()) ++frames;
            std::this_thread::sleep_for(1ms);
        }
    });
    std::jthread window([&](std::stop_token stop) {
        while (!stop.stop_requested()) {
            ++window_events;
            if (activate.exchange(false)) BbBackground::Update(false);
            std::this_thread::sleep_for(1ms);
        }
    });
    for (int cycle = 0; cycle < 30; ++cycle) {
        BbBackground::Update(true);
        std::this_thread::sleep_for(5ms); // let already-started frame work reach the gate
        const int frozen = frames.load(), events = window_events.load();
        // A busy test runner may not schedule the event thread within 10 ms.
        // Require an actual event-pump tick, with the existing bounded timeout.
        Until([&] { return window_events > events; });
        const auto before = BbBackground::PausedNanoseconds();
        std::this_thread::sleep_for(10ms);
        assert(frames == frozen);
        assert(window_events > events);
        assert(BbBackground::PausedNanoseconds() >= before + 8'000'000);
        activate = true; // activation is handled by the live event thread, not a foreground poll
        Until([&] { return !BbBackground::Paused() && frames > frozen; });
        const auto total = BbBackground::PausedNanoseconds();
        std::this_thread::sleep_for(2ms);
        assert(BbBackground::PausedNanoseconds() == total);
    }
    assert(BbBackground::PausedNanoseconds() >= 30 * 12'000'000ull);
    BbBackground::Update(true);
    std::atomic<bool> stopped{false};
    std::jthread waiter([&](std::stop_token stop) { BbBackground::Wait(stop); stopped = true; });
    waiter.request_stop();
    Until([&] { return stopped.load(); });
    assert(BbBackground::Paused());
    BbBackground::Update(false);
}
