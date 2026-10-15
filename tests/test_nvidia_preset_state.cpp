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
    // Current V2 and old V1 drivers must agree. Only -9 permits an ABI retry;
    // never hide a real API failure by issuing another query.
    int queries=0;
    auto modern=[&](void* data) {
        ++queries;auto& v=*static_cast<DriverStateV2*>(data);
        assert(v.version==(sizeof(v)|(2u<<16)) && v.process==777);
        v.fg=complete;v.frame_preset=3;return 0;
    };
    assert(ReadState(modern,777,state)==0 && Reported(state)==3 && queries==1);
    queries=0;
    auto legacy=[&](void* data) {
        ++queries;auto version=*static_cast<uint32_t*>(data);
        if ((version>>16)==2) return -9;
        auto& v=*static_cast<DriverState*>(data);
        assert(v.version==(sizeof(v)|(1u<<16)) && v.process==777);
        v.fg=complete;v.frame_preset=2;return 0;
    };
    assert(ReadState(legacy,777,state)==0 && Reported(state)==2 && queries==2);
    queries=0;
    auto failure=[&](void*) {++queries;return -1;};
    assert(ReadState(failure,777,state)==-1 && queries==1 && state.fg==0);
    char label[64];
    FormatLabel(label,sizeof(label),true,3,2,0);assert(std::string(label)=="FG model:C");
    FormatLabel(label,sizeof(label),true,-1,3,0);assert(std::string(label)=="FG model:C?");
    FormatLabel(label,sizeof(label),true,-1,3,1ull<<19);assert(std::string(label)=="FG model:C!");
    FormatLabel(label,sizeof(label),true,-1,-1,0);assert(std::string(label)=="FG model:?");
    FormatLabel(label,sizeof(label),false,3,3,0);assert(std::string(label)=="FG model:off");
    assert(std::string(ErrorName(1ull<<19))=="runtime/model not found");
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
