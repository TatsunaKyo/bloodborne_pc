# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Exercise release preparation and malformed package rejection with real ZIPs."""
import hashlib
import importlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
integrity = importlib.import_module('release_integrity')
prepare = importlib.import_module('prepare_release').prepare


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
        data.update({name:b'fixture' for name in integrity.DATA})
        data['source/modified-files/launcher/bbport_launcher_win.py'] = f'VERSION = {version!r}\n'.encode()
        data[f'docs/releases/windows-v{version}.md'] = b'# Workshop revision\n\nI kept the settings shared.\n'
        identity = {'version':version, 'source_commit':'1'*40, 'source_tree':'2'*40,
                    'release_tag':'windows-v'+version, 'channel':'stable',
                    'executables':{name:hashlib.sha256(data[name]).hexdigest() for name in integrity.CORE},
                    'runtime_files':{name:hashlib.sha256(data[name]).hexdigest() for name in integrity.RUNTIMES+('_internal/python314.dll',)}}
        if modify: modify(identity, data)
        data['BUILD-IDENTITY.json'] = json.dumps(identity).encode()
        path = self.root/integrity.package_name(version)
        with zipfile.ZipFile(path, 'w') as archive:
            for name, value in data.items(): archive.writestr('Workshop/'+name, value)
            for name, value in extra or []: archive.writestr(name, value)
        return path

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

    def test_wrong_binary_architecture_even_with_matching_hash(self):
        def mutation(identity, data):
            data['Bloodborne.exe'] = b'not a Windows program'
            identity['executables']['Bloodborne.exe'] = hashlib.sha256(data['Bloodborne.exe']).hexdigest()
        with self.assertRaises(ValueError): integrity.validate(self.package(modify=mutation))

    def test_path_traversal_multiple_roots_duplicates_and_game_files(self):
        for name in ('Workshop/../evil', 'Workshop/C:/evil', 'Workshop/eboot.bin',
                     'Other/extra', 'Workshop/README.MD', 'Workshop/dir\\evil'):
            with self.subTest(name=name), self.assertRaises(ValueError): integrity.validate(self.package(extra=[(name,b'x')]))

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
