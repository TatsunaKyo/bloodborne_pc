# SPDX-License-Identifier: GPL-2.0-or-later
"""Install the pinned native ABI2 bridge without replacing the original ABI1 SR bridge."""
import hashlib
import io
import json
from pathlib import Path
import shutil
import urllib.request
import zipfile


def install(stage, repo):
    stage,repo=Path(stage),Path(repo)
    lock=json.loads((repo/'packaging/windows/native-fg-runtime.lock.json').read_text())
    original=lock['default_sr_bridge'];native=lock['native_fg_bridge'];feature=lock['native_fg_feature']
    def matches(path,sha):
        return path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==sha
    if not matches(stage/original['file'],original['sha256']):
        raise ValueError('The original DLSS SR bridge does not match the pinned ABI1 runtime')
    target=stage/native['file']
    if not matches(target,native['sha256']):
        with urllib.request.urlopen(native['release_url'],timeout=60) as response:data=response.read()
        if hashlib.sha256(data).hexdigest()!=native['release_sha256']:
            raise ValueError('Native DLSS bridge release checksum mismatch')
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            name=next(n for n in archive.namelist() if n.replace('\\','/')==native['original_file'])
            payload=archive.read(name)
        if hashlib.sha256(payload).hexdigest()!=native['sha256']:
            raise ValueError('Native DLSS bridge checksum mismatch')
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(payload)
    source=stage/feature['same_bytes_as']
    if not matches(source,feature['sha256']):raise ValueError('Original DLSSG feature checksum mismatch')
    shutil.copy2(source,stage/feature['file'])
    return lock
