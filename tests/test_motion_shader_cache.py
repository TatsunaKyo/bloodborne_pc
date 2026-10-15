# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Build the actual vertex-motion emitter and optionally execute its cached SPIR-V.

Vulkan execution validates buffer addressing. A software Vulkan result is not
an NVIDIA DLSS/FG or target-game timing result.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = 'a93ce851256ce41acc2953539a2ada3bd12de7f8'
EMITTER = 'gpu/shadps4/shader_recompiler/backend/spirv/emit_spirv_special.cpp'
RUNTIME = 'gpu/shadps4/shader_recompiler/runtime_info.h'


def read(path, revision=None):
    return (subprocess.check_output(['git','show',revision+':'+path],cwd=ROOT,text=True)
            if revision else (ROOT/path).read_text())


def run(folder, args):
    folder.mkdir(parents=True,exist_ok=True)
    sirit = ROOT/'gpu/third_party/sirit'
    includes = ['-I'+str(ROOT/'gpu/shadps4'),'-I'+str(sirit/'include'),
                '-I'+str(sirit/'externals/SPIRV-Headers/include'),'-I'+str(sirit/'src'),
                '-I'+str(args.vulkan_include.resolve())]
    objects=[]
    def compile_object(source):
        obj=folder/(source.stem+'.o')
        if not obj.exists() or obj.stat().st_mtime_ns < source.stat().st_mtime_ns:
            subprocess.run([args.compiler,'-std=c++20','-O1',*includes,'-c',str(source),'-o',str(obj)],check=True)
        return obj
    with ThreadPoolExecutor(max_workers=4) as pool:
        objects=list(pool.map(compile_object,sorted((sirit/'src').rglob('*.cpp'))))
    template=(ROOT/'tests/test_motion_shader_cache.cpp').read_text()
    for name,revision in [('revision41',BASE),('current',None)]:
        emitter=read(EMITTER,revision);start=emitter.index('static void EmitVertexMotion(')
        emitter=emitter[start:emitter.index('// Screen-space motion',start)]
        declaration=read(RUNTIME,revision);start=declaration.index('struct MotionVectors {')
        declaration=declaration[start:declaration.index('\n};',start)+3]
        cpp=folder/(name+'.cpp');exe=folder/name
        cpp.write_text(template.replace('@MOTION_DECLARATION@',declaration).replace('@MOTION_EMITTER@',emitter))
        subprocess.run([args.compiler,'-std=c++20','-O1','-UNDEBUG','-DCURRENT='+str(int(not revision)),
                        *includes,str(cpp),*map(str,objects),'-Wl,-l:libvulkan.so.1','-o',str(exe)],check=True)
        subprocess.run([str(exe),str(folder),*(['--vulkan'] if args.vulkan and not revision else [])],check=True,timeout=60)
    if args.validator:
        for name in ('portable.spv','linked.spv'):
            subprocess.run([str(args.validator.resolve()),'--target-env','vulkan1.2',str(folder/name)],check=True)
        print('PASS: portable and linked production vertex-motion modules validate for Vulkan 1.2.',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler',default='g++')
    parser.add_argument('--vulkan',action='store_true')
    parser.add_argument('--vulkan-include',type=Path,default=ROOT/'out/test-headers')
    parser.add_argument('--validator',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.output:run(args.output.resolve(),args)
    else:
        with tempfile.TemporaryDirectory(prefix='motion-cache-') as temp:run(Path(temp),args)


if __name__ == '__main__':
    main()
