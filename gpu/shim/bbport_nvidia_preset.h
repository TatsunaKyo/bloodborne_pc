// SPDX-License-Identifier: GPL-2.0-or-later
// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
// NVAPI layout/flags adapted from NVIDIA's MIT SDK. See third_party/nvapi/LICENSE.txt.
#pragma once
#include <cstdint>
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
inline constexpr uint64_t PresetFlag=1ull<<5, Created=1ull<<9, Evaluated=1ull<<10;
inline constexpr uint64_t ErrorMask=0x1full<<16;
inline int Reported(const DriverState& state) {
    constexpr auto required=PresetFlag|Created|Evaluated;
    return !(state.fg&ErrorMask) && (state.fg&required)==required &&
        state.frame_preset>=1 && state.frame_preset<=3 ? int(state.frame_preset) : -1;
}
// Driver feedback is diagnostic IO. It must never run on Present/Reflex threads.
class Observer {
public:
    void Start(std::function<void()> poll, std::function<void()> finish) {
        if (worker.joinable()) return;
        worker=std::jthread([this,poll=std::move(poll),finish=std::move(finish)](std::stop_token stop) {
            while (!stop.stop_requested()) {
                poll();
                std::unique_lock lock{mutex};
                wake.wait_for(lock,stop,std::chrono::seconds(1),[]{return false;});
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
