// SPDX-License-Identifier: GPL-2.0-or-later
#include "bbport_background.h"
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <mutex>

namespace BbBackground {
namespace {
std::atomic<bool> paused{false};
std::atomic<std::uint64_t> elapsed{0};
std::mutex mutex;
std::condition_variable_any changed;
std::chrono::steady_clock::time_point started;
void (*audio_callback)(int){};
}

void Update(bool pause) {
    if (paused.load(std::memory_order_acquire) == pause) return;
    {
        std::scoped_lock lock{mutex};
        if (paused.load(std::memory_order_relaxed) == pause) return;
        if (pause) {
            started = std::chrono::steady_clock::now();
        } else {
            elapsed.fetch_add(std::chrono::duration_cast<std::chrono::nanoseconds>(
                std::chrono::steady_clock::now() - started).count(), std::memory_order_relaxed);
        }
        paused.store(pause, std::memory_order_release);
        if (audio_callback) audio_callback(pause);
    }
    changed.notify_all();
}

void SetAudioCallback(void (*callback)(int)) {
    std::scoped_lock lock{mutex};
    audio_callback = callback;
    if (callback) callback(paused.load(std::memory_order_relaxed));
}

bool Paused() { return paused.load(std::memory_order_acquire); }

void Wait(std::stop_token stop) {
    if (!Paused()) return;
    std::unique_lock lock{mutex};
    changed.wait(lock, stop, [] { return !Paused(); });
}

std::uint64_t PausedNanoseconds() {
    if (!Paused()) return elapsed.load(std::memory_order_acquire);
    std::scoped_lock lock{mutex};
    auto total = elapsed.load(std::memory_order_relaxed);
    if (Paused()) total += std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now() - started).count();
    return total;
}
}

extern "C" std::uint64_t bbgpu_background_paused_ns() {
    return BbBackground::PausedNanoseconds();
}

extern "C" void bbgpu_set_background_audio_callback(void (*callback)(int)) {
    BbBackground::SetAudioCallback(callback);
}
