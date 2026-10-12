# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Assemble fresh Windows executables with pinned, unchanged runtime dependencies.

The stable baseline supplies redistributables/licenses only. Native programs,
the launcher and repository files are replaced by the current build.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from release_integrity import checksum, package_name, canonical_tag, validate, require
from pe_integrity import PE, system
from prepare_release import prepare

ROOT=Path(__file__).resolve().parents[1]
TESTS=('frame-limits-test','frame-pacing-test','background-pause-test','temporal-history-test',
       'motion-history-test','xess-presets-test','amd-antilag-test','camera-motion-test')


def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT)


def assemble(baseline, native, launcher, destination, channel='stable', dll_dir=None):
    lock=json.loads((ROOT/'packaging/windows/runtime-baseline.lock.json').read_text())
    baseline=Path(baseline); native=Path(native); launcher=Path(launcher); destination=Path(destination)
    require(checksum(baseline)==lock['sha256'],'Baseline runtime bundle checksum mismatch')
    source=ast.parse((ROOT/'launcher/bbport_launcher_win.py').read_text())
    version=next(n.value.value for n in source.body if isinstance(n,ast.Assign)
                 and any(isinstance(t,ast.Name) and t.id=='VERSION' for t in n.targets))
    revision=version.rsplit('.',1)[1]; commit=git('rev-parse','HEAD').decode().strip()
    require(not git('diff','--name-only','--ignore-submodules=all','HEAD'),'Commit source changes before packaging')
    require(all((native/(name+'.exe')).is_file() for name in TESTS),'Native regression executables are missing')
    require((ROOT/'out/verification/native-windows-tests.log').is_file(), 'Run the native Windows tests before packaging')
    destination.mkdir(parents=True,exist_ok=True)
    target=destination/package_name(version);require(not target.exists(),'Package already exists; preserve the previous candidate')
    with tempfile.TemporaryDirectory(prefix='workshop-package-') as directory:
        temp=Path(directory);stage=temp/f'Bloodborne-Windows-TatsunaKyo-Revision-{revision}'
        with zipfile.ZipFile(baseline) as z:
            old=next(n.split('/')[0] for n in z.namelist() if n.endswith('/BUILD-IDENTITY.json'))
            z.extractall(temp/'baseline')
        shutil.copytree(temp/'baseline'/old,stage)
        for name in ('source','docs','scripts','tools','launcher','_internal','.github'):
            shutil.rmtree(stage/name,ignore_errors=True)
        shutil.copy2(launcher/'Bloodborne.exe',stage/'Bloodborne.exe')
        shutil.copytree(launcher/'_internal',stage/'_internal')
        for name in ('docs','scripts','tools','patches','launcher','.github'):
            shutil.copytree(ROOT/name,stage/name,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        for name in ('README.md','LICENSE','run.py','CONTRIBUTING.md','SECURITY.md'):shutil.copy2(ROOT/name,stage/name)
        shutil.copy2(ROOT/'packaging/windows/bbport.menu.ini',stage/'bbport.menu.ini')
        shutil.copy2(ROOT/'packaging/windows/README-Windows.txt',stage/'README-Windows.txt')
        # Do not keep historical test programs under the names of a new build.
        for p in (stage/'bin').glob('*-test.exe'):p.unlink()
        programs={'Bloodborne.exe':checksum(stage/'Bloodborne.exe')}
        for name,output in [('bb-probe','bin/bb-probe.exe'),('bb-gpu-capabilities','bin/bb-gpu-capabilities.exe'),
                            ('bb-play','Play Bloodborne.exe')]+[(n,'bin/'+n+'.exe') for n in TESTS]:
            subprocess.run(['llvm-strip','--strip-debug','-o',str(stage/output),str(native/(name+'.exe'))],check=True)
            programs[output]=checksum(stage/output)
        # Use the pinned CLANG64 DLLs selected for this build, including transitive dependencies.
        require(dll_dir is not None, 'Provide the CLANG64 DLL directory for this build')
        prefix=Path(dll_dir)
        for p in (stage/'bin').glob('*.dll'):
            current=prefix/p.name
            if current.is_file():shutil.copy2(current,p)
        # A new compiler/library may need a DLL absent from the baseline. Resolve
        # that closure from the same pinned toolchain instead of silently omitting it.
        available={p.name.lower():p for p in prefix.glob('*.dll')}
        pending=list((stage/'bin').glob('*.dll'))+[stage/'bin/bb-probe.exe',stage/'bin/bb-gpu-capabilities.exe',stage/'Play Bloodborne.exe']
        seen=set()
        while pending:
            program=pending.pop()
            if program in seen:continue
            seen.add(program)
            for dll,_ in PE(program).imports():
                if dll in system or dll.startswith(('api-ms-win-','ext-ms-win-')):continue
                target=stage/'bin'/dll
                if not target.is_file() and dll in available:
                    shutil.copy2(available[dll],target);pending.append(target)
        command='@echo off\r\ncd /d "%~dp0"\r\npowershell -NoProfile -Command "$p=Join-Path (Get-Location) \'Bloodborne.exe\'; if ((Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash -ne \''+programs['Bloodborne.exe']+'\') {Write-Error \'Incorrect launcher for TatsunaKyo revision '+revision+'.\'; exit 1}; Start-Process -FilePath $p -WorkingDirectory (Get-Location)"\r\n'
        (stage/'Start-Verified-Launcher.cmd').write_bytes(command.encode('ascii'))
        source_dir=stage/'source';source_dir.mkdir()
        base=json.loads((temp/'baseline'/old/'BUILD-IDENTITY.json').read_text())['upstream_base']
        (source_dir/'tatsunakyo-revision.patch').write_bytes(git('diff','--binary',base,commit))
        for name in git('diff','--name-only',base,commit).decode().splitlines():
            p=source_dir/'modified-files'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(git('show',commit+':'+name))
        provenance={'project':'Bloodborne: The Crowned Workshop','version':version,'revision':int(revision),
                    'channel':channel,'release_tag':canonical_tag(version,channel),'source_commit':commit,
                    'source_tree':git('rev-parse','HEAD^{tree}').decode().strip(),'upstream_base':base,
                    'repository':'https://github.com/TatsunaKyo/bloodborne_pc','executables':programs,
                    'runtime_files':{str(p.relative_to(stage)):checksum(p) for p in stage.rglob('*')
                                     if p.suffix.lower() in ('.dll','.pyd')},
                    'runtime_baseline':lock,'native_and_launcher_fresh_build':True,
                    'byte_identical_build_claimed':False}
        (stage/'BUILD-IDENTITY.json').write_text(json.dumps(provenance,indent=2)+'\n')
        (stage/'BUILD-INFO.txt').write_text('The Crowned Workshop\nSource: '+commit+'\nNative and launcher built from this checkout. Unchanged SDK redistributables are pinned to the recorded baseline. No claim of byte-identical compiler output.\n')
        records=source_dir/'verification';records.mkdir()
        for p in (ROOT/'out/verification').rglob('*'):
            if p.is_file():
                out=records/p.relative_to(ROOT/'out/verification');out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,out)
        subprocess.run(['pacman','-Q'],check=True,stdout=(records/'msys2-installed-packages.txt').open('wb'))
        subprocess.run(['clang++','--version'],check=True,stdout=(records/'compiler.txt').open('wb'))
        notes=(ROOT/f'docs/releases/windows-v{version}.md').read_text()
        (stage/'README-EN.txt').write_text(notes)
        # The portable current player guide is kept instead of a previous revision summary.
        (stage/'README-IT.txt').write_text('Bloodborne: The Crowned Workshop\nVersione '+version+'\nApri README-Windows.txt per installazione, impostazioni live e documentazione aggiornata.\n')
        for p in stage.rglob('__pycache__'):shutil.rmtree(p,ignore_errors=True)
        with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for p in sorted(stage.rglob('*')):
                if p.is_file():z.write(p,str(Path(stage.name)/p.relative_to(stage)))
    target.with_suffix('.zip.sha256').write_text(checksum(target)+'  '+target.name+'\n')
    report=validate(target,repo=ROOT,require_sidecar=True)
    report.pop('notes');(destination/'package-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    release=prepare(target,channel=channel,repo=ROOT)
    (destination/'release.json').write_text(json.dumps(release,indent=2)+'\n')
    (destination/'release.md').write_text('# '+release['title']+'\n\n'+release['body'])
    return target


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--native',type=Path,default=ROOT/'out/gpu')
    parser.add_argument('--launcher',type=Path,default=ROOT/'out/pyi-dist/Bloodborne')
    parser.add_argument('--output',type=Path,default=ROOT/'dist')
    parser.add_argument('--channel',choices=('stable','preview'),default='stable')
    parser.add_argument('--dll-dir',type=Path,required=True)
    args=parser.parse_args()
    print(assemble(args.baseline,args.native,args.launcher,args.output,args.channel,args.dll_dir))


if __name__=='__main__':main()
