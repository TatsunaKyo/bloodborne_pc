"""Execute production graphics support serialization, including generated fragments."""
from pathlib import Path
import os
import shlex
import subprocess
import tempfile
from test_renderer_cache_refresh import method

ROOT = Path(__file__).resolve().parents[1]
PATH = "gpu/shadps4/video_core/renderer_vulkan/vk_pipeline_serialization.cpp"
BASE = "d7062615e1cd1ee68e591ca7e36956619de1f975"
CPP = r'''
#include "common/serdes.h"
#include <array>
#include <cassert>
#include <cstdio>
struct Support {
 std::array<u32,4>vertex_attributes{},vertex_bindings{},divisors{};
 u32 multisampling{};std::vector<u32>tcs,tes,fragment;
 void Serialize(Serialization::Archive&)const;
 bool Deserialize(Serialization::Archive&);
};
@METHODS@
int main(){
 unsigned cases=0;
 for(unsigned n:{0,1,8,128}){
  Support input;input.vertex_attributes={1,2,3,4};input.vertex_bindings={5,6,7,8};
  input.divisors={9,10,11,12};input.multisampling=13;input.tcs={14,15};input.tes={16,17};
  for(unsigned i=0;i<n;++i)input.fragment.push_back(0x7230203u+i);
  Serialization::Archive blob;input.Serialize(blob);auto bytes=blob.TakeOff();
  Serialization::Archive stored{std::move(bytes)};Support output;assert(output.Deserialize(stored));assert(stored.IsEoS());
  assert(input.vertex_attributes==output.vertex_attributes && input.vertex_bindings==output.vertex_bindings);
  assert(input.divisors==output.divisors && input.multisampling==output.multisampling && input.tcs==output.tcs && input.tes==output.tes);
#if CURRENT
  assert(input.fragment==output.fragment);
#else
  assert(output.fragment.empty());
#endif
  ++cases;
 }
 printf("%s: %u actual graphics-pipeline payload round trips; generated fragment shader %s.\n",CURRENT?"PASS":"R51 CONTROL",cases,CURRENT?"preserved":"omitted");
}
'''
with tempfile.TemporaryDirectory(prefix="pipeline-payload-") as directory:
    for current in (False, True):
        source = ((ROOT / PATH).read_text() if current else
                  subprocess.check_output(["git", "show", BASE + ":" + PATH], cwd=ROOT, text=True))
        definitions = "\n".join(method(source, name) for name in (
            "void GraphicsPipeline::SerializationSupport::Serialize(",
            "bool GraphicsPipeline::SerializationSupport::Deserialize("))
        definitions = definitions.replace("GraphicsPipeline::SerializationSupport::", "Support::")
        cpp = Path(directory) / ("current.cpp" if current else "r51.cpp")
        cpp.write_text(CPP.replace("@METHODS@", definitions))
        exe = cpp.with_suffix("")
        subprocess.run([*shlex.split(os.environ.get("CXX", "g++")), "-std=c++23", "-O1", "-UNDEBUG",
                        "-DCURRENT=" + str(int(current)), "-I" + str(ROOT / "gpu/shadps4"),
                        str(cpp), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True, timeout=30)
