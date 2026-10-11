"""Compile the production ConstRam-dump branch and reproduce delayed guest reads."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'gpu/shadps4/video_core/amdgpu/liverpool.cpp').read_text()
start = source.index('case PM4ItOpcode::DumpConstRam: {')
end = source.index('case PM4ItOpcode::IncrementCeCounter:', start)
branch = source[start:end]
fixture = r'''
#include <array>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <functional>
#include <vector>
using u32 = unsigned; using u8 = unsigned char;
enum class PM4ItOpcode { DumpConstRam };
namespace Vulkan { struct DrawPipe { enum { ReasonConstRam }; }; }
struct PM4DumpConstRam {
    void* destination;
    template<class T> T Address() const { return static_cast<T>(destination); }
    u32 Offset() const { return 0; }
    u32 Size() const { return 256; }
};
struct Rasterizer {
    std::vector<std::function<void()>> draws, recorder, workers;
    int waits = 0;
    void DrainDrawPipe(int = 0) { run(draws); }
    void WaitHostCopies() { ++waits; run(draws); run(recorder); run(workers); }
    static void run(std::vector<std::function<void()>>& queue) {
        auto tasks = std::move(queue); queue.clear();
        for (auto& task : tasks) task();
    }
};
void dump(Rasterizer* rasterizer, void* header, const std::array<u8,256>& heap) {
    struct { std::array<u8,256> constants_heap; } cblock{heap};
    switch (PM4ItOpcode::DumpConstRam) {
    @BRANCH@
    }
}
int main() {
    int failures=0;
    // Vertex/index source reads can run directly, on the Vulkan recorder or on
    // copy workers, with or without the separate draw-recording stage.
    for (bool draw_pipe : {false,true}) for (int copy_path=0;copy_path<3;++copy_path)
    for (unsigned frame=0;frame<512;++frame) {
        std::array<u8,256> guest, snapshot{}, replacement;
        guest.fill(u8(frame)); replacement.fill(u8(frame+1));
        auto before=guest;
        Rasterizer r;
        auto read=[&]{snapshot=guest;};
        auto record=[&]{
            if (copy_path==0) read();
            else if (copy_path==1) r.recorder.push_back(read);
            else r.workers.push_back(read);
        };
        if (draw_pipe) r.draws.push_back(record); else record();
        PM4DumpConstRam packet{guest.data()};
        dump(&r,&packet,replacement);
        r.WaitHostCopies();
        if (snapshot != before) ++failures;
        assert(guest==replacement); // The new constants must still be installed.
        assert(r.draws.empty() && r.recorder.empty() && r.workers.empty());
    }
    // A dump without a rasterizer still performs its ordinary memory write.
    std::array<u8,256> guest{},replacement; replacement.fill(7);
    PM4DumpConstRam packet{guest.data()};dump(nullptr,&packet,replacement);assert(guest==replacement);
    std::printf("ConstRam delayed-read cases: 3072; corrupted snapshots: %d\n",failures);
    return failures ? 1 : 0;
}
'''
with tempfile.TemporaryDirectory(prefix='bb-const-ram-') as directory:
    root = Path(directory)
    for label, code, expected in (
        ('previous behavior', branch.replace('rasterizer->WaitHostCopies();', ''), 1),
        ('production behavior', branch, 0),
    ):
        (root/'fixture.cpp').write_text(fixture.replace('@BRANCH@', code))
        subprocess.run(['g++', '-std=c++20', '-O2', '-Wall', '-Wextra', '-Werror',
                        str(root/'fixture.cpp'), '-o', str(root/'fixture')], check=True)
        result = subprocess.run([str(root/'fixture')], capture_output=True, text=True)
        print(label + ': ' + result.stdout.strip())
        assert result.returncode == expected, (label, result.stdout, result.stderr)
print('PASS: the previous branch reproduces geometry-source corruption; the production branch completes all host reads before replacement.')
