# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Compile the production WarmUp body with isolated cache/driver boundary fixtures."""
import argparse
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
def extract():
    text=(ROOT/'gpu/shadps4/video_core/renderer_vulkan/vk_pipeline_serialization.cpp').read_text()
    start=text.index('void PipelineCache::WarmUp() {');body=text.index('{',start);depth=1;end=body+1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--compiler',default='g++');p.add_argument('--prepare',type=Path);a=p.parse_args()
    with tempfile.TemporaryDirectory(prefix='crowned-warmup-') as temp:
        temp=a.prepare.resolve() if a.prepare else Path(temp);temp.mkdir(parents=True,exist_ok=True)
        (temp/'production_warmup.inc').write_text(extract())
        if a.prepare:return
        target=temp/'cache-warmup'
        subprocess.run([a.compiler,'-std=c++20','-O1','-Wall','-Wextra','-Werror','-Itests/cache_stubs','-Igpu/shadps4','-I'+str(temp),'tests/test_cache_warmup.cpp','-o',str(target)],cwd=ROOT,check=True)
        subprocess.run([str(target)],cwd=ROOT,check=True,timeout=30)
if __name__=='__main__':main()
