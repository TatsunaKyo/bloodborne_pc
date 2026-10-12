# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Check the uploaded ZIP, sidecar, tag and recorded source; never modify a release."""
import argparse
import json
import os
from pathlib import Path
import tempfile
import urllib.parse
import urllib.request
from release_integrity import TAG_RE, require, package_name, validate, checksum


def release_version(release):
    require(isinstance(release,dict) and not release.get('draft'), 'No published release found')
    tag=release.get('tag_name')
    require(isinstance(tag,str), 'Missing release tag')
    match=TAG_RE.fullmatch(tag)
    require(match, 'Release is not a TatsunaKyo Windows revision')
    return match[1]+'-tatsunakyo.'+match[2]


def verify(release, directory, repo=None, fetch=None):
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
    report.pop('notes')
    report.update(release_tag=release['tag_name'],prerelease=bool(release.get('prerelease')),published=True,
                  legacy_stable_preview_tag=release['tag_name'].endswith('-preview') and not release.get('prerelease'))
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag',default='')
    parser.add_argument('--repo',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    api='https://api.github.com/repos/TatsunaKyo/bloodborne_pc/releases/'
    api+='tags/'+urllib.parse.quote(args.tag,safe='') if args.tag else 'latest'
    headers={'Accept':'application/vnd.github+json','User-Agent':'crowned-workshop-release-check'}
    if os.environ.get('GH_TOKEN'):headers['Authorization']='Bearer '+os.environ['GH_TOKEN']
    with urllib.request.urlopen(urllib.request.Request(api,headers=headers),timeout=30) as response:release=json.load(response)
    with tempfile.TemporaryDirectory(prefix='workshop-release-') as tmp:report=verify(release,tmp,args.repo)
    result=json.dumps(report,indent=2)+'\n'
    if args.output:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(result)
    print(result)


if __name__=='__main__':main()
