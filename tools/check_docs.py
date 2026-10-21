# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Check first-party Markdown links/assets and heading anchors without network IO."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit
import collections
import html
import json
import re
import subprocess
from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
md = MarkdownIt('commonmark', {'html': True})


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.links.extend(attrs[key] for key in ('href', 'src') if attrs.get(key))
        self.ids.update(attrs[key] for key in ('id', 'name') if attrs.get(key))


def plain(children):
    return ''.join(token.content for token in children or []
                   if token.type in ('text', 'code_inline', 'image'))


def slug(text):
    return re.sub(r'[^\w\- ]', '', text.lower(), flags=re.UNICODE).replace(' ', '-')


def check(root=ROOT):
    root = Path(root).resolve()
    paths = sorted({root/name for name in subprocess.check_output(
        ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '*.md'], cwd=root,
        text=True).splitlines() if not name.startswith(('gpu/third_party/', 'third_party/'))})
    links, anchors = {}, {}
    for path in paths:
        tokens = md.parse(path.read_text(encoding='utf-8'))
        found, ids, counts = [], set(), collections.Counter()
        for index, token in enumerate(tokens):
            if token.type == 'heading_open':
                key = slug(plain(tokens[index+1].children))
                n = counts[key]
                counts[key] += 1
                ids.add(key + (f'-{n}' if n else ''))
            if token.type in ('html_inline', 'html_block'):
                parser = Links()
                parser.feed(token.content)
                found.extend(parser.links)
                ids.update(parser.ids)
            for child in token.children or []:
                for key in ('href', 'src'):
                    if child.attrGet(key):
                        found.append(child.attrGet(key))
                if child.type == 'html_inline':
                    parser = Links()
                    parser.feed(child.content)
                    found.extend(parser.links)
                    ids.update(parser.ids)
        links[path], anchors[path] = found, ids
    errors, checked = [], 0
    for path, refs in links.items():
        for ref in refs:
            parts = urlsplit(html.unescape(ref))
            if parts.scheme or parts.netloc:
                continue
            target = (path.parent / unquote(parts.path)).resolve() if parts.path else path
            if not target.exists():
                errors.append((str(path.relative_to(root)), ref, 'missing target'))
                continue
            fragment = unquote(parts.fragment).removeprefix('user-content-')
            if fragment and target in anchors and fragment not in anchors[target]:
                errors.append((str(path.relative_to(root)), ref, 'missing anchor'))
            checked += 1
    return {'pages': len(paths), 'relative_links': checked, 'errors': errors}


def main():
    report = check()
    out = ROOT/'out/verification'
    out.mkdir(parents=True, exist_ok=True)
    (out/'documentation-links.json').write_text(json.dumps(report, indent=2))
    print(f"{report['pages']} Markdown pages; {report['relative_links']} relative links/assets; {len(report['errors'])} errors")
    for error in report['errors']:
        print(' | '.join(error))
    raise SystemExit(bool(report['errors']))


if __name__ == '__main__':
    main()
