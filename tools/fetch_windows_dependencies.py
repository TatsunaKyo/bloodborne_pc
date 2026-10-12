# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Download checksum-pinned MSYS2 packages and the unchanged vendor runtime bundle."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT=Path(__file__).resolve().parents[1]


def download(url,target,sha):
    if target.is_file() and hashlib.file_digest(target.open('rb'),'sha256').hexdigest()==sha:return
    temporary=target.with_suffix(target.suffix+'.part')
    with urllib.request.urlopen(url,timeout=90) as response,temporary.open('wb') as out:
        while chunk:=response.read(1024*1024):out.write(chunk)
    if hashlib.file_digest(temporary.open('rb'),'sha256').hexdigest()!=sha:
        temporary.unlink();raise ValueError('Dependency checksum mismatch: '+target.name)
    temporary.replace(target)


def main():
    dest=ROOT/'out/dependencies';dest.mkdir(parents=True,exist_ok=True)
    packages=json.loads((ROOT/'packaging/windows/msys2-packages.lock.json').read_text())
    requests=[('https://repo.msys2.org/mingw/clang64/'+p['filename'],dest/p['filename'],p['sha256']) for p in packages.values()]
    runtime=json.loads((ROOT/'packaging/windows/runtime-baseline.lock.json').read_text())
    requests.append((runtime['url'],dest/'runtime-baseline.zip',runtime['sha256']))
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda args:download(*args),requests))
    print(f'PASS: {len(packages)} pinned packages and vendor baseline verified.')


if __name__=='__main__':main()
