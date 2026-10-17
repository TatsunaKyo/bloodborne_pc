# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Prepare an opt-in provider. Only the renderer loads it, after its own GPU check."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.request
import zipfile

URL = 'https://github.com/SilyNoMeta/rtx-encore/releases/download/v1.0.0-rc.3/RTX-Encore-v1.0.0-rc.3.zip'
ARCHIVE_SHA = 'a6b7ef387184115006e0b04e5f691e1c9733f1a81950f65018a7030255ba30f7'
ARCHIVE_SIZE = 120892421
DLL_SHA = 'b6a367fd4103f36290ccf464f50486ab7283264b8c0c1558a197615cf01b13b0'
DLL_SIZE = 93079552


def preferences(config):
    values = {}
    path = Path(config).with_suffix('.menu.ini')
    if path.is_file():
        for line in path.read_text(encoding='utf-8').splitlines():
            if '=' in line and not line.lstrip().startswith(('#', ';')):
                key, value = line.split('=', 1)
                values[key.strip()] = value.strip()
    return values


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def ensure_config(folder):
    config = folder / 'rtx-encore.jsonc'
    if not config.exists():
        atomic_write(config, (json.dumps({
            'frameGeneration': {'mode': 'game'},
            # This integration opts into FG only. Neural Rendering is a separate
            # Encore feature and its nvngx_dlssnr.dll is neither needed nor installed.
            'neuralRendering': {'nrEnabled': False},
            'nativeMenuFeatures': {'reflexFrameLimit': 0, 'vsyncOff': False},
            'overlay': {'showOverlay': False},
            'keyboardShortcuts': {'disableKeybinds': True},
            'menuState': {'menuFirstLaunchShown': True},
        }, indent=2) + '\n').encode())



def download_provider(folder, opener=urllib.request.urlopen):
    ensure_config(folder)
    target = folder / 'rtx-encore.asi'
    if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == DLL_SHA:
        return
    with tempfile.TemporaryFile() as stream:
        with opener(URL, timeout=60) as response:
            digest = hashlib.sha256(); total = 0
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > ARCHIVE_SIZE:
                    raise ValueError('provider archive exceeds the pinned size')
                digest.update(chunk); stream.write(chunk)
        if total != ARCHIVE_SIZE or digest.hexdigest() != ARCHIVE_SHA:
            raise ValueError('provider archive checksum mismatch')
        stream.seek(0)
        with zipfile.ZipFile(stream) as archive:
            info = archive.getinfo('alternative-proxies/rtx-encore.asi')
            if info.file_size != DLL_SIZE:
                raise ValueError('provider DLL size mismatch')
            data = archive.read(info)
            if hashlib.sha256(data).hexdigest() != DLL_SHA:
                raise ValueError('provider DLL checksum mismatch')
            # Extract only the plugin and its notices: no proxy, manager, NR assets or second ZIP.
            notices = archive.read('THIRD-PARTY-NOTICES.md')
            atomic_write(folder / 'THIRD-PARTY-NOTICES.md', notices)
            atomic_write(target, data)


def configure_launch(config, probe, env, *, windows=None, run=subprocess.run, download=download_provider):
    values = preferences(config)
    if values.get('nvidia_fg_mod') != '1' or values.get('frame_generation') != 'nvidia':
        return 'DLSSG mod: off; original NVIDIA runtime.'
    if not (os.name == 'nt' if windows is None else windows):
        return 'DLSSG mod: Windows only; original path retained.'
    probe = Path(probe)
    try:
        checked = run([str(probe.parent / 'bb-gpu-capabilities.exe'), '--dlssg-mod'],
                      env=env, capture_output=True, text=True, timeout=30,
                      creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if checked.returncode or checked.stdout.strip() != '1':
            return 'DLSSG mod: selected GPU is not verified as RTX 20/30; nothing downloaded or loaded.'
        folder = probe.parent / 'mods' / 'dlssg'
        if (folder / 'dlssg_sm86.dll').is_file():
            return 'DLSSG mod: using the explicitly supplied dlssg_sm86.dll; Vulkan compatibility is provider-dependent.'
        print('DLSSG mod: preparing RTX Encore for the selected RTX 20/30. Vulkan support is experimental.', flush=True)
        download(folder)
        return 'DLSSG mod: provider ready; native GPU gate and actual Streamline support checks still apply.'
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, subprocess.SubprocessError) as error:
        return f'DLSSG mod unavailable: {error}. Original NVIDIA path retained.'
