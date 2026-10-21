# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Execute production swapchain recovery/drain scopes under competing queue work."""
import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PRESENTER = 'gpu/shadps4/video_core/renderer_vulkan/vk_presenter.cpp'
SWAPCHAIN = 'gpu/shadps4/video_core/renderer_vulkan/vk_swapchain.cpp'
BASELINE = '26fa4d6e8ecd2a39b9ad707c205941690dd40e5d'


def extract(source, start, end):
    a = source.index(start)
    return source[a:source.index(end, a)]


HARNESS = r'''
#include <cassert>
#include <chrono>
#include <condition_variable>
#include <future>
#include <functional>
#include <mutex>
#include <cstdio>
#include <vector>
#include <utility>
#include "bbport_hitch.h"
using u32 = unsigned;
#define ASSERT_MSG(value, ...) assert(value)
template<class... T> void SetObjectName(T&&...) {}
using namespace std::chrono_literals;
struct Scheduler { static std::mutex submit_mutex; };
std::mutex Scheduler::submit_mutex;
std::mutex gate;
std::condition_variable changed;
bool draining{}, release_drain{}, recovery_order{};
namespace vk {
enum class Result { eSuccess };
using Semaphore = int;
struct Device {
    std::pair<Result, Semaphore> createSemaphore(int) const {
        static int next = 1;
        return {Result::eSuccess, next++};
    }
    Result waitIdle() const {
        std::unique_lock lock{gate};
        draining = true; changed.notify_all();
        changed.wait(lock, [] { return release_drain; });
        return Result::eSuccess;
    }
};
}
struct Instance { vk::Device GetDevice() { return {}; } };
Instance instance;
u32 frame_index, image_index, image_count;
std::vector<vk::Semaphore> image_acquired, present_ready;
REFRESH
namespace BbNvidia {
bool Present(void*, const std::function<bool()>& call) { return call(); }
void BeforeSwapchainChange() {
    auto probe = std::async(std::launch::async, [] {
        if (!Scheduler::submit_mutex.try_lock()) return false;
        Scheduler::submit_mutex.unlock(); return true;
    });
    assert(probe.get());
}
}
namespace BbAmd { void BeforePresent(int, bool) {} }
struct Frame { int amd_token{}; BbHitch::FramePath hitch_path{}; };
struct Window { int GetWidth() { return 1920; } int GetHeight() { return 1080; } };
struct Swapchain {
    bool Present() { return false; }
    void Recreate(int, int) {
        auto probe = std::async(std::launch::async, [] {
            if (!Scheduler::submit_mutex.try_lock()) return false;
            Scheduler::submit_mutex.unlock(); return true;
        });
        recovery_order = probe.get();
    }
};
void Recovery() {
    Frame value; Frame* frame = &value; Window window; Swapchain swapchain;
    bool final = true, is_game_frame = true, is_reusing_frame = false;
PRESENT
    assert(!presented);
}
void Drain() {
    Instance instance;
DRAIN
    assert(wait_result == vk::Result::eSuccess);
}
int main() {
    unsigned invalid_slots = 0;
    for (unsigned previous_count = 2; previous_count <= 8; ++previous_count) {
        for (image_count = 2; image_count <= 8; ++image_count) {
            frame_index = image_index = previous_count - 1;
            RefreshSemaphores();
            assert(image_acquired.size() == image_count && present_ready.size() == image_count);
            if (frame_index >= image_acquired.size()) ++invalid_slots;
            if (EXPECTED) assert(frame_index == 0 && image_index == 0);
        }
    }
    assert(invalid_slots == (EXPECTED ? 0u : 21u));
    std::printf("Swapchain image-count transitions: 49 cases, %u invalid acquisition slots\n", invalid_slots);
    Recovery();
    assert(recovery_order == EXPECTED);
    auto drain = std::async(std::launch::async, Drain);
    { std::unique_lock lock{gate}; assert(changed.wait_for(lock, 2s, [] { return draining; })); }
    auto queue = std::async(std::launch::async, [] {
        std::scoped_lock lock{Scheduler::submit_mutex};
    });
    const bool progressed = queue.wait_for(100ms) == std::future_status::ready;
    { std::scoped_lock lock{gate}; release_drain = true; } changed.notify_all();
    drain.get(); queue.get();
    assert(progressed != EXPECTED);
    std::puts(EXPECTED ? "PASS production recovery: NVIDIA retirement precedes queue lock; GPU drain excludes queue work"
                      : "PASS Revision25 control: reversed recovery lock order and concurrent GPU-drain queue work reproduced");
}
'''


def prepare(folder):
    folder.mkdir(parents=True, exist_ok=True)
    for label, reference, corrected in [('revision25', BASELINE, False), ('current', None, True)]:
        def source(path):
            return subprocess.check_output(['git', 'show', reference + ':' + path], cwd=ROOT, text=True) if reference else (ROOT / path).read_text()
        present = extract(source(PRESENTER), '        bool presented;', '        BbOverlay::RecordPresent')
        drain = extract(source(SWAPCHAIN), '    BbNvidia::BeforeSwapchainChange();', '    if (wait_result')
        refresh = extract(source(SWAPCHAIN), 'void Swapchain::RefreshSemaphores()', 'void Swapchain::SetupImages()')
        refresh = refresh.replace('void Swapchain::RefreshSemaphores()', 'void RefreshSemaphores()')
        path = folder / (label + '.cpp')
        path.write_text(HARNESS.replace('PRESENT', present).replace('DRAIN', drain).replace('REFRESH', refresh)
                        .replace('EXPECTED', 'true' if corrected else 'false'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='workshop-recovery-') as temporary:
        folder = args.prepare.resolve() if args.prepare else Path(temporary)
        prepare(folder)
        if not args.prepare:
            for name in ('revision25', 'current'):
                binary = folder / name
                subprocess.run(['g++', '-std=c++20', '-pthread', '-Wall', '-Wextra', '-Werror',
                                '-I'+str(ROOT/'gpu/shim'), str(folder / (name + '.cpp')), '-o', str(binary)], check=True)
                subprocess.run([str(binary)], check=True, timeout=10)
