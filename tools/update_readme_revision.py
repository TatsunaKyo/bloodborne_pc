# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Keep the README's build badge in step with the launcher version."""
import argparse
import ast
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def expected(root=ROOT):
    source = ast.parse((root / 'launcher/bbport_launcher_win.py').read_text(encoding='utf-8'))
    version = next(node.value.value for node in source.body if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == 'VERSION' for t in node.targets))
    match = re.fullmatch(r'(\d+(?:\.\d+)*)-tatsunakyo\.(\d+)', version)
    if not match:
        raise ValueError('Launcher version has no Crowned Workshop revision')
    notes = f'docs/releases/windows-v{version}.md'
    if not (root / notes).is_file():
        raise ValueError('Current revision release notes are missing')
    unreleased = re.search(r'^Status: unreleased\s*$', (root / notes).read_text(encoding='utf-8'), re.M | re.I) is not None
    label = f'Source R{match[2]} (unreleased)' if unreleased else f'Revision {match[2]}'
    width = 230 if unreleased else 164
    badge = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="28" viewBox="0 0 {width} 28" '
             f'role="img" aria-label="{label}"><title>{label}</title><rect width="{width}" height="28" '
             f'rx="14" fill="#003b1b"/><text x="{width // 2}" y="19" text-anchor="middle" '
             f'font-family="Arial, Helvetica, sans-serif" font-size="14" fill="#20d66b">{label}</text></svg>\n')
    link = f'<a href="{notes}"><img src="docs/assets/readme/revision-stable.svg" alt="{label}" height="28"></a>'
    return badge, link


def update(root=ROOT, *, check=False):
    badge, link = expected(root)
    readme_path = root / 'README.md'
    readme = readme_path.read_text(encoding='utf-8')
    pattern = r'<a href="[^"]+"><img src="docs/assets/readme/revision-stable\.svg"[^>]+></a>'
    updated, count = re.subn(pattern, lambda _: link, readme)
    if count != 1:
        raise ValueError('README must contain one revision badge')
    badge_path = root / 'docs/assets/readme/revision-stable.svg'
    stale = updated != readme or not badge_path.is_file() or badge_path.read_text(encoding='utf-8') != badge
    if check and stale:
        raise ValueError('README revision is stale; run python tools/update_readme_revision.py')
    if not check:
        readme_path.write_text(updated, encoding='utf-8')
        badge_path.write_text(badge, encoding='utf-8')
    return stale


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    update(check=parser.parse_args().check)
