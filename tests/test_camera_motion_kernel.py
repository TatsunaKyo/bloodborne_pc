# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Execute the production GLSL motion body with float32 GLM vectors on the CPU."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--glm-include', type=Path)
    args = parser.parse_args()
    shader = (ROOT / 'gpu/shadps4/video_core/host_shaders/camera_motion.comp').read_text()
    body = shader[shader.index('void main()'):].replace('void main()', 'void kernel()')
    body = re.sub(r'\.(xy|rg)\b', r'.\1()', body)
    body = re.sub(r'\b(\d+\.\d*(?:[eE][+-]?\d+)?|\d+[eE][+-]?\d+)\b', r'\1f', body)
    fixture = r'''
#define GLM_FORCE_SWIZZLE
#include <glm/glm.hpp>
#include <glm/common.hpp>
#include <array>
#include <cassert>
#include <cmath>
#include <cstdio>
#include <limits>
using namespace glm;
constexpr int W=9,H=7;
struct Texture { std::array<vec4,W*H> pixels; };
Texture depth_tex, object_tex, motion_img;
uvec3 gl_GlobalInvocationID;
vec4 reproject[3],proj,prev_proj;
vec2 size(W,H),jitter,previous_jitter;
unsigned mode;
bool captured=false;
vec4 texelFetch(const Texture& image,ivec2 p,int) { return image.pixels.at(captured ? 0 : p.y*W+p.x); }
void imageStore(Texture& image,ivec2 p,vec4 value) { image.pixels.at(captured ? 0 : p.y*W+p.x)=value; }
@BODY@
int main() {
    int cases=0;

    const auto run=[&](const char* label,float depth,float stored_depth,float state,
                       vec2 object_motion,vec2 expected,float previous_z=1.f,
                       float camera_x=0.f) {
        depth_tex.pixels.fill(vec4(depth,0,0,0));
        object_tex.pixels.fill(vec4(object_motion,state,stored_depth));
        reproject[0]=vec4(1,0,camera_x,0);reproject[1]=vec4(0,1,0,0);
        reproject[2]=vec4(0,0,previous_z,0);
        proj=prev_proj=vec4(1,1,1,-.05f);jitter=vec2(0);mode=1;
        for(int y=0;y<H;++y)for(int x=0;x<W;++x) {
            gl_GlobalInvocationID=uvec3(x,y,0);kernel();
            const auto result=motion_img.pixels[y*W+x];
            assert(std::isfinite(result.x)&&std::isfinite(result.y));
            if(x==4&&y==3)assert(length(vec2(result)-expected)<.002f);
        }
        ++cases;std::printf("Production motion GLSL: %s PASS\n",label);
    };
    const float distant=.999995f;
    run("matching history retained",distant,distant,1,vec2(2,0),vec2(2,0));
    run("missing history retains camera fallback",distant,distant,0,vec2(2,0),vec2(0));
    run("covered geometry retains foreground",distant,.9999f,0,vec2(2,0),vec2(0));
    run("obsolete negative marker cannot create offscreen motion",distant,distant,-1,vec2(2,0),vec2(0));
    run("stale distant vector remains rejected",distant,.9999f,1,vec2(2,0),vec2(0));
    run("nonfinite object vector stays finite",distant,distant,1,vec2(std::numeric_limits<float>::quiet_NaN(),0),vec2(0));
    run("FP16 overflow vector stays finite",distant,distant,1,vec2(100000,0),vec2(0));
    run("behind-camera point rejects history",.5f,.5f,0,vec2(0),vec2(-5.625f,-4.375f),-1);
    run("verified world keeps small wind motion",distant,distant,2,vec2(.2f,.1f),vec2(.2f,.1f));
    run("verified world rejects whole-screen history jump",distant,distant,2,vec2(8,4),vec2(0));
    run("actor motion keeps large legitimate displacement",distant,distant,1,vec2(8,4),vec2(8,4));
    run("verified world keeps large matching camera motion",distant,distant,2,vec2(8.2f,.1f),vec2(8.2f,.1f),1.f,16.f/9.f);
    run("verified world rejects stale motion during camera movement",distant,distant,2,vec2(-8,4),vec2(8,0),1.f,16.f/9.f);
    @CAPTURE_CASES@
    captured=false;size=vec2(W,H);
    // Rasterizer extent guards must not write beyond the last partial workgroup.
    gl_GlobalInvocationID=uvec3(W,H,0);kernel();
    std::printf("PASS: %d production GLSL cases: 13 grids of 63 pixels and 8 captured numeric probes; partial-workgroup guard. CPU float32 execution.\n",cases);
}
'''.replace('@BODY@', body)
    captures=json.loads((ROOT/'tests/fixtures/static-world-motion.json').read_text())['samples']
    checks=[]
    for sample in captures:
        x,y=sample['pixel'];w,h=sample['size'];ox,oy,state,od=sample['object'];depth=sample['depth']
        checks.append(f'''
    captured=true;size=vec2({w},{h});gl_GlobalInvocationID=uvec3({x},{y},0);
    reproject[0]=vec4(1,0,0,0);reproject[1]=vec4(0,1,0,0);reproject[2]=vec4(0,0,1,0);
    depth_tex.pixels[0]=vec4({depth:.9g}f,0,0,0);
    object_tex.pixels[0]=vec4({ox:.9g}f,{oy:.9g}f,2.f,{od:.9g}f);
    kernel();assert(length(vec2(motion_img.pixels[0]))<.002f);
    object_tex.pixels[0].z=1.f;kernel();
    assert(length(vec2(motion_img.pixels[0])-vec2({ox:.9g}f,{oy:.9g}f))<.002f);++cases;
''')
    fixture=fixture.replace('@CAPTURE_CASES@',''.join(checks))
    with tempfile.TemporaryDirectory(prefix='workshop-motion-kernel-') as directory:
        source = Path(directory) / 'kernel.cpp'; source.write_text(fixture)
        binary = Path(directory) / 'kernel'
        command = ['g++', '-std=c++23', '-O1', '-UNDEBUG']
        if args.glm_include: command += ['-I' + str(args.glm_include)]
        subprocess.run([*command, str(source), '-o', str(binary)], check=True, cwd=ROOT)
        subprocess.run([str(binary)], check=True, timeout=30)


if __name__ == '__main__': main()
