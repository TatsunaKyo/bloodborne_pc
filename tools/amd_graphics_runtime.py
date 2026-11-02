# SPDX-License-Identifier: GPL-2.0-or-later
"""Stage the verified AMD runtime closure and its corresponding source."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def install(stage, repo):
    stage, repo = Path(stage), Path(repo)
    scripts = repo / 'packaging/windows'
    cache = repo / 'out/fsr411-dx12'
    # These tools validate both the SDK archive and every extracted DLL.
    for name in ('fetch_fsr411_dx12.py', 'fetch_fg401_dx12.py'):
        subprocess.run([sys.executable, str(scripts / name), '--dir', str(cache)], check=True)
    sdk = load(scripts / 'fetch_fsr411_dx12.py', 'package_amd_sdk')
    files = {sdk.DLL_NAME: (sdk.DLL_SIZE, sdk.DLL_SHA256)}
    # Read the FG tool's pinned table without importing it under another SDK context.
    import ast
    tree = ast.parse((scripts / 'fetch_fg401_dx12.py').read_text())
    files.update(next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == 'FILES' for t in n.targets)))
    for name, (size, digest) in files.items():
        if not sdk.verified(cache / name, size, digest):
            raise ValueError(f'AMD runtime verification failed: {name}')
        shutil.copy2(cache / name, stage / 'bin' / name)
    provider = load(scripts / 'prepare_fsr4vk.py', 'package_fsr4vk')
    target = provider.prepare(repo / 'out/fsr4vk')
    shutil.rmtree(stage / 'fsr4vk', ignore_errors=True)
    provider.stage_provider(target, stage / 'fsr4vk')
    source = stage / 'source/third_party'
    source.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target.parent / provider.SOURCE_NAME, source / provider.SOURCE_NAME)
    for name in ('Cinzel-OFL.txt', 'Inter-LICENSE.txt'):
        shutil.copy2(repo / 'launcher/assets/fonts' / name, stage / 'licenses' / name)
    return {'sdk_archive_sha256': sdk.ARCHIVE_SHA256,
            'files': {f'bin/{name}': digest for name, (_, digest) in files.items()},
            'fsr4vk_source_sha256': provider.SOURCE_SHA256}
