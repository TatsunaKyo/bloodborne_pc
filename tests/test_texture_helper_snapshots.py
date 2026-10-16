# SPDX-License-Identifier: GPL-2.0-or-later
# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
"""Execute the actual texture-helper handoff and actual Info snapshot accessors.

R43 control: the helper has separate TLS and reads a later draw's shared Info.
Current: the helper sees the calling draw, including early returns and reuse.
Vulkan binding is stubbed; these are CPU ownership checks, not game validation.
"""
import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = 'cbb4acbc71372f20b7291ebe9e50baf8c7e4a3b7'
CPP = 'gpu/shadps4/video_core/renderer_vulkan/vk_rasterizer.cpp'
HEADER = 'gpu/shadps4/video_core/renderer_vulkan/vk_rasterizer.h'
INFO = 'gpu/shadps4/shader_recompiler/info.h'

HARNESS = r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <span>
#include <thread>
#include <vector>
#include "common/scope_exit.h"
using u32 = std::uint32_t;
using VAddr = std::uint64_t;
#define ASSERT(condition) assert(condition)
namespace Shader {
constexpr u32 MaxStageTypes = 6;
namespace Backend { struct Bindings {}; }
struct Info {
    std::vector<u32> user_data;
    std::vector<u32> flattened_ud_buf;
    VAddr pgm_base{};
@ACCESSORS@
};
}
struct PreparedStage { u32 user{}, flat{}; VAddr base{}; };
struct Seen {
    u32 user{}, flat{}; VAddr base{};
    bool operator==(const Seen&) const = default;
};
class Rasterizer {
public:
@TASK@
    int stop_at = -1;
    unsigned checks = 0;
    std::vector<u32> checked_images;
    std::vector<Seen> bound;
    bool TexturesBindableOnHelper(const Shader::Info& info, const PreparedStage* prepared) {
        checked_images.push_back(prepared ? prepared->flat : info.FlatUserData()[0]);
        return int(checks++) != stop_at;
    }
    void BindTextures(const Shader::Info& info, const PreparedStage* prepared,
                      Shader::Backend::Bindings&, u32&, bool&, bool) {
        bound.push_back(prepared ? Seen{prepared->user, prepared->flat, prepared->base}
                                : Seen{info.UserData()[0], info.FlatUserData()[0], info.ProgramBase()});
    }
    static void RunTextureTask(void*);
};
@RUN@

bool RunCase(u32 draw, bool snapshots, bool prepared, int stop_at, bool previous_tls) {
    using Shader::Info;
    std::array<Info,2> infos;
    std::array<std::array<u32,1>,2> packet_ud{}, packet_flat{};
    std::array<PreparedStage,2> prepared_values;
    Rasterizer self;
    self.stop_at = stop_at;
    auto& task = self.texture_task;
    task.count = 2;
    for (u32 i = 0; i < task.count; ++i) {
        packet_ud[i][0] = draw * 100 + i + 10;
        packet_flat[i][0] = draw * 100 + i + 20;
        prepared_values[i] = {draw * 100 + i + 40, draw * 100 + i + 50,
                              VAddr(draw * 100 + i + 60)};
        infos[i].user_data = {draw * 100 + i + 1000};
        infos[i].flattened_ud_buf = {draw * 100 + i + 2000};
        infos[i].pgm_base = draw * 100 + i + 3000;
        task.stages[i] = {&infos[i], prepared ? &prepared_values[i] : nullptr, {}, i};
        Info::ud_snapshots[i] = {&infos[i], packet_ud[i].data(), 1,
                                packet_flat[i].data(), 1, VAddr(draw * 100 + i + 30)};
    }
    Info::num_ud_snapshots = snapshots ? task.count : 0;
    // This is the production publication fragment, immediately before Fork.
@PUBLISH@
    Info::num_ud_snapshots = 0;

    // Shared Info already describes a later draw by the time the helper runs.
    // Only packet memory is authoritative. Avoid a data race in the fixture:
    // the overwrite completes before the new helper thread starts.
    for (u32 i = 0; i < task.count; ++i) {
        infos[i].user_data[0] += 7000;
        infos[i].flattened_ud_buf[0] += 8000;
        infos[i].pgm_base += 9000;
    }
    bool restored = true;
    std::jthread helper([&] {
        Info sentinel;
        const std::array<u32,1> old_ud{77}, old_flat{88};
        if (previous_tls) {
            Info::ud_snapshots[0] = {&sentinel, old_ud.data(), 1, old_flat.data(), 1, 99};
            Info::num_ud_snapshots = 1;
        }
        const auto old_count = Info::num_ud_snapshots;
        const auto old = Info::ud_snapshots[0];
        // Invoke twice on the same thread: every early return must restore TLS.
        Rasterizer::RunTextureTask(&self);
        restored = Info::num_ud_snapshots == old_count;
        if (old_count) {
            const auto& now = Info::ud_snapshots[0];
            restored &= now.info == old.info && now.user_data == old.user_data &&
                        now.flat == old.flat && now.pgm_base == old.pgm_base &&
                        now.user_data_size == old.user_data_size && now.flat_size == old.flat_size;
        }
        task.completed = 0;
        self.checks = 0;
        Rasterizer::RunTextureTask(&self);
        restored &= Info::num_ud_snapshots == old_count;
        if (old_count) {
            restored &= sentinel.UserData()[0] == 77 && sentinel.FlatUserData()[0] == 88 &&
                        sentinel.ProgramBase() == 99;
        }
        Info::num_ud_snapshots = 0;
    });
    helper.join();
    assert(restored);
    const unsigned checked = stop_at < 0 ? 2u : unsigned(stop_at + 1);
    const unsigned bound = stop_at < 0 ? 2u : unsigned(stop_at);
    assert(self.checked_images.size() == checked * 2 && self.bound.size() == bound * 2);
    assert(task.completed == bound);
    bool mismatch = false;
    for (unsigned invocation = 0; invocation < 2; ++invocation) {
        for (unsigned i = 0; i < checked; ++i) {
            const u32 expected = prepared ? prepared_values[i].flat :
                snapshots ? packet_flat[i][0] : infos[i].flattened_ud_buf[0];
            mismatch |= self.checked_images[invocation * checked + i] != expected;
        }
        for (unsigned i = 0; i < bound; ++i) {
            const Seen expected = prepared
                ? Seen{prepared_values[i].user, prepared_values[i].flat, prepared_values[i].base}
                : snapshots
                    ? Seen{packet_ud[i][0], packet_flat[i][0], VAddr(draw * 100 + i + 30)}
                    : Seen{infos[i].user_data[0], infos[i].flattened_ud_buf[0], infos[i].pgm_base};
            mismatch |= self.bound[invocation * bound + i] != expected;
        }
    }
    // Both the serial fallback and prepared descriptors must work in the old control too.
    if (!snapshots || prepared) assert(!mismatch);
    return mismatch;
}
int main() {
    unsigned cases = 0, mismatches = 0;
    for (u32 draw = 1; draw <= 24; ++draw)
        for (bool snapshots : {false,true})
            for (bool prepared : {false,true})
                for (int stop_at : {-1,0,1})
                    for (bool previous_tls : {false,true}) {
                        mismatches += RunCase(draw,snapshots,prepared,stop_at,previous_tls);
                        ++cases;
                    }
#if CONTROL
    assert(mismatches == 144);
    std::printf("R43 CONTROL: wrong draw descriptors in %u/%u cases; actual helper lacks caller TLS.\n",
                mismatches,cases);
#else
    assert(mismatches == 0);
    std::printf("PASS: %u cases, actual helper uses packet descriptors; early returns and reuse restore TLS.\n",
                cases);
#endif
}
'''


def contents(path, control):
    if control:
        return subprocess.check_output(['git', 'show', BASE + ':' + path], cwd=ROOT, text=True)
    return (ROOT / path).read_text()


def source(control):
    cpp, header, info = (contents(path, control) for path in (CPP, HEADER, INFO))
    accessors = info[info.index('    struct UdSnapshot {'):
                     info.index('    template <typename T>', info.index('    struct UdSnapshot {'))]
    start = header.index('    struct TextureTask {')
    task = header[start:header.index('} texture_task;', start) + len('} texture_task;')]
    start = cpp.index('void Rasterizer::RunTextureTask(')
    run = cpp[start:cpp.index('\nvoid Rasterizer::JoinBindHelper(', start)]
    if control:
        publish = ''
    else:
        start = cpp.index('        task.num_snapshots =', cpp.index('bool Rasterizer::BindResources('))
        publish = cpp[start:cpp.index('        bind_helper.Fork(', start)]
    return (HARNESS.replace('@ACCESSORS@', accessors).replace('@TASK@', task)
            .replace('@RUN@', run).replace('@PUBLISH@', publish))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', default='g++')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='texture-helper-') as temporary:
        folder = Path(temporary)
        for name, control in [('r43', True), ('current', False)]:
            cpp = folder / (name + '.cpp')
            binary = folder / (name + ('.exe' if Path(args.compiler).stem.lower() in ('cl', 'clang-cl') else ''))
            cpp.write_text(source(control))
            if Path(args.compiler).stem.lower() in ('cl', 'clang-cl'):
                command = [args.compiler, '/nologo', '/O2', '/EHsc', '/std:c++20',
                           '/UNDEBUG', '/DCONTROL=' + str(int(control)),
                           '/I' + str(ROOT / 'gpu/shadps4'), str(cpp), '/Fe:' + str(binary)]
            else:
                command = [args.compiler, '-std=c++20', '-O2', '-UNDEBUG', '-Wall', '-Wextra',
                           '-pthread', '-DCONTROL=' + str(int(control)),
                           '-I', str(ROOT / 'gpu/shadps4'), str(cpp), '-o', str(binary)]
            subprocess.run(command, cwd=folder, check=True)
            subprocess.run([str(binary)], cwd=ROOT, check=True, timeout=60)


if __name__ == '__main__':
    main()
