# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Exercise production cache IO/serialization with isolated host services and driver responses."""
import argparse
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler',default='g++')
    parser.add_argument('--binary',type=Path)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='crowned-cache-') as temp:
        temp=Path(temp);binary=args.binary.resolve() if args.binary else temp/'cache-test'
        if not args.binary:
            (temp/'miniz_export.h').write_text('#define MINIZ_EXPORT\n')
            subprocess.run([args.compiler,'-std=c++20','-O1','-pthread','-Wall','-Wextra','-Werror',
                            '-Itests/cache_stubs','-Igpu/shadps4','-Igpu/third_party/miniz','-I'+str(temp),
                            'tests/test_shader_cache.cpp','gpu/shadps4/video_core/cache_storage.cpp',
                            'gpu/shadps4/video_core/renderer_vulkan/vk_shader_util.cpp','-o',str(binary)],cwd=ROOT,check=True)
        subprocess.run([str(binary),str(temp)],cwd=ROOT,check=True,timeout=60)
if __name__=='__main__':main()
