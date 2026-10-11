"""Execute the production F8 trigger and frame polling code without opening a game window."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root/'gpu/shadps4/video_core/renderer_vulkan/vk_temporal_upscaler.cpp').read_text()
start = source.index('int DumpFrame() {')
end = source.index('\nstruct DumpImage', start)
function = source[start:end]
program = r'''
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include "bbport_capture.h"
''' + function + r'''
int main(int argc, char** argv) {
    const auto directory = std::filesystem::path(argv[1]);
    const auto trigger = (directory/"capture.trigger").string();
    const auto passes = (directory/"passes.trigger").string();
    setenv("BB_DUMP_TRIGGER",trigger.c_str(),1);
    setenv("BB_CAPTURE_TRIGGER",passes.c_str(),1);
    setenv("BB_DUMP_POLL_FRAMES","1",1);
    setenv("BB_DUMP_FRAMES","8",1);
    BbCapture::GeometryKey key;
    unsetenv("BB_GEOMETRY_CAPTURE");
    assert(!key.Press(true,false));
    setenv("BB_GEOMETRY_CAPTURE","0",1);
    assert(!key.Press(true,false));
    setenv("BB_GEOMETRY_CAPTURE","1",1);
    assert(!key.Press(false,false));
    assert(!key.Press(true,true));
    assert(!std::filesystem::exists(trigger));
    assert(DumpFrame()==-1);
    assert(key.Press(true,false));
    assert(std::filesystem::exists(trigger) && std::filesystem::exists(passes));
    for (int i=0;i<8;++i) assert(DumpFrame()==i);
    assert(!std::filesystem::exists(trigger));
    assert(DumpFrame()==-1);
    assert(key.Press(true,false));
    assert(!std::filesystem::exists(trigger)); // One request; no unbounded disk/memory growth.
    assert(DumpFrame()==-1);
    // A failed trigger can be retried instead of being marked captured.
    BbCapture::GeometryKey retry;
    const auto missing=(directory/"missing"/"capture.trigger").string();
    setenv("BB_DUMP_TRIGGER",missing.c_str(),1);
    assert(retry.Press(true,false));
    setenv("BB_DUMP_TRIGGER",trigger.c_str(),1);
    assert(retry.Press(true,false));
    assert(std::filesystem::exists(trigger));
    std::filesystem::remove(trigger);
    std::puts("PASS: production F8 trigger is opt-in, ignores repeats, retries failed writes, requests one bounded batch, and frame polling captures eight consecutive frames immediately.");
}
'''
with tempfile.TemporaryDirectory(prefix='bb-capture-test-') as temporary:
    directory=Path(temporary)
    cpp=directory/'capture.cpp'; cpp.write_text(program)
    exe=directory/'capture'
    subprocess.run(['g++','-std=c++23','-Wall','-Wextra','-Werror','-Wno-unused-parameter',
                    '-I'+str(root/'gpu/shim'),str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe),str(directory)],check=True)
