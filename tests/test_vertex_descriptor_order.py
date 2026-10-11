"""Reproduce stale vertex-table reuse through the production selection/binding checks.

This is a CPU command-data fixture, not a substitute for the Hunter's Dream capture.
The V# layout, guest pointer reader, fetch attributes and both acceptance branches
are read from the renderer sources. Only Vulkan handles and pipeline lookup are stubbed.
"""
from pathlib import Path
import argparse
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--compiler', default='g++')
parser.add_argument('--baseline', default='6766a0432c68c3cb43712fd8f0e6a5c70669f8f7')
args = parser.parse_args()


def source(path, baseline=False):
    if baseline:
        return subprocess.check_output(['git', 'show', f'{args.baseline}:{path}'], cwd=ROOT).decode()
    return (ROOT / path).read_text()


def section(text, start, end):
    a = text.index(start)
    return text[a:text.index(end, a)]


base = 'gpu/shadps4/'
resource = source(base + 'video_core/amdgpu/resource.h')
buffer = section(resource, 'struct Buffer {', '    CompMapping DstSelect()') + '};\n'
info = source(base + 'shader_recompiler/info.h')
snapshot = section(info, '    struct UdSnapshot {', '    std::span<const u32> FlatUserData()')
read_ud = section(info, '    template <typename T>\n    T ReadUdReg(', '    void PushUd(')
fetch = section(source(base + 'shader_recompiler/frontend/fetch_shader.h'),
                'struct VertexAttribute {', 'const u32* GetFetchShaderCode(')

fixture = r'''
#include <array>
#include <atomic>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <optional>
#include <span>
#include <vector>
using u8=std::uint8_t;using u32=std::uint32_t;using u64=std::uint64_t;
using s8=std::int8_t;using VAddr=std::uintptr_t;
namespace Serialization { struct Archive; }
namespace AmdGpu { @BUFFER@ }
namespace Shader {
namespace IR { constexpr u32 NumScalarRegs=104; }
enum class SwStage { Vertex };
enum class HwStage { Vertex };
struct Info {
    std::span<const u32> user_data;
    std::vector<u32> flattened_ud_buf;
    VAddr pgm_base=123;
    @SNAPSHOT@
    @READ_UD@
    void RefreshFlatBuf() { flattened_ud_buf.assign(user_data.begin(),user_data.end()); }
};
namespace Gcn { @FETCH@ }
}
namespace vk {
struct VertexInputAttributeDescription2EXT{};
struct VertexInputBindingDescription2EXT{};
}
namespace Vulkan { @PREPARED@ }
struct Program { Shader::Info info; };
struct PreparedStage {
    const Program* program;
    u64 hash;
    Shader::HwStage hw_stage;
    VAddr pgm_base;
    const u32* flat;
    u32 flat_size;
};
struct PreparedDraw {
    enum { Ready=1 };
    std::atomic<u32> state{Ready};
    u64 reg_checksum=456;
    int key=1;
    u32 num_stages=1;
    std::array<PreparedStage,1> stages;
    Vulkan::PreparedVertexInputs vertex{};
};
struct GuestProgram {
    Shader::Info* info;
    template<class T> T Address() const { return reinterpret_cast<T>(info->pgm_base); }
};
namespace AmdGpu {
struct Params {
    u64 hash=789;
    std::span<const u32> user_data;
    VAddr Base() const { return 123; }
};
Params GetParams(const GuestProgram& p) { return {789,p.info->user_data}; }
}
struct GraphicsPipeline {
    Shader::Info* info;
    std::optional<const Shader::Gcn::FetchShaderData> fetch;
    const auto& GetFetchShader() const { return fetch; }
    const Shader::Info& GetStage(Shader::SwStage) const { return *info; }
};
struct Owner { GraphicsPipeline* pipeline; auto get() const { return pipeline; } };
struct Regs {
    GuestProgram pgm;
    const GuestProgram* ProgramForStage(u32) const { return &pgm; }
};
struct Liverpool { u64 gfx_reg_checksum=456; Regs regs; };
struct PipelineCache {
    Liverpool* liverpool;
    std::map<int,Owner> graphics_pipelines;
    const GraphicsPipeline* TryPreparedPipeline(const PreparedDraw& prepared);
};
@TRY_PIPELINE@
namespace FrameCapture { bool Active() { return false; } }
namespace BbToggle { constexpr u64 PreparedResources=4096; bool Disabled(u64) { return false; } }
struct Instance { bool IsVertexInputDynamicState() const { return true; } };
const Vulkan::PreparedVertexInputs* Binding(const GraphicsPipeline* pipeline,
                                           const PreparedDraw* prepared) {
    Instance instance;
    @BINDING@
    return ready;
}
int main() {
    using Shader::Gcn::VertexAttribute;
    int stale_pipeline=0,stale_bind=0,cases=0;
    // Includes a stream in a second table, a typed instruction offset and an
    // inline descriptor. The user-data pointer words stay unchanged on reuse.
    for(int change=0;change<8;++change) for(unsigned frame=0;frame<128;++frame) {
        std::array<AmdGpu::Buffer,3> table{};
        for(unsigned i=0;i<table.size();++i) {
            table[i].base_address=0x100000+frame*4096+i*512;
            table[i].stride=16;table[i].num_records=32;
            table[i].data_format=14;table[i].num_format=7;
            table[i].dst_sel_x=4;table[i].dst_sel_y=5;
        }
        std::array<u32,16> words{};
        const void* ptr=table.data();std::memcpy(words.data(),&ptr,sizeof(ptr));
        ptr=table.data()+2;std::memcpy(words.data()+2,&ptr,sizeof(ptr));
        std::memcpy(words.data()+8,&table[0],sizeof(table[0]));
        Program p;p.info.user_data=words;p.info.RefreshFlatBuf();
        Shader::Gcn::FetchShaderData fs;
        fs.attributes={{0,0,4,0,0,0,0},{1,0,4,0,4,0,8,14,7},
                       {2,0,4,2,0,3,0},{3,0,4,u8(Shader::IR::NumScalarRegs),8,0,0}};
        GraphicsPipeline pipeline{&p.info,fs};
        std::array<AmdGpu::Buffer,4> captured;
        for(unsigned i=0;i<captured.size();++i)captured[i]=fs.attributes[i].GetSharp(p.info);
        auto flat=p.info.flattened_ud_buf;
        PreparedDraw draw;
        draw.stages[0]={&p,789,Shader::HwStage::Vertex,123,flat.data(),u32(flat.size())};
        draw.vertex.valid=true;draw.vertex.count=4;draw.vertex.buffers=captured.data();
        Liverpool liver{456,Regs{GuestProgram{&p.info}}};
        PipelineCache cache{&liver,{{1,{&pipeline}}}};
        assert(cache.TryPreparedPipeline(draw)==&pipeline);
        assert(Binding(&pipeline,&draw)==&draw.vertex);
        auto originals=words;
        switch(change) {
        case 0:table[0].base_address+=0x700000;break; // different mesh, same valid format
        case 1:table[0].stride=32;break;
        case 2:table[0].num_records=64;break;
        case 3:table[0].data_format=13;break;
        case 4:table[0].num_format=4;break;
        case 5:table[0].dst_sel_x=6;break;
        case 6:table[1].base_address+=0x800000;break; // changed non-first attribute
        case 7:table[2].base_address+=0x900000;break; // separate instance/skinning stream
        }
        assert(words==originals);
        assert(p.info.flattened_ud_buf==flat); // The old validation still passes.
        if(cache.TryPreparedPipeline(draw))++stale_pipeline;
        if(Binding(&pipeline,&draw))++stale_bind;
        ++cases;
    }
    // A stage-B snapshot freezes pointer words; it cannot freeze the pointed-to table.
    std::array<AmdGpu::Buffer,1> table{};table[0].base_address=0x100000;
    std::array<u32,16> ud{};const void* ptr=table.data();std::memcpy(ud.data(),&ptr,sizeof(ptr));
    Program p;p.info.user_data=ud;
    Shader::Gcn::FetchShaderData fs;fs.attributes={{0,0,4,0,0,0,0}};
    auto saved=ud;
    Shader::Info::ud_snapshots[0]={&p.info,saved.data(),16,nullptr,0,123};
    Shader::Info::num_ud_snapshots=1;
    auto captured=fs.attributes[0].GetSharp(p.info);
    Vulkan::PreparedVertexInputs ready{};ready.valid=true;ready.count=1;ready.buffers=&captured;
    GraphicsPipeline pipeline{&p.info,fs};PreparedDraw draw;draw.vertex=ready;
    assert(Binding(&pipeline,&draw)==&draw.vertex);
    table[0].base_address=0x900000;
    if(Binding(&pipeline,&draw))++stale_bind;
    ++cases;
    Shader::Info::num_ud_snapshots=0;
    std::printf("Vertex-table reuse cases: %d; stale pipelines accepted: %d; stale bindings accepted: %d\n",
                cases,stale_pipeline,stale_bind);
    return stale_pipeline||stale_bind ? 1:0;
}
'''
with tempfile.TemporaryDirectory(prefix='bb-vertex-tables-') as directory:
    temp = Path(directory)
    for label, old, expected in [('Revision 16', True, 1), ('production behavior', False, 0)]:
        prep = section(source(base+'video_core/renderer_vulkan/vk_draw_prep.h', old),
                       'struct PreparedVertexInputs {', 'struct PreparedDraw {')
        pipeline = section(source(base+'video_core/renderer_vulkan/vk_pipeline_cache.cpp', old),
                           'const GraphicsPipeline* PipelineCache::TryPreparedPipeline(',
                           'const GraphicsPipeline* PipelineCache::GetGraphicsPipeline(')
        binding = section(source(base+'video_core/renderer_vulkan/vk_rasterizer.cpp', old),
                          '    const auto& fetch = pipeline->GetFetchShader();\n    const PreparedVertexInputs* ready',
                          '    if (ready) {').replace('const PreparedVertexInputs* ready',
                                                     'const Vulkan::PreparedVertexInputs* ready')
        text = fixture
        for name, replacement in [('BUFFER',buffer),('SNAPSHOT',snapshot),('READ_UD',read_ud),
                                  ('FETCH',fetch),('PREPARED',prep),('TRY_PIPELINE',pipeline),
                                  ('BINDING',binding)]:
            text = text.replace('@'+name+'@',replacement)
        (temp/'fixture.cpp').write_text(text)
        subprocess.run(shlex.split(args.compiler)+['-std=c++23','-O2','-Wall','-Wextra','-Werror',
                         str(temp/'fixture.cpp'),'-o',str(temp/'fixture')],check=True)
        result=subprocess.run([str(temp/'fixture')],capture_output=True,text=True,timeout=30)
        print(label+': '+result.stdout.strip(),flush=True)
        assert result.returncode==expected,(label,result.stdout,result.stderr)
print('PASS: unchanged user-data pointers cannot validate overwritten vertex descriptors.')
