# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Compare production cache hot paths with R35, including byte compatibility."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = 'a3df0604a808a4bb9fb52c03e3791ae956ba0e0f'
SERDES = 'gpu/shadps4/common/serdes.h'
PIPELINE = 'gpu/shadps4/video_core/renderer_vulkan/vk_pipeline_cache.cpp'


def patch_lookup(source):
    start = source.index('std::optional<std::vector<u32>> PipelineCache::GetShaderPatch(')
    end = source.index('\n}', start) + 2
    return source[start:end]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--prepare', type=Path)
    mode.add_argument('--verify-existing', type=Path)
    parser.add_argument('--compiler', default='g++')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='workshop-cache-hotpaths-') as tmp:
        folder = (args.prepare or args.verify_existing).resolve() if (args.prepare or args.verify_existing) else Path(tmp)
        folder.mkdir(parents=True, exist_ok=True)
        for name, old in [('revision35', True), ('current', False)]:
            child = folder / name
            child.mkdir(exist_ok=True)
            if args.verify_existing:
                continue
            def read(path):
                return (subprocess.check_output(['git', 'show', BASE + ':' + path], cwd=ROOT, text=True)
                        if old else (ROOT / path).read_text())
            (child / 'serdes.h').write_text(read(SERDES))
            (child / 'production_patch_lookup.inc').write_text(patch_lookup(read(PIPELINE)))
            (child / 'serialization.cpp').write_text(
                f'#define FAST_PATH {int(not old)}\n#define TEST_SERDES_HEADER "serdes.h"\n' +
                (ROOT / 'tests/test_cache_serialization.cpp').read_text())
            (child / 'patch-lookup.cpp').write_text(f'#define CONTROL {int(old)}\n' +
                (ROOT / 'tests/test_shader_patch_lookup.cpp').read_text())
            if args.prepare:
                continue
            for target in ['serialization', 'patch-lookup']:
                subprocess.run([args.compiler, '-std=c++20', '-O1', '-Wall', '-Wextra', '-Werror', '-UNDEBUG',
                                '-I' + str(child), '-I' + str(ROOT / 'gpu/shadps4'),
                                str(child / (target + '.cpp')), '-o', str(child / target)], check=True)
        if args.prepare:
            return
        suffix = '.exe' if os.name == 'nt' else ''
        for name, old in [('revision35', True), ('current', False)]:
            child = folder / name
            subprocess.run([str(child / ('serialization' + suffix)), 'write', str(child / 'cache.bin')], check=True, timeout=20)
            result = subprocess.run([str(child / ('patch-lookup' + suffix)), str(child / 'lookup')], timeout=20)
            if result.returncode != (7 if old else 0):
                raise RuntimeError(f'{name} patch lookup: unexpected exit {result.returncode}')
        old, new = folder / 'revision35', folder / 'current'
        if (old / 'cache.bin').read_bytes() != (new / 'cache.bin').read_bytes():
            raise AssertionError('Bulk serialization changed the on-disk shader cache format')
        for binary in [old / ('serialization' + suffix), new / ('serialization' + suffix)]:
            for data in [old / 'cache.bin', new / 'cache.bin']:
                subprocess.run([str(binary), 'read', str(data)], check=True, timeout=20)
        print('PASS: old/new cache bytes match exactly; both readers cross-read both files; flat table writes use one copy and reads one resize instead of per-element growth.')


if __name__ == '__main__':
    main()
