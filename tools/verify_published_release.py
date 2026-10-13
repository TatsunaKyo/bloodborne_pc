# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Check the uploaded ZIP, sidecar, tag and recorded source; never modify a release."""
import argparse
import json
import os
from pathlib import Path
import tempfile
import time
import urllib.parse
import urllib.request
from release_integrity import TAG_RE, require, package_name, validate, validate_developer, checksum


def release_version(release):
    require(isinstance(release,dict) and not release.get('draft'), 'No published release found')
    tag=release.get('tag_name')
    require(isinstance(tag,str), 'Missing release tag')
    match=TAG_RE.fullmatch(tag)
    require(match, 'Release is not a TatsunaKyo Windows revision')
    return match[1]+'-tatsunakyo.'+match[2]


def verify(release, directory, repo=None, fetch=None, *, refresh=None, wait_seconds=0):
    version=release_version(release); name=package_name(version); assets=release.get('assets',[])
    require(isinstance(assets,list), 'Malformed release assets')
    def asset(label):
        found=[a for a in assets if isinstance(a,dict) and a.get('name')==label and a.get('state','uploaded')=='uploaded']
        require(len(found)==1,'Expected one uploaded asset: '+label)
        expected='https://github.com/TatsunaKyo/bloodborne_pc/releases/download/'+release['tag_name']+'/'+label
        require(found[0].get('browser_download_url')==expected,
                'Unexpected asset download origin')
        return found[0]
    package,sidecar=asset(name),asset(name+'.sha256')
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    def download(record):
        path=directory/record['name']
        if fetch is not None:fetch(record['browser_download_url'],path)
        else:
            with urllib.request.urlopen(record['browser_download_url'],timeout=90) as response,path.open('wb') as out:
                while chunk:=response.read(1024*1024):out.write(chunk)
        require(record.get('size',path.stat().st_size)==path.stat().st_size,'Uploaded asset size mismatch')
        digest=record.get('digest')
        if digest:require(digest=='sha256:'+checksum(path),'GitHub asset digest mismatch')
        return path
    path=download(package);download(sidecar)
    report=validate(path,expected_version=version,repo=repo,require_sidecar=True)
    if repo is not None:
        import subprocess
        tagged=subprocess.check_output(['git','rev-parse',release['tag_name']+'^{commit}'],cwd=repo,text=True).strip()
        require(tagged==report['source_commit'],'Public tag and package source commit disagree')
    companion = report['identity'].get('developer_bundle')
    if companion is not None:
        expected = (companion['filename'], companion['filename'] + '.sha256')
        if refresh is not None:
            release = wait_for_assets(release, refresh, wait_seconds, expected_names=expected)
            assets = release['assets']
        developer = download(asset(expected[0])); download(asset(expected[1]))
        report['developer_bundle'] = validate_developer(developer, report, require_sidecar=True)
    report.pop('notes')
    report.update(release_tag=release['tag_name'],prerelease=bool(release.get('prerelease')),published=True,
                  legacy_stable_preview_tag=release['tag_name'].endswith('-preview') and not release.get('prerelease'))
    return report


def wait_for_assets(release, refresh, seconds, *, clock=time.monotonic, pause=time.sleep, expected_names=None):
    """Allow a bounded publication/upload race; malformed or duplicate assets still fail."""
    require(0 <= seconds <= 300, 'Asset wait must be between 0 and 300 seconds')
    version = release_version(release)
    expected = expected_names or (package_name(version), package_name(version) + '.sha256')
    deadline = clock() + seconds
    while True:
        assets = release.get('assets', [])
        require(isinstance(assets, list), 'Malformed release assets')
        missing = []
        for name in expected:
            matching = [a for a in assets if isinstance(a, dict) and a.get('name') == name]
            require(len(matching) <= 1, 'Duplicate release asset: ' + name)
            if not matching or matching[0].get('state', 'uploaded') != 'uploaded': missing.append(name)
        if not missing: return release
        remaining = deadline - clock()
        require(remaining > 0, 'Release assets are missing or still uploading: ' + ', '.join(missing) +
                '. Upload the ZIP and matching SHA-256 file before publishing, then rerun this check.')
        print('Waiting for release assets: ' + ', '.join(missing), flush=True)
        pause(min(5, remaining))
        refreshed = refresh()
        require(release_version(refreshed) == version and refreshed.get('tag_name') == release.get('tag_name'),
                'Release changed while waiting for its assets')
        release = refreshed


def save_check_result(output, report):
    result = json.dumps(report, indent=2) + '\n'
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(result)
    print(result)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag',default='')
    parser.add_argument('--repo',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--wait-for-assets', type=int, default=0,
                        help='Wait at most this many seconds for a newly published ZIP and sidecar (maximum 300)')
    args=parser.parse_args()
    api='https://api.github.com/repos/TatsunaKyo/bloodborne_pc/releases/'
    api+='tags/'+urllib.parse.quote(args.tag,safe='') if args.tag else 'latest'
    headers={'Accept':'application/vnd.github+json','User-Agent':'crowned-workshop-release-check'}
    if os.environ.get('GH_TOKEN'):headers['Authorization']='Bearer '+os.environ['GH_TOKEN']
    def refresh():
        with urllib.request.urlopen(urllib.request.Request(api,headers=headers),timeout=30) as response:
            return json.load(response)
    try:
        deadline = time.monotonic() + args.wait_for_assets
        release = wait_for_assets(refresh(), refresh, args.wait_for_assets)
        with tempfile.TemporaryDirectory(prefix='workshop-release-') as tmp:
            report=verify(release,tmp,args.repo,refresh=refresh,
                          wait_seconds=max(0, deadline - time.monotonic()))
    except Exception as error:
        save_check_result(args.output, {'status': 'failed', 'requested_tag': args.tag or 'latest',
                                       'error_type': type(error).__name__, 'error': str(error)})
        raise SystemExit(1)
    save_check_result(args.output, report)


if __name__=='__main__':main()
