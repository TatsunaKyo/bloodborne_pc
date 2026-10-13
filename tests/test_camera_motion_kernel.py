# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Execute the production GLSL motion body with float32 GLM vectors on the CPU."""
import argparse
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
vec4 texelFetch(const Texture& image,ivec2 p,int) { return image.pixels.at(p.y*W+p.x); }
void imageStore(Texture& image,ivec2 p,vec4 value) { image.pixels.at(p.y*W+p.x)=value; }
@BODY@
int main() {
    int cases=0;
    const auto run=[&](const char* label,float depth,float stored_depth,float state,
                       vec2 object_motion,vec2 expected,float previous_z=1.f) {
        depth_tex.pixels.fill(vec4(depth,0,0,0));
        object_tex.pixels.fill(vec4(object_motion,state,stored_depth));
        reproject[0]=vec4(1,0,0,0);reproject[1]=vec4(0,1,0,0);
        reproject[2]=vec4(0,0,previous_z,0);
        proj=prev_proj=vec4(1,1,1,-.05f);jitter=vec2(0);mode=1;
        for(int y=0;y<H;++y)for(int x=0;x<W;++x) {
            gl_GlobalInvocationID=uvec3(x,y,0);kernel();
            const auto result=motion_img.pixels[y*W+x];
            assert(std::isfinite(result.x)&&std::isfinite(result.y));
            if(x==4&&y==3)assert(length(vec2(result)-expected)<.002f);
            if(state < -.99f && std::abs(depth-stored_depth) < glm::max(2e-7f,(1.f-depth)*.01f))
                assert(result.x< -float(x)-.5f&&result.y< -float(y)-.5f);
        }
        ++cases;std::printf("Production motion GLSL: %s PASS\n",label);
    };
    const float distant=.999995f;
    run("matching history retained",distant,distant,1,vec2(2,0),vec2(2,0));
    run("new geometry rejects unrelated history",distant,distant,-1,vec2(2,0),vec2(-5.625f,-4.375f));
    run("covered new geometry retains foreground",distant,.9999f,-1,vec2(2,0),vec2(0));
    run("untracked surface keeps camera fallback",distant,distant,0,vec2(2,0),vec2(0));
    run("stale distant vector remains rejected",distant,.9999f,1,vec2(2,0),vec2(0));
    run("nonfinite object vector stays finite",distant,distant,1,vec2(std::numeric_limits<float>::quiet_NaN(),0),vec2(0));
    run("FP16 overflow vector stays finite",distant,distant,1,vec2(100000,0),vec2(0));
    run("behind-camera tracked point rejects history",.5f,.5f,-1,vec2(0),vec2(-5.625f,-4.375f),-1);
    // Rasterizer extent guards must not write beyond the last partial workgroup.
    gl_GlobalInvocationID=uvec3(W,H,0);kernel();
    std::printf("PASS: %d production GLSL cases, 63 pixels each; partial-workgroup guard. CPU float32 execution, not a GPU gameplay run.\n",cases);
}
'''.replace('@BODY@', body)
    with tempfile.TemporaryDirectory(prefix='workshop-motion-kernel-') as directory:
        source = Path(directory) / 'kernel.cpp'; source.write_text(fixture)
        binary = Path(directory) / 'kernel'
        command = ['g++', '-std=c++23', '-O1', '-UNDEBUG']
        if args.glm_include: command += ['-I' + str(args.glm_include)]
        subprocess.run([*command, str(source), '-o', str(binary)], check=True, cwd=ROOT)
        subprocess.run([str(binary)], check=True, timeout=30)


if __name__ == '__main__': main()
