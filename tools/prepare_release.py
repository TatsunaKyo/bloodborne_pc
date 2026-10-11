#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Prepare a GitHub release form for the exact rebuilt Windows ZIP."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode
import zipfile


def prepare(package: Path):
    with zipfile.ZipFile(package) as archive:
        candidates = [name for name in archive.namelist()
                      if name.count('/') == 1 and name.endswith('/BUILD-IDENTITY.json')]
        if len(candidates) != 1:
            raise ValueError('Expected one package identity at the archive root')
        identity = json.loads(archive.read(candidates[0]))
    if identity['version'] != '1.6-tatsunakyo.15':
        raise ValueError('This release text is for Revision 15')
    commit = identity['source_commit']
    if len(commit) != 40 or any(c not in '0123456789abcdef' for c in commit):
        raise ValueError('Invalid source commit')
    with package.open('rb') as stream:
        checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
    title = 'Bloodborne: The Crowned Workshop — TatsunaKyo Revision 15'
    notes_url = f'https://github.com/TatsunaKyo/bloodborne_pc/blob/{commit}/docs/releases/windows-v1.6-tatsunakyo.15.md'
    body = f'''Assets were still flashing in my Revision 14 tests, so I checked the rendering commands again. I found that vertex/index copies could still be queued when the game replaced their source constants. This revision completes those reads before the replacement, gives the launcher the workshop's full identity and brings the roadmap up to date.

- **Rendering:** complete the queued geometry reads before ConstRam writes. The regression compiles the actual command branch: 2,048 corrupted snapshots with the old behavior, zero with the correction across 3,072 cases. The constant ring, threaded renderer, upscalers and FG stay available.
- **Launcher:** the original cover gives way to my workshop painting, live lettering and TK emblem. Slate panels, brass accents, active navigation, settings headings and the Play button carry the same design. The compact hero and conditional DLSS/XeSS/FG rows are checked at small sizes and high DPI.
- **Roadmap:** current implementation inventory, open gameplay bugs and a concrete release order, including Save Manager, input, ultrawide, HUD/FG work and all fourteen proposed cheats.

I rebuilt Bloodborne.exe and the native Windows components. The compiled launcher passed 180 layout checks and 84 real XeSS popup selections, along with settings/update, geometry-read and retained limiter/history checks.

My gameplay setup is Windows 11 with an RTX 5070 Ti. The flashing report stays open for the affected-scene comparison on this build. Firing with several cheats, sprint stamina and Echoes remain tracked in the guide.

Extract the complete **{package.name}** into a separate folder and keep your saves, mods and preferences. You need your own decrypted Bloodborne CUSA03173 1.09 dump; no game files are included.

[Full Revision 15 notes]({notes_url}) · [Development plan](https://github.com/TatsunaKyo/bloodborne_pc/blob/{commit}/docs/tatsunakyo-next.md)

Source commit: `{commit}`

ZIP SHA256: `{checksum}`

Maintained by TatsunaKyo, based on Super Medo's Windows port, bbport and shadPS4. Original credits and licenses are retained.
'''

    url = 'https://github.com/TatsunaKyo/bloodborne_pc/releases/new?' + urlencode({
        'tag': identity['release_tag'], 'target': commit, 'title': title, 'body': body})
    return {'title': title, 'body': body, 'url': url, 'source_commit': commit,
            'zip_sha256': checksum, 'release_tag': identity['release_tag']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('--output', type=Path, help='Write ready-to-use Markdown and JSON beside it')
    args = parser.parse_args()
    result = prepare(args.package)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text('# '+result['title']+'\n\n'+result['body']+'\n[Open the prepared publishing page]('+result['url']+')\n', encoding='utf-8')
        args.output.with_suffix('.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(result['url'])


if __name__ == '__main__':
    main()
