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
    if identity['version'] != '1.6-tatsunakyo.14':
        raise ValueError('This release text is for Revision 14')
    commit = identity['source_commit']
    if len(commit) != 40 or any(c not in '0123456789abcdef' for c in commit):
        raise ValueError('Invalid source commit')
    with package.open('rb') as stream:
        checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
    title = 'Bloodborne: The Crowned Workshop — TatsunaKyo Revision 14'
    notes_url = f'https://github.com/TatsunaKyo/bloodborne_pc/blob/{commit}/docs/releases/windows-v1.6-tatsunakyo.14.md'
    body = f'''I tracked down why the FPS cap kept landing below the number I chose, and added another safeguard after assets were still flashing in Revision 13. I also brought the launcher sidebar into line with The Crowned Workshop and added feature overviews to the README.

- **FPS cap:** small Windows timer delays no longer accumulate from frame to frame. Real stalls still start a fresh interval, so queued frames do not rush through after a hitch. Real FPS and the optional FG-output cap stay separate.
- **Temporal data:** ambiguous repeated mesh instances fall back to camera motion instead of inheriting another object's positions. NVIDIA FG receives the explicit pinhole offset and render/output extents that were missing from the diagnostic log.
- **Launcher:** BLOODBORNE: THE CROWNED WORKSHOP, by TatsunaKyo, with the current version and credit to Super Medo's Windows port. The longer title fits the tested window sizes and DPI scales.
- **XeSS table:** input examples for 1080p, 1440p and 4K, using the renderer's even-pixel rounding.
- **README artwork:** eleven feature overviews, with editable SVGs and PNG exports in the same workshop style.

I rebuilt Bloodborne.exe and the native Windows components together. The compiled launcher passed 180 layout checks and 84 real XeSS popup selections, alongside native limiter/history, settings, ImGui, pause, XeSS and Anti-Lag adapter checks.

My gameplay PC is Windows 11 with an RTX 5070 Ti. The diagnostic session that led to these fixes was recorded on Revision 13; I still want to compare the affected scenes on this build before closing the flashing report. The firing crash and other open checks remain in the project guide.

Extract the complete **{package.name}** into a separate folder and keep your saves, mods and preferences. No game files are included; you need your own decrypted Bloodborne CUSA03173 1.09 dump.

[Full Revision 14 notes]({notes_url})

Source commit: `{commit}`

ZIP SHA256: `{checksum}`

Maintained by TatsunaKyo, based on Super Medo's Windows port, bbport and shadPS4. Original project, community and vendor credits and licenses are retained.
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
