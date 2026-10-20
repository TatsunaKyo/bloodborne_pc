# SPDX-License-Identifier: GPL-2.0-or-later
"""Execute the production jitter-selection block, including single world quads."""
from pathlib import Path
import os,shlex,subprocess,tempfile
root=Path(__file__).resolve().parents[1]
s=(root/'gpu/shadps4/video_core/renderer_vulkan/vk_rasterizer.cpp').read_text()
a=s.index('    draw_jitter = {};',s.index('// bbport: jitter geometry'))
b=s.index('    UpdateDynamicState(',a)
body=s[a:b]
prefix=r'''
#include <array>
#include <cassert>
#include <cstdio>
#include <optional>
struct Upscaler {bool enabled=true;bool Enabled(){return enabled;}std::array<float,2> Jitter(){return{.375f,-.25f};}} up;
struct Camera {unsigned depth=7;unsigned Depth(){return depth;}} camera;
auto* upscaler=&up;auto* camera_motion=&camera;
struct {unsigned first;} db_desc;
struct Count{unsigned n=1;unsigned NumInstances(){return n;}};
struct {unsigned num_indices{};Count num_instances;bool screen_space{};bool IsClipDisabled(){return screen_space;}} regs;
struct FetchShader {bool empty;bool Empty()const{return empty;}};
struct Pipeline{bool attributes=true;FetchShader GetFetchShader(){return {!attributes};}} gpu_pipeline;
auto* pipeline=&gpu_pipeline;
std::array<float,2> draw_jitter;bool gbuffer_draw;
void Select(){
'''
main=r'''}
int main(){
 db_desc.first=7;gbuffer_draw=true;
 for(unsigned count:{3u,4u,6u,12u}){regs.num_indices=count;Select();assert(draw_jitter==up.Jitter());}
 regs.num_indices=6;gpu_pipeline.attributes=false;Select();assert((draw_jitter==std::array<float,2>{}));
 gpu_pipeline.attributes=true;regs.screen_space=true;Select();assert((draw_jitter==std::array<float,2>{}));regs.screen_space=false;
 gbuffer_draw=false;regs.num_indices=6;Select();assert((draw_jitter==std::array<float,2>{}));
 regs.num_indices=36;Select();assert(draw_jitter==up.Jitter());
 regs.num_indices=6;regs.num_instances.n=2;Select();assert(draw_jitter==up.Jitter());
 db_desc.first=8;Select();assert((draw_jitter==std::array<float,2>{}));
 db_desc.first=7;up.enabled=false;Select();assert((draw_jitter==std::array<float,2>{}));
 std::puts("PASS: production jitter policy includes single G-buffer triangles/quads, preserves full-screen/UI exclusion and instanced geometry.");
}
'''
with tempfile.TemporaryDirectory(prefix='bb-jitter-draw-') as d:
 p=Path(d);(p/'test.cpp').write_text(prefix+body+main)
 subprocess.run(shlex.split(os.environ.get('CXX','g++'))+['-std=c++20','-O2',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
