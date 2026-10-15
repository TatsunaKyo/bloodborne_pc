// SPDX-License-Identifier: GPL-2.0-or-later
// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
// NVAPI layout/flags adapted from NVIDIA's MIT SDK. See third_party/nvapi/LICENSE.txt.
#pragma once
#include <cstdint>
#include <cstdio>
#include <cstddef>
#include <chrono>
#include <condition_variable>
#include <functional>
#include <mutex>
#include <thread>
namespace BbNvidia::Preset {
// NV_NGX_DLSS_OVERRIDE_GET_STATE_PARAMS_V1, public NVAPI 570+.
struct DriverState {
    uint32_t version{}, process{};
    uint64_t sr{}, rr{}, fg{};
    float scaling_ratio{};
    uint32_t performance{}, render_preset{}, frame_count{}, frame_preset{}, frame_mode{};
    uint32_t reserved[2]{};
};
static_assert(sizeof(DriverState)==64);
// Current NVAPI V2; keep V1 for drivers that return INCOMPATIBLE_STRUCT_VERSION.
struct DriverStateV2 {
    uint32_t version{}, process{};
    uint64_t sr{}, rr{}, fg{};
    float scaling_ratio{};
    uint32_t performance{}, render_preset{}, frame_count{}, frame_preset{}, frame_mode{};
    uint64_t reserved0{};
    uint32_t reserved1{}, reserved[7]{};
};
static_assert(sizeof(DriverStateV2)==96 && offsetof(DriverStateV2,frame_preset)==48);
template<class Query> int ReadState(Query&& query, uint32_t process, DriverState& state) {
    DriverStateV2 current{};
    current.version=uint32_t(sizeof(current))|(2u<<16);current.process=process;
    int result=query(&current);
    state={};
    if (result==-9) {
        state.version=uint32_t(sizeof(state))|(1u<<16);state.process=process;
        return query(&state);
    }
    if (result==0) {
        state.process=process;state.sr=current.sr;state.rr=current.rr;state.fg=current.fg;
        state.frame_preset=current.frame_preset;state.frame_count=current.frame_count;
        state.frame_mode=current.frame_mode;
    }
    return result;
}
inline constexpr uint64_t PresetFlag=1ull<<5, Created=1ull<<9, Evaluated=1ull<<10;
inline constexpr uint64_t ErrorMask=0x1full<<16;
inline int Reported(const DriverState& state) {
    constexpr auto required=PresetFlag|Created|Evaluated;
    return !(state.fg&ErrorMask) && (state.fg&required)==required &&
        state.frame_preset>=1 && state.frame_preset<=3 ? int(state.frame_preset) : -1;
}
inline const char* ErrorName(uint64_t flags) {
    if (flags&(1ull<<20)) return "runtime load failed";
    if (flags&(1ull<<19)) return "runtime/model not found";
    if (flags&(1ull<<18)) return "driver profile error";
    if (flags&(1ull<<17)) return "override denied";
    if (flags&(1ull<<16)) return "override failed";
    return "unconfirmed";
}
// The profile letter is useful (as in ReLimiter), but is not execution proof.
inline void FormatLabel(char* label, size_t size, bool active, int reported,
                        int profile, uint64_t errors) {
    if (!active) std::snprintf(label,size,"FG model:off");
    else if (reported>=1 && reported<=3 && !errors)
        std::snprintf(label,size,"FG model:%c",'A'+reported-1);
    else if (errors) std::snprintf(label,size,"FG model:%s",profile>=1 && profile<=3 ?
        (profile==1 ? "A!" : profile==2 ? "B!" : "C!") : "error");
    else if (profile>=1 && profile<=3) std::snprintf(label,size,"FG model:%c?",'A'+profile-1);
    else std::snprintf(label,size,"FG model:?");
}
// Driver feedback is diagnostic IO. It must never run on Present/Reflex threads.
class Observer {
public:
    void Start(std::function<void()> poll, std::function<void()> finish,
               std::chrono::milliseconds period=std::chrono::seconds(1)) {
        if (worker.joinable()) return;
        worker=std::jthread([this,poll=std::move(poll),finish=std::move(finish),period](std::stop_token stop) {
            while (!stop.stop_requested()) {
                poll();
                std::unique_lock lock{mutex};
                wake.wait_for(lock,stop,period,[]{return false;});
            }
            finish();
        });
    }
    void Stop() {
        if (worker.joinable()) {worker.request_stop();worker.join();}
    }
    ~Observer() {Stop();}
private:
    std::mutex mutex;
    std::condition_variable_any wake;
    std::jthread worker;
};
} // namespace BbNvidia::Preset
