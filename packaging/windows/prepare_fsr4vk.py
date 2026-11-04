#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Prepare the pinned fsr4vk provider and corresponding source for Windows packages."""
import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('package_fsr4vk_fetch', ROOT/'scripts/fetch_fsr4vk.py')
provider = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provider)

SOURCE_NAME = 'fsr4vk-v0.4.3-amdfix-src.zip'
SOURCE_SIZE = 61150462
SOURCE_SHA256 = '23a05d16ca6116760bff4cd6dbf667bf38319eb20d0107c781e9d65a9b065c90'


def prepare_source(cache: Path) -> Path:
    source = cache/SOURCE_NAME
    if provider.verified(source, SOURCE_SIZE, SOURCE_SHA256):
        return source
    cache.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        request = urllib.request.Request(provider.SOURCE_ZIP_URL, headers={'User-Agent': 'bbport-package-fsr4vk'})
        with urllib.request.urlopen(request, timeout=60) as response:
            with tempfile.NamedTemporaryFile(dir=cache, suffix='.part', delete=False) as stream:
                temporary = Path(stream.name)
                shutil.copyfileobj(response, stream)
        if not provider.verified(temporary, SOURCE_SIZE, SOURCE_SHA256):
            raise ValueError('fsr4vk source archive size or SHA-256 mismatch')
        os.replace(temporary, source)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
    return source


def prepare(cache: Path) -> Path:
    # A package is only ready when the exact corresponding source is available too.
    prepare_source(cache)
    target = cache/'provider'
    provider.fetch(target)
    if not provider.files_ok(target):
        raise ValueError('fsr4vk provider files failed verification')
    (target/'SOURCE.txt').write_text(
        provider.SOURCE_NOTE + '\nCorresponding source accompanies the Windows package as '
        + SOURCE_NAME + '.\n', encoding='utf-8')
    return target


def stage_provider(target: Path, destination: Path) -> None:
    # Never ship cache leftovers, interrupted downloads or locally added files.
    names = [name for _, name, _, _ in provider.FILES] + ['SOURCE.txt']
    names += [name for name in provider.EXTRA if (target/name).is_file()]
    for name in names:
        output = destination/name
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(target/name, output)
    if not provider.files_ok(destination):
        raise ValueError('staged fsr4vk files failed verification')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dir', type=Path, default=ROOT/'out/fsr4vk')
    parser.add_argument('--stage', type=Path, help='copy only provider files and notices into this package folder')
    args = parser.parse_args(argv)
    try:
        target = prepare(args.dir)
        if args.stage:
            stage_provider(target, args.stage)
    except (OSError, ValueError, provider.FetchError) as error:
        parser.exit(1, f'prepare_fsr4vk: {error}\n')
    print(f'fsr4vk {provider.RELEASE}: provider, licenses and corresponding source verified in {target.parent}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
