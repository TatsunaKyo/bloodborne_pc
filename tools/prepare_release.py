#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Prepare a release from a verified package identity and its matching notes."""
import argparse
import json
import posixpath
from pathlib import Path
import re
from urllib.parse import urlencode, urlsplit, quote
from release_integrity import validate, validate_developer, canonical_tag, TAG_RE, require


def prepare(package: Path, *, channel=None, existing_tag=None, repo=None):
    report = validate(package, repo=repo)
    identity, version = report['identity'], report['version']
    if channel is None:
        channel = identity.get('channel') or ('preview' if identity['release_tag'].endswith('-preview') else 'stable')
    tag = canonical_tag(version, channel)
    if existing_tag is not None:
        match = TAG_RE.fullmatch(existing_tag)
        require(match and match[1]+'-tatsunakyo.'+match[2] == version, 'Existing tag belongs to a different version')
        tag = existing_tag
    title = f"Bloodborne: The Crowned Workshop — Revision {report['revision']}" + (' preview' if channel == 'preview' else '')
    lines = report['notes'].strip().splitlines()
    if lines and lines[0].startswith('# '): lines = lines[1:]
    notes = '\n'.join(lines).strip()
    commit = report['source_commit']
    # Release descriptions have a different URL base from docs/releases/*.md.
    # Keep their guide links tied to this package's exact source revision.
    def guide_link(match):
        target=match[2]
        parsed=urlsplit(target)
        if parsed.scheme or parsed.netloc or target.startswith('#'):return match[0]
        path=posixpath.normpath(posixpath.join('docs/releases',parsed.path))
        require(not path.startswith('../'), 'Release note link leaves the repository')
        url='https://github.com/TatsunaKyo/bloodborne_pc/blob/'+commit+'/'+quote(path,safe='/')
        if parsed.query:url+='?'+parsed.query
        if parsed.fragment:url+='#'+parsed.fragment
        return match[1]+url+match[3]
    notes=re.sub(r'(\]\()([^\s)]+)(\))',guide_link,notes)
    body = notes+f"\n\nPackage: `{package.name}`\n\nSHA256: `{report['sha256']}`\n\nSource: [{commit[:7]}](https://github.com/TatsunaKyo/bloodborne_pc/commit/{commit}).\n"
    developer = None
    if report['identity'].get('developer_bundle'):
        companion = package.parent / report['identity']['developer_bundle']['filename']
        developer = validate_developer(companion, report, require_sidecar=True)
        body += (f"\nOptional Developer package: `{developer['filename']}`\n\n"
                 f"Developer SHA256: `{developer['sha256']}`\n\n"
                 "Upload both ZIPs and both matching `.zip.sha256` files before publishing. Players only need the ordinary game package.\n")
    url = 'https://github.com/TatsunaKyo/bloodborne_pc/releases/new?' + urlencode({
        'tag':tag, 'target':commit, 'title':title, 'body':body, 'prerelease':'true' if channel == 'preview' else 'false'})
    return {'title':title, 'body':body, 'url':url, 'release_page':url,
            'source_commit':commit, 'source_tree':report['source_tree'], 'version':version,
            'package':package.name, 'bytes':report['bytes'], 'zip_sha256':report['sha256'],
            'sha256':report['sha256'], 'release_tag':tag, 'channel':channel, 'prerelease':channel == 'preview',
            'published':False, 'source_verified':report['source_verified'], 'developer_bundle':developer}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('--channel', choices=('stable','preview'))
    parser.add_argument('--existing-tag', help='Keep a previously published tag while regenerating its form')
    parser.add_argument('--repo', type=Path, help='Verify the exact source commit, tree and patch')
    parser.add_argument('--output', type=Path, help='Write Markdown and JSON here')
    args = parser.parse_args()
    result = prepare(args.package, channel=args.channel, existing_tag=args.existing_tag, repo=args.repo)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text('# '+result['title']+'\n\n'+result['body'], encoding='utf-8')
        args.output.with_suffix('.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(result['url'])


if __name__ == '__main__':
    main()
