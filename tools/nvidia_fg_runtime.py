# SPDX-License-Identifier: GPL-2.0-or-later
"""Install the exact unmodified NVIDIA FG runtime qualified for preset C."""
import hashlib
import json
from pathlib import Path
import urllib.request


def install(stage, repo):
    lock = json.loads((Path(repo)/'packaging/windows/nvidia-fg-runtime.lock.json').read_text())
    target = Path(stage)/'bin/streamline/nvngx_dlssg.dll'
    data = target.read_bytes() if target.is_file() else b''
    if hashlib.sha256(data).hexdigest() != lock['sha256']:
        with urllib.request.urlopen(lock['url'], timeout=60) as response:
            data = response.read(lock['bytes']+1)
    if len(data) != lock['bytes'] or hashlib.sha256(data).hexdigest() != lock['sha256']:
        raise ValueError('NVIDIA FG runtime failed the pinned size/SHA256 check')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return lock
