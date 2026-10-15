// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
// SPDX-License-Identifier: GPL-2.0-or-later
#include "bbport_nvidia_preset.h"
#include "bbport_settings.h"
#include <cassert>
#include <cstdio>
#include <future>
int main() {
    using namespace BbNvidia::Preset;
    DriverState state{};
    constexpr auto complete=PresetFlag|Created|Evaluated;
    for (int preset=1;preset<=3;++preset) {
        state.frame_preset=preset;
        for (auto flags : {uint64_t(0), PresetFlag, PresetFlag|Created, Created|Evaluated}) {
            state.fg=flags;assert(Reported(state)==-1);
        }
        state.fg=complete;assert(Reported(state)==preset);
        for (int error=16;error<=20;++error) {
            state.fg=complete|(1ull<<error);assert(Reported(state)==-1);
        }
        auto key=BbSettings::NvidiaFgPresetKey(preset);
        assert(BbSettings::ParseNvidiaFgPreset(key)==preset);
    }
    state.fg=complete;state.frame_preset=0;assert(Reported(state)==-1);
    state.frame_preset=4;assert(Reported(state)==-1);
    assert(BbSettings::ParseNvidiaFgPreset("M")==0);
    assert(BbSettings::ParseNvidiaFgPreset("3")==0);
    // A blocked driver query runs on the observer, not the caller/Present thread.
    using namespace std::chrono_literals;
    Observer observer;
    std::promise<void> entered, release;
    auto gate=release.get_future().share();
    std::atomic<bool> finished{};
    const auto caller=std::this_thread::get_id();
    observer.Start([&] {assert(std::this_thread::get_id()!=caller);entered.set_value();gate.wait();},
                   [&] {finished=true;});
    assert(entered.get_future().wait_for(2s)==std::future_status::ready);
    auto stopping=std::async(std::launch::async,[&] {observer.Stop();});
    assert(stopping.wait_for(20ms)==std::future_status::timeout && !finished);
    release.set_value();
    assert(stopping.wait_for(500ms)==std::future_status::ready);stopping.get();assert(finished);
    std::puts("PASS: NVIDIA FG presets require evaluated driver feedback and reject errors/unknown models.");
    std::puts("PASS: driver telemetry stays off the caller thread and shutdown waits for outstanding queries.");
}
