# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Prepare the same pinned Vulkan/VMA declarations for Linux recording tests."""
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
from fetch_windows_dependencies import download

ROOT=Path(__file__).resolve().parents[1]


def main():
    lock=json.loads((ROOT/'packaging/windows/msys2-packages.lock.json').read_text())
    target=ROOT/'out/test-headers';target.mkdir(parents=True,exist_ok=True)
    dependencies=ROOT/'out/dependencies';dependencies.mkdir(parents=True,exist_ok=True)
    records={}
    for name in ('vulkan-headers','vulkan-memory-allocator'):
        package=lock['mingw-w64-clang-x86_64-'+name]
        path=dependencies/package['filename']
        download('https://repo.msys2.org/mingw/clang64/'+package['filename'],path,package['sha256'])
        data=subprocess.check_output(['zstd','-d','-c',str(path)])
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            for member in archive:
                parts=PurePosixPath(member.name).parts
                if not member.isfile() or parts[:2]!=('clang64','include'):continue
                relative=PurePosixPath(*parts[2:])
                if '..' in relative.parts or relative.is_absolute():raise ValueError('Unsafe header path')
                dest=target/relative;dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_bytes(archive.extractfile(member).read())
        records[name]=package
    for name in ('vulkan/vulkan.hpp','vk_video/vulkan_video_codecs_common.h','vma/vk_mem_alloc.h'):
        if not (target/name).is_file():raise ValueError('Missing pinned test header: '+name)
    (target/'provenance.json').write_text(json.dumps(records,indent=2)+'\n')
    print('PASS: checksum-pinned Vulkan and VMA test declarations prepared.')


if __name__=='__main__':main()
