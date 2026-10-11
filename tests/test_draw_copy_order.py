"""Exercise the actual draw queue and copy pool across a guest-memory replacement."""
from pathlib import Path
import argparse
import shlex
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--compiler', default='g++')
args = parser.parse_args()
ROOT = Path(__file__).resolve().parents[1]
header = (ROOT / 'gpu/shadps4/video_core/renderer_vulkan/vk_draw_pipe.h').read_text()
flush = '''            // A drained draw queue must not hide guest reads in stage B's thread-local
            // copy batch. Publish them before stage A can replace their source memory.
            // Flush once at the end of a queued burst, keeping copies batched per burst.
            if (at == published.load(std::memory_order_acquire)) {
                BbCopy::FlushBatch();
            }
'''
fixture = r'''
#include <array>
#include <atomic>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <vector>
#include "bbport_copy.h"
#include "vk_draw_pipe.h"
extern "C" { std::uint64_t runtime_disabled_optimizations = 0; }
struct Command { const void* source; void* destination; unsigned size; bool flush; };
void Copy(const BbCopy::Item& item) {
    std::memcpy(reinterpret_cast<void*>(item.destination),
                reinterpret_cast<const void*>(item.source), item.size);
}
void Record(void*, const u8* bytes, u32 size) {
    assert(size == sizeof(Command));
    Command cmd; std::memcpy(&cmd, bytes, sizeof(cmd));
    if (cmd.flush) { BbCopy::FlushBatch(); return; }
    BbCopy::QueueCopy({&Copy, nullptr, reinterpret_cast<u64>(cmd.source),
                      reinterpret_cast<u64>(cmd.destination), cmd.size, 0});
}
void Queue(Vulkan::DrawPipe& pipe, Command cmd) {
    std::memcpy(pipe.Begin(sizeof(cmd)), &cmd, sizeof(cmd));
    pipe.Commit(sizeof(cmd));
}
int main() {
    setenv("BB_COPY_THREADS", "2", 1);
    setenv("BB_PIPE_SPIN_US", "0", 1);
    int failures = 0, replaced = 0, cases = 0;
    Vulkan::DrawPipe pipe{&Record, nullptr};
    for (unsigned burst : {1u, 7u, 64u}) for (unsigned frame = 0; frame < 128; ++frame) {
        std::vector<std::array<u8, 32>> source(burst), destination(burst), original(burst);
        for (unsigned i = 0; i < burst; ++i) {
            source[i].fill(u8(frame + i)); destination[i].fill(0xff); original[i] = source[i];
            Queue(pipe, {source[i].data(), destination[i].data(), 32, false});
        }
        // The production ConstRam/write/fence paths drain the draw queue and wait for
        // host copies on stage A. Stage B's unpublished TLS batch was invisible to both.
        pipe.Drain(); BbCopy::WaitAsync();
        if (destination != original) ++failures;
        ++cases;
        for (auto& bytes : source) bytes.fill(0xee);
        // Flush on the owning thread, then finish, so no pointer outlives this iteration.
        Queue(pipe, {nullptr, nullptr, 0, true}); pipe.Drain(); BbCopy::WaitAsync();
        if (destination != original) ++replaced;
    }
    // Stage A's ordinary inline batch already drains correctly, and must keep doing so.
    std::array<u8, 32> source, destination{}; source.fill(42);
    BbCopy::QueueCopy(BbCopy::Item{&Copy, nullptr, reinterpret_cast<u64>(source.data()),
                                 reinterpret_cast<u64>(destination.data()), 32, 0});
    BbCopy::WaitAsync();
    assert(source == destination);
    std::printf("Draw-thread copy cases: %d; unfinished snapshots: %d; replaced-source snapshots: %d\n",
                cases, failures, replaced);
    return failures || replaced ? 1 : 0;
}
'''
with tempfile.TemporaryDirectory(prefix='bb-draw-copies-') as directory:
    temp = Path(directory)
    (temp / 'common').mkdir()
    (temp / 'common/types.h').write_text('#pragma once\n#include <cstdint>\nusing u8=std::uint8_t; using u32=std::uint32_t; using u64=std::uint64_t;\n')
    (temp / 'common/assert.h').write_text('#pragma once\n#include <cassert>\n#define ASSERT(expr) assert(expr)\n')
    (temp / 'common/thread.h').write_text('#pragma once\nnamespace Common { inline void SetCurrentThreadName(const char*) {} }\n')
    (temp / 'fixture.cpp').write_text(fixture)
    versions = [('previous behavior', header.replace(flush, ''), 1)]
    if flush in header:
        versions.append(('production behavior', header, 0))
    for label, code, expected in versions:
        (temp / 'vk_draw_pipe.h').write_text(code)
        subprocess.run(shlex.split(args.compiler) + ['-std=c++20', '-O2', '-pthread', '-Wall', '-Wextra', '-Werror',
                        '-I' + str(temp), '-I' + str(ROOT / 'gpu/shim'),
                        str(temp / 'fixture.cpp'), str(ROOT / 'gpu/shim/bbport_copy.cpp'),
                        '-o', str(temp / 'fixture')], check=True)
        result = subprocess.run([str(temp / 'fixture')], capture_output=True, text=True, timeout=30)
        print(label + ': ' + result.stdout.strip(), flush=True)
        assert result.returncode == expected, (label, result.stdout, result.stderr)
    if len(versions) == 2:
        print('PASS: copies leave the draw thread before a drained queue permits a guest write.')
