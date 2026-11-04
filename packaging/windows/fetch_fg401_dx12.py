#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Extract the pinned AMD ML-FG and Agility runtime from SDK v2.3.0."""
import argparse
import hashlib
import os
from pathlib import Path
import tempfile
import zipfile

import fetch_fsr411_dx12 as sdk

FILES = {
    'amd_fidelityfx_framegeneration_dx12.dll': (40085776, '02297beedd285e822d3a64f314cf00faf378dcec0edc47ff0c4dd71b3a8c2f18'),
    'amd_fidelityfx_loader_dx12.dll': (26376, 'e2d85aa05a9bd9ed8b38935fdf5199372cca6f74c12015143bb6f945ee1608aa'),
    'D3D12Core.dll': (4533320, '83820d5eed8a35ad4ba1169d6b66545d3638225fc3f640702432360a38143bc5'),
}
MEMBER = 'Samples/Upscalers/FidelityFX_FSR/dx12/x64/Release/'

def verified(target):
    return all(sdk.verified(target/name, size, digest) for name, (size, digest) in FILES.items())

def prepare(target):
    if verified(target):
        return
    # Share the verified SDK archive with the FSR 4.1.1 packaging step; fetched again
    # when only its upscaler DLL is cached.
    with zipfile.ZipFile(sdk.fetch_archive(target)) as package:
        for name, (size, digest) in FILES.items():
            member = MEMBER+name
            if package.getinfo(member).file_size != size:
                raise ValueError(f'{name}: unexpected SDK member size')
            data = package.read(member)
            if hashlib.sha256(data).hexdigest() != digest:
                raise ValueError(f'{name}: unexpected SDK member SHA-256')
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=target, suffix='.part', delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(data)
                os.replace(temporary, target/name)
            finally:
                if temporary:
                    temporary.unlink(missing_ok=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dir', type=Path, default=sdk.ROOT/'out/fsr411-dx12')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.check:
        return 0 if verified(args.dir) else 1
    try:
        prepare(args.dir)
        print('AMD ML-FG 4.0.1 and D3D12 Agility 616 verified')
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        parser.exit(1, f'fetch_fg401_dx12: {error}\n')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
