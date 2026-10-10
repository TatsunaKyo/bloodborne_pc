// SPDX-License-Identifier: GPL-2.0-or-later
// Exercises the production Vulkan adapter, with the driver's calls captured at the boundary.
#include "bbport_amd.h"
#include "bbport_settings.h"
#include <cassert>
#include <condition_variable>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <thread>
#include <vector>

namespace {
struct Call { VkAntiLagModeAMD mode; uint32_t cap; int stage; uint64_t frame; };
std::mutex mutex;
std::condition_variable cv;
std::vector<Call> calls;
bool feature = true, block = false, entered = false, released = false;
int queries{}, resolves{};
VKAPI_ATTR void VKAPI_CALL Query(VkPhysicalDevice, VkPhysicalDeviceFeatures2* data) {
    ++queries;
    auto* f = static_cast<VkPhysicalDeviceAntiLagFeaturesAMD*>(data->pNext);
    assert(f && f->sType == VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_ANTI_LAG_FEATURES_AMD);
    f->antiLag = feature;
}
VKAPI_ATTR void VKAPI_CALL Update(VkDevice dev, const VkAntiLagDataAMD* data) {
    assert(dev && data && data->sType == VK_STRUCTURE_TYPE_ANTI_LAG_DATA_AMD && !data->pNext);
    const auto* p = data->pPresentationInfo;
    assert(!p || (p->sType == VK_STRUCTURE_TYPE_ANTI_LAG_PRESENTATION_INFO_AMD && !p->pNext));
    std::unique_lock lock{mutex};
    calls.push_back({data->mode, data->maxFPS, p ? int(p->stage) : -1, p ? p->frameIndex : 0});
    assert(data->maxFPS == 0); // VideoOut, not the latency driver, owns both cap policies.
    if (p && p->stage == VK_ANTI_LAG_STAGE_INPUT_AMD && block) {
        entered = true; cv.notify_all();
        cv.wait(lock, [] {return released;});
    }
    if (p && p->stage == VK_ANTI_LAG_STAGE_PRESENT_AMD) {
        released = true; cv.notify_all();
    }
}
VKAPI_ATTR PFN_vkVoidFunction VKAPI_CALL Resolve(VkDevice, const char* name) {
    ++resolves;
    assert(std::strcmp(name,"vkAntiLagUpdateAMD") == 0);
    return reinterpret_cast<PFN_vkVoidFunction>(Update);
}
}

int main() {
    auto& s = BbSettings::Get();
    const auto dev = reinterpret_cast<VkDevice>(uintptr_t(1));
    assert(!BbAmd::QueryFeature({},false,true,Query) && queries == 0);
    assert(!BbAmd::QueryFeature({},true,false,Query) && queries == 0);
    assert(!BbAmd::QueryFeature({},true,true,nullptr));
    feature = false;
    assert(!BbAmd::QueryFeature({},true,true,Query));
    feature = true;
    assert(BbAmd::QueryFeature({},true,true,Query) && queries == 2);
    BbAmd::BindDevice(dev,false,Resolve);
    s.amd_antilag = true; BbAmd::BeforeInput();
    assert(!s.amd_antilag_supported && calls.empty() && resolves == 0);
    BbAmd::BindDevice(dev,true,nullptr);
    assert(!s.amd_antilag_supported && calls.empty());
    BbAmd::BindDevice(dev,true,Resolve);
    assert(s.amd_antilag_supported && calls.size() == 1 && calls.back().mode == VK_ANTI_LAG_MODE_OFF_AMD);
    s.amd_antilag = false; BbAmd::BeforeInput();
    assert(calls.size() == 1);
    s.amd_antilag = true; s.window_focused = true;
    BbAmd::BeforeInput(); BbAmd::BeforeInput();
    assert(calls.size() == 2 && calls.back().stage == VK_ANTI_LAG_STAGE_INPUT_AMD);
    const auto first_id = calls.back().frame;
    BbAmd::QueueFlip(0,10);
    BbAmd::BeforeInput(); BbAmd::QueueFlip(1,11);
    const auto second = BbAmd::FinishRender(1,11);
    const auto first = BbAmd::FinishRender(0,10);
    assert(first.index == first_id && second.index > first.index);
    assert(!BbAmd::FinishRender(0,10).index);
    const auto count = calls.size();
    BbAmd::BeforePresent(first,false); // FSR interpolated frame or redisplay.
    BbAmd::BeforePresent({},true);
    assert(calls.size() == count);
    BbAmd::BeforePresent(first,true);
    assert(calls.back().frame == first_id && calls.back().stage == VK_ANTI_LAG_STAGE_PRESENT_AMD);
    BbAmd::BeforeInput(); BbAmd::QueueFlip(2,12); BbAmd::CancelFlip(2,12);
    assert(!BbAmd::FinishRender(2,12).index);

    // A driver's finite input wait must never lock out the presentation it is waiting for.
    block = true; released = false;
    std::thread input{BbAmd::BeforeInput};
    {
        std::unique_lock lock{mutex};
        assert(cv.wait_for(lock,std::chrono::seconds(2),[] {return entered;}));
    }
    BbAmd::BeforePresent(second,true);
    input.join(); block = false;
    assert(calls.back().frame == second.index);
    BbAmd::QueueFlip(3,13);
    s.amd_antilag = false;
    BbAmd::BeforeInput();
    assert(calls.back().mode == VK_ANTI_LAG_MODE_OFF_AMD && calls.back().stage == -1);
    const auto off_count = calls.size();
    BbAmd::BeforeInput(); assert(calls.size() == off_count);
    s.amd_antilag = true; s.window_focused = false; s.background_mode = BbSettings::Background30;
    BbAmd::BeforeInput(); assert(calls.size() == off_count);
    s.background_mode = BbSettings::BackgroundRun;
    BbAmd::BeforeInput(); assert(calls.back().mode == VK_ANTI_LAG_MODE_ON_AMD);
    BbAmd::QueueFlip(4,14); const auto old = BbAmd::FinishRender(4,14);
    BbAmd::Shutdown();
    const auto shutdown_count = calls.size();
    BbAmd::BeforeInput(); BbAmd::BeforePresent(old,true);
    assert(calls.size() == shutdown_count && !s.amd_antilag_supported);
    BbAmd::BindDevice(dev,true,Resolve);
    const auto rebound_count = calls.size();
    BbAmd::BeforePresent(old,true); assert(calls.size() == rebound_count);
    BbAmd::Shutdown();
    std::puts("AMD Anti-Lag 2: PASS (capability, opt-in, input/real-present IDs, queued flips, FG exclusion, independent caps, focus, concurrent driver wait, device lifetime)");
}
