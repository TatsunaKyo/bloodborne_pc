# SPDX-License-Identifier: GPL-2.0-or-later
# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
"""Compare production camera motion against independently projected static vertices.

The R42 control retains its actual camera decoder (fixed viewport convention).
Current code must agree for all four viewport signs, vertical travel and pitch.
Optional native Vulkan executes the production GLSL with the same inputs.
"""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = '2fe3a67fc3c2930352bb88af57f881b9b0829494'


def run(folder, args):
    folder.mkdir(parents=True, exist_ok=True)
    shader = (ROOT/'gpu/shadps4/video_core/host_shaders/camera_motion.comp').read_text()
    body = shader[shader.index('void main()'):].replace('void main()', 'void kernel()')
    body = re.sub(r'\.(xy|rg)\b', r'.\1()', body)
    body = re.sub(r'\b(\d+\.\d*(?:[eE][+-]?\d+)?|\d+[eE][+-]?\d+)\b', r'\1f', body)
    helper = (ROOT/'tests/test_motion_shader_cache.cpp').read_text()
    helper = helper[helper.index('void Check('):helper.index('void Write(')]
    helper = helper.replace('VK_BUFFER_USAGE_STORAGE_BUFFER_BIT;',
                            'VK_BUFFER_USAGE_STORAGE_BUFFER_BIT|VK_BUFFER_USAGE_TRANSFER_SRC_BIT|VK_BUFFER_USAGE_TRANSFER_DST_BIT;')
    template = (ROOT/'tests/test_camera_viewport.cpp').read_text()
    header_path = 'gpu/shadps4/video_core/renderer_vulkan/temporal_history.h'
    for name, control in [('r42', True), ('current', False)]:
        header = (subprocess.check_output(['git','show',BASE+':'+header_path],cwd=ROOT,text=True)
                  if control else (ROOT/header_path).read_text())
        (folder/'camera.h').write_text(header)
        source = folder/(name+'.cpp')
        source.write_text(template.replace('@KERNEL@', body).replace('@GPU_HELPERS@', helper))
        executable = folder/name
        subprocess.run([args.compiler,'-std=c++20','-O1','-UNDEBUG','-DCONTROL='+str(int(control)),
                        '-I'+str(args.glm_include.resolve()),'-I'+str(args.vulkan_include.resolve()),
                        str(source),'-Wl,-l:libvulkan.so.1','-o',str(executable)],check=True,cwd=ROOT)
        commands = [str(executable)]
        if args.vulkan and not control:
            spv = folder/'camera.spv'; glsl = folder/'camera.comp'; glsl.write_text(shader)
            subprocess.run([str(args.glslang.resolve()),'-V','--target-env','vulkan1.2',str(glsl),'-o',str(spv)],check=True)
            if args.validator:subprocess.run([str(args.validator.resolve()),'--target-env','vulkan1.2',str(spv)],check=True)
            commands.append(str(spv))
        subprocess.run(commands,check=True,timeout=60)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler',default='g++')
    parser.add_argument('--glm-include',type=Path,required=True)
    parser.add_argument('--vulkan-include',type=Path,default=ROOT/'out/test-headers')
    parser.add_argument('--vulkan',action='store_true')
    parser.add_argument('--glslang',type=Path)
    parser.add_argument('--validator',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.vulkan and not args.glslang:parser.error('--vulkan requires --glslang')
    if args.output:run(args.output.resolve(),args)
    else:
        with tempfile.TemporaryDirectory(prefix='camera-viewport-') as directory:run(Path(directory),args)


if __name__=='__main__':main()
