# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Exercise release preparation and malformed package rejection with real ZIPs."""
import hashlib
import importlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
integrity = importlib.import_module('release_integrity')
prepare = importlib.import_module('prepare_release').prepare


def raw_member(archive, name, data):
    # Preserve malformed fixture bytes on Windows too: ZipInfo's constructor
    # would otherwise sanitize the very filename this regression must test.
    entry = zipfile.ZipInfo('fixture')
    entry.filename = entry.orig_filename = name
    archive.writestr(entry, data)


def pe():
    data = bytearray(512); data[:2] = b'MZ'
    struct.pack_into('<I', data, 60, 128); data[128:132] = b'PE\0\0'
    struct.pack_into('<H', data, 132, 0x8664); struct.pack_into('<H', data, 152, 0x20b)
    struct.pack_into('<I', data, 260, 16)
    return bytes(data)


class Releases(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def package(self, version='1.6-tatsunakyo.22', modify=None, extra=None):
        data = {name:pe() for name in integrity.CORE+integrity.RUNTIMES+('_internal/python314.dll',)}
        data['bin/streamline/nvngx_dlss.dll'] = data['bin/nvngx_dlss.dll']
        data.update({name:b'fixture' for name in integrity.DATA})
        data['source/modified-files/launcher/bbport_launcher_win.py'] = f'VERSION = {version!r}\n'.encode()
        data[f'docs/releases/windows-v{version}.md'] = b'# Workshop revision\n\nI kept the settings shared.\n'
        identity = {'version':version, 'source_commit':'1'*40, 'source_tree':'2'*40,
                    'release_tag':'windows-v'+version, 'channel':'stable',
                    'executables':{name:hashlib.sha256(data[name]).hexdigest() for name in integrity.CORE},
                    'runtime_files':{name:hashlib.sha256(data[name]).hexdigest() for name in integrity.RUNTIMES+('bin/streamline/nvngx_dlss.dll','_internal/python314.dll')}}
        base,revision=integrity.version_parts(version)
        if (tuple(map(int,base.split('.'))),revision)>=((1,6),54):
            data['launcher/bbport_launcher_win.py']=data['source/modified-files/launcher/bbport_launcher_win.py']
            for name in ('patches/Bloodborne.xml','patches/redzone.json','scripts/patches.py'):
                data[name]=b'current fixture'
            identity['runtime_source_files']={name:hashlib.sha256(data[name]).hexdigest() for name in
                ('run.py','launcher/bbport_launcher_win.py','scripts/patches.py','patches/Bloodborne.xml','patches/redzone.json')}
            data['bin/bbport_dlss_native.dll']=pe()
            data['bin/nvngx_dlssg.dll']=data['bin/streamline/nvngx_dlssg.dll']
            identity['native_fg_runtime']={
                'default_sr_bridge':{'file':'bin/bbport_dlss.dll','abi':1,
                    'sha256':hashlib.sha256(data['bin/bbport_dlss.dll']).hexdigest()},
                'native_fg_bridge':{'file':'bin/bbport_dlss_native.dll','abi':2,
                    'sha256':hashlib.sha256(data['bin/bbport_dlss_native.dll']).hexdigest()},
                'native_fg_feature':{'file':'bin/nvngx_dlssg.dll','same_bytes_as':'bin/streamline/nvngx_dlssg.dll',
                    'sha256':hashlib.sha256(data['bin/nvngx_dlssg.dll']).hexdigest()}}
        if modify: modify(identity, data)
        data['BUILD-IDENTITY.json'] = json.dumps(identity).encode()
        path = self.root/integrity.package_name(version)
        with zipfile.ZipFile(path, 'w') as archive:
            for name, value in data.items(): archive.writestr('Workshop/'+name, value)
            for name, value in extra or []: raw_member(archive, name, value)
        return path

    def test_full_assembly_returns_and_validates_zip_after_dependency_copy(self):
        import shutil
        assembler = importlib.import_module('assemble_windows')
        repo = self.root/'source'; repo.mkdir()
        version = '1.6-tatsunakyo.55'
        files = {'VERSION':'55', 'run.py':'# fixture runtime\n',
            'launcher/bbport_launcher_win.py':f'VERSION = {version!r}\n',
            'scripts/patches.py':'# current patch compiler\n',
            'patches/Bloodborne.xml':'<Patch/>', 'patches/redzone.json':'{}',
            f'docs/releases/windows-v{version}.md':'# Fixture release\n',
            'packaging/windows/README-Windows.txt':'Current player guide\n',
            'packaging/windows/Capture-Traversal.cmd':'@echo off\n',
            'packaging/windows/licenses/fixture.txt':'Fixture license\n',
            'packaging/windows/runtime-baseline.lock.json':'{}',
            '.github/workflows/check.yml':'name: fixture\n', '.gitignore':'out/\n'}
        files.update({name:'Fixture source\n' for name in
                      ('README.md','LICENSE','CONTRIBUTING.md','SECURITY.md','AGENTS.md')})
        for name, value in files.items():
            p=repo/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(value)
        def git(*args):
            return subprocess.check_output(['git',*args],cwd=repo)
        def commit():
            git('add','.')
            git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid',
                'commit','-qm','assembly fixture')
            return git('rev-parse','HEAD').decode().strip()
        git('init','-q'); base=commit()
        native_lock={}
        def baseline_data(identity, data):
            identity['upstream_base']=base
            native_lock.update(identity['native_fg_runtime'])
            data['bin/stale-test.exe']=pe()
        baseline=self.package(version,modify=baseline_data)
        (repo/'packaging/windows/runtime-baseline.lock.json').write_text(
            json.dumps({'sha256':integrity.checksum(baseline)}))
        (repo/'run.py').write_text('# revised current runtime\n')
        source_commit=commit()
        records=repo/'out/verification';records.mkdir(parents=True)
        (records/'native-windows-tests.log').write_text('PASS fixture CPU tests\n')
        native=self.root/'native';native.mkdir()
        for name in (*assembler.TESTS,'bb-probe','bb-gpu-capabilities','bb-play'):
            (native/(name+'.exe')).write_bytes(pe())
        launcher=self.root/'launcher';(launcher/'_internal').mkdir(parents=True)
        (launcher/'Bloodborne.exe').write_bytes(pe())
        (launcher/'_internal/python314.dll').write_bytes(pe())
        prefix=self.root/'toolchain';prefix.mkdir()
        (prefix/'fixture-dependency.dll').write_bytes(pe())
        actual_run=subprocess.run
        def tool_run(command, **kwargs):
            if command[0]=='llvm-strip':
                shutil.copy2(command[-1],command[command.index('-o')+1])
                return subprocess.CompletedProcess(command,0)
            if command[0] in ('pacman','clang++'):
                kwargs['stdout'].write(b'fixture toolchain\n')
                return subprocess.CompletedProcess(command,0)
            return actual_run(command,**kwargs)
        class ImportedDependency:
            def __init__(self, path):self.path=Path(path)
            def imports(self):
                return [] if self.path.name=='fixture-dependency.dll' else [('fixture-dependency.dll',[])]
        destination=self.root/'assembled'
        with patch.object(assembler,'ROOT',repo), patch.object(assembler,'PE',ImportedDependency), \
             patch.object(assembler,'install_nvidia_fg'), \
             patch.object(assembler,'install_native_fg',return_value=native_lock), \
             patch.object(assembler.subprocess,'run',side_effect=tool_run):
            package=assembler.assemble(baseline,native,launcher,destination,dll_dir=prefix)
        self.assertEqual(package,destination/integrity.package_name(version))
        report=integrity.validate(package,repo=repo,require_sidecar=True)
        self.assertEqual(report['source_commit'],source_commit)
        self.assertEqual(len(list(destination.iterdir())),2)
        self.assertFalse(any('Developer' in p.name for p in destination.iterdir()))
        with zipfile.ZipFile(package) as archive:
            names={name.removeprefix(report['root']+'/') for name in archive.namelist()}
            self.assertIn('bin/fixture-dependency.dll',names)
            self.assertIn('Capture-Traversal.cmd',names)
            self.assertFalse(any(name.endswith('-test.exe') for name in names))

    def test_preparation_uses_identity_notes_and_real_hash(self):
        for version in ('1.6-tatsunakyo.15','1.6-tatsunakyo.21','1.6-tatsunakyo.22','1.7-tatsunakyo.1'):
            p = self.package(version); report = prepare(p)
            self.assertEqual(report['version'], version)
            self.assertEqual(report['release_tag'], 'windows-v'+version)
            self.assertEqual(report['sha256'], hashlib.sha256(p.read_bytes()).hexdigest())
            self.assertIn('I kept the settings shared.', report['body'])
            self.assertIn('target='+'1'*40, report['url'])
            self.assertFalse(report['prerelease'])

    def test_preview_and_legacy_stable_tags(self):
        p = self.package('1.6-tatsunakyo.21')
        preview = prepare(p, channel='preview')
        self.assertTrue(preview['prerelease']); self.assertTrue(preview['release_tag'].endswith('-preview'))
        stable = prepare(p, channel='stable', existing_tag='windows-v1.6-tatsunakyo.21-preview')
        self.assertFalse(stable['prerelease']); self.assertEqual(stable['release_tag'], 'windows-v1.6-tatsunakyo.21-preview')
        with self.assertRaises(ValueError): prepare(p, existing_tag='windows-v1.6-tatsunakyo.20')

    def test_release_links_resolve_to_the_recorded_source(self):
        def notes(identity,data):
            data['docs/releases/windows-v1.6-tatsunakyo.22.md']=b'# Revision\n\n[Setup](../repository-setup.md#actions) and [GitHub](https://github.com/).\n'
        result=prepare(self.package(modify=notes))
        self.assertIn('https://github.com/TatsunaKyo/bloodborne_pc/blob/'+'1'*40+'/docs/repository-setup.md#actions',result['body'])
        self.assertIn('[GitHub](https://github.com/)',result['body'])
        self.assertNotIn('](../',result['body'])

    def test_identity_and_binary_mismatches(self):
        mutations = [lambda i,d:i.update(source_commit='bad'),
                     lambda i,d:i.update(source_tree='bad'),
                     lambda i,d:i.update(release_tag='windows-v1.6-tatsunakyo.9'),
                     lambda i,d:i['executables'].pop('Bloodborne.exe'),
                     lambda i,d:d.pop('bin/bb-probe.exe'),
                     lambda i,d:d.pop('bin/streamline/sl.interposer.dll'),
                     lambda i,d:d.update({'bin/xess/libxess.dll':b'wrong runtime'}),
                     lambda i,d:d.update({'Bloodborne.exe':b'corrupt'}),
                     lambda i,d:d.update({'source/modified-files/launcher/bbport_launcher_win.py':b"VERSION='1.6-tatsunakyo.21'"}),
                     lambda i,d:d.pop('docs/releases/windows-v1.6-tatsunakyo.22.md')]
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): integrity.validate(self.package(modify=mutation))

    def test_new_releases_require_both_ngx_search_paths(self):
        version = '1.6-tatsunakyo.40'
        self.assertEqual(integrity.validate(self.package(version))['version'], version)
        def r39_omission(identity, data):
            # R39 removed the file AND its recorded hash, so import and hash
            # checks passed. The search-path contract must reject that layout.
            data.pop('bin/streamline/nvngx_dlss.dll')
            identity['runtime_files'].pop('bin/streamline/nvngx_dlss.dll')
        with self.assertRaisesRegex(ValueError, 'missing bin/streamline/nvngx_dlss.dll'):
            integrity.validate(self.package(version, modify=r39_omission))
        # Existing archives remain readable for recovery, without claiming that
        # the old broken layout is fit for another release.
        integrity.validate(self.package('1.6-tatsunakyo.39', modify=r39_omission))

    def test_new_releases_require_and_verify_startup_sources(self):
        version='1.6-tatsunakyo.54'
        integrity.validate(self.package(version))
        with self.assertRaisesRegex(ValueError,'Missing first-party runtime source provenance'):
            integrity.validate(self.package(version,modify=lambda i,d:i.pop('runtime_source_files')))
        with self.assertRaisesRegex(ValueError,'First-party runtime checksum mismatch: patches/Bloodborne.xml'):
            integrity.validate(self.package(version,modify=lambda i,d:d.update({'patches/Bloodborne.xml':b'old revision'})))
        with self.assertRaisesRegex(ValueError,'Missing native FG bridge provenance'):
            integrity.validate(self.package(version,modify=lambda i,d:i.pop('native_fg_runtime')))

    def test_every_startup_file_is_compared_with_git_even_if_self_hashes_match(self):
        repo=self.root/'source';repo.mkdir()
        tracked={'VERSION':b'54','run.py':b'launch',
            'launcher/app.py':b'launcher','scripts/patches.py':b'new patch compiler',
            'tools/input-plan.json':b'current input plan','patches/Bloodborne.xml':b'new FPS patch data',
            'patches/redzone.json':b'new red-zone data','packaging/windows/bbport.menu.ini':b'new defaults'}
        for name,data in tracked.items():
            p=repo/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
        subprocess.run(['git','init','-q'],cwd=repo,check=True)
        subprocess.run(['git','add','.'],cwd=repo,check=True)
        subprocess.run(['git','-c','user.name=Fixture','-c','user.email=fixture@example.invalid',
                        'commit','-qm','fixture'],cwd=repo,check=True)
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
        layout=integrity.runtime_source_paths(repo,commit)
        self.assertEqual(set(layout),{n.removeprefix('packaging/windows/') for n in tracked})
        shipped={name:tracked[source] for name,source in layout.items()}
        self.assertEqual(set(integrity.verify_runtime_sources(shipped.__getitem__,repo,commit)),set(shipped))
        for name in ('patches/Bloodborne.xml','patches/redzone.json','scripts/patches.py','tools/input-plan.json'):
            with self.subTest(name=name):
                old=shipped[name];shipped[name]=b'old payload with a valid self-reported hash'
                with self.assertRaisesRegex(ValueError,'Packaged runtime differs from source commit: '+name):
                    integrity.verify_runtime_sources(shipped.__getitem__,repo,commit)
                shipped[name]=old

    def test_dynamic_dlss_runtime_requires_matching_bytes_and_provenance(self):
        def mismatch(identity, data):
            name = 'bin/streamline/nvngx_dlss.dll'
            data[name] += b'another runtime'
            identity['runtime_files'][name] = hashlib.sha256(data[name]).hexdigest()
        with self.assertRaisesRegex(ValueError, 'runtimes in bin and bin/streamline disagree'):
            integrity.validate(self.package('1.6-tatsunakyo.40', modify=mismatch))
        with self.assertRaisesRegex(ValueError, 'Missing dynamic DLSS runtime provenance'):
            integrity.validate(self.package('1.6-tatsunakyo.40', modify=lambda i,d:
                i['runtime_files'].pop('bin/streamline/nvngx_dlss.dll')))

    def test_wrong_binary_architecture_even_with_matching_hash(self):
        def mutation(identity, data):
            data['Bloodborne.exe'] = b'not a Windows program'
            identity['executables']['Bloodborne.exe'] = hashlib.sha256(data['Bloodborne.exe']).hexdigest()
        with self.assertRaises(ValueError): integrity.validate(self.package(modify=mutation))

    def test_path_traversal_multiple_roots_duplicates_and_game_files(self):
        for name in ('Workshop/../evil', 'Workshop/C:/evil', 'Workshop/eboot.bin',
                     'Other/extra', 'Workshop/README.MD', 'Workshop/dir\\evil'):
            with self.subTest(name=name), self.assertRaises(ValueError): integrity.validate(self.package(extra=[(name,b'x')]))

    def test_parser_normalization_cannot_hide_unsafe_member_names(self):
        for name in ('Workshop/dir\\evil', 'Workshop/extra\x00hidden'):
            package = self.package(extra=[(name, b'x')])
            # Exercise Windows parsing on Linux as well as in Windows CI.
            with self.subTest(name=name), patch('zipfile.os.sep', '\\'):
                with zipfile.ZipFile(package) as archive:
                    entry = archive.infolist()[-1]
                    self.assertEqual(entry.orig_filename, name)
                    self.assertNotEqual(entry.filename, name)
                with self.assertRaisesRegex(ValueError, 'Unsafe archive path'):
                    integrity.validate(package)

    def test_symlink_rejected(self):
        p = self.package()
        info = zipfile.ZipInfo('Workshop/link'); info.create_system = 3; info.external_attr = 0o120777 << 16
        with zipfile.ZipFile(p, 'a') as z: z.writestr(info, 'outside')
        with self.assertRaises(ValueError): integrity.validate(p)

    def test_windows_aliases_and_devices_rejected(self):
        for name in ('Workshop/README.md.', 'Workshop/README.md ', 'Workshop/NUL.txt',
                     'Workshop/dir/COM1', 'Workshop/LPT¹.log', 'Workshop/AUX',
                     'Workshop/dir\x01/file', 'Workshop/CON/source'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                integrity.validate(self.package(extra=[(name, b'x')]))

    def test_sidecar_filename_and_hash(self):
        p = self.package(); sha = integrity.checksum(p); sidecar = p.with_suffix('.zip.sha256')
        with self.assertRaises(ValueError): integrity.validate(p, require_sidecar=True)
        sidecar.write_text(sha+'  '+p.name+'\n')
        self.assertEqual(integrity.validate(p, require_sidecar=True)['sha256'], sha)
        for value in ('0'*64+'  '+p.name, sha+'  wrong.zip'):
            sidecar.write_text(value)
            with self.assertRaises(ValueError): integrity.validate(p, require_sidecar=True)

    def test_expected_version_and_filename(self):
        p = self.package()
        with self.assertRaises(ValueError): integrity.validate(p, expected_version='1.6-tatsunakyo.21')
        wrong = p.with_name('wrong.zip'); p.rename(wrong)
        with self.assertRaises(ValueError): integrity.validate(wrong)


if __name__ == '__main__': unittest.main()
