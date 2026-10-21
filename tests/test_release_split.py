# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Verify both archives retain their contents, dependencies and update compatibility."""
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import test_release_integrity as fixtures
from release_integrity import validate, validate_developer, checksum
from split_release import split, write_zip, DIAGNOSTICS
from prepare_release import prepare


class SplitRelease(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.Releases(); self.fixture.setUp(); self.addCleanup(self.fixture.tmp.cleanup)
        self.folder = self.fixture.root / 'exports'

    def complete(self):
        def add(identity, data):
            data['bin/regression-test.exe'] = fixtures.pe()
            identity['executables']['bin/regression-test.exe'] = hashlib.sha256(data['bin/regression-test.exe']).hexdigest()
            data['source/verification/test.log'] = b'PASS: genuine test record fixture\n'
            data['source/modified-files/docs/art.png'] = bytes(range(256)) * 32
            data['source/tatsunakyo-revision.patch'] = b'complete source fixture\n'
            data['docs/assets/art.png'] = data['source/modified-files/docs/art.png']
            for name in DIAGNOSTICS:
                data[name] = b'@echo off\ncd /d "%~dp0"\n"%~dp0Bloodborne.exe" --play --geometry-diagnostic=normal\npause\n'
        return self.fixture.package(modify=add)

    def test_modern_revisions_cannot_create_split_deliverables(self):
        original = self.fixture.package('1.6-tatsunakyo.55')
        digest = checksum(original)
        with self.assertRaisesRegex(ValueError, 'one complete ZIP'):
            split(original, self.folder)
        self.assertFalse(self.folder.exists())
        self.assertEqual(checksum(original), digest)

    def test_runtime_stays_valid_and_all_original_content_is_preserved(self):
        original = self.complete(); original_sha = checksum(original)
        result = split(original, self.folder)
        runtime, developer = Path(result['runtime']), Path(result['developer'])
        report = validate(runtime, require_sidecar=True)
        self.assertNotIn('bin/regression-test.exe', report['identity']['executables'])
        self.assertEqual(report['identity']['developer_bundle']['sha256'], checksum(developer))
        with zipfile.ZipFile(original) as old, zipfile.ZipFile(runtime) as regular, zipfile.ZipFile(developer) as dev:
            for name in old.namelist():
                relative = name.removeprefix('Workshop/')
                if relative == 'BUILD-IDENTITY.json': target = 'Workshop-Developer/ORIGINAL-BUILD-IDENTITY.json'; archive = dev
                elif relative in DIAGNOSTICS: target = 'Workshop-Developer/diagnostics/originals/' + relative + '.txt'; archive = dev
                elif name in regular.namelist(): target = name; archive = regular
                else: target = 'Workshop-Developer/' + relative; archive = dev
                self.assertEqual(old.read(name), archive.read(target), relative)
            for name in DIAGNOSTICS:
                body = dev.read('Workshop-Developer/diagnostics/' + name).decode()
                self.assertIn('WORKSHOP_PORT', body)
                self.assertNotIn('"%~dp0Bloodborne.exe"', body)
            self.assertIsNone(regular.testzip()); self.assertIsNone(dev.testzip())
        self.assertEqual(checksum(original), original_sha)
        result = prepare(runtime)
        self.assertIn(developer.name, result['body'])
        self.assertEqual(result['developer_bundle']['sha256'], checksum(developer))

    def test_existing_outputs_are_not_overwritten(self):
        original = self.complete(); self.folder.mkdir()
        output = self.folder / original.name; output.write_bytes(b'previous candidate')
        with self.assertRaisesRegex(ValueError, 'Output already exists'): split(original, self.folder)
        self.assertEqual(output.read_bytes(), b'previous candidate')

    def test_interrupted_export_leaves_the_complete_input_and_no_partial_archives(self):
        original = self.complete(); before = checksum(original)
        from split_release import write_zip
        writes = [0]
        def interrupted(path, root, entries, **kwargs):
            writes[0] += 1
            if writes[0] == 1: return write_zip(path, root, entries, **kwargs)
            path.write_bytes(b'partial ZIP')
            raise OSError('fixture interrupted write')
        with patch('split_release.write_zip', side_effect=interrupted):
            with self.assertRaises(OSError): split(original, self.folder)
        self.assertEqual(checksum(original), before)
        self.assertFalse(list(self.folder.glob('*.zip*')))

    def test_missing_or_corrupted_companion_cannot_prepare_a_release(self):
        result = split(self.complete(), self.folder)
        runtime, developer = Path(result['runtime']), Path(result['developer'])
        data = developer.read_bytes(); developer.unlink()
        with self.assertRaisesRegex(ValueError, 'missing or renamed'): prepare(runtime)
        developer.write_bytes(data[:-10])
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'): prepare(runtime)

    def test_companion_identity_and_paths_are_checked_independently_of_its_hash(self):
        result = split(self.complete(), self.folder)
        runtime, developer = Path(result['runtime']), Path(result['developer'])
        report = validate(runtime)
        with zipfile.ZipFile(developer) as archive:
            entries = {name: archive.read(name) for name in archive.namelist()}
        def rewrite(changed):
            with zipfile.ZipFile(developer, 'w') as archive:
                for name, data in changed.items(): fixtures.raw_member(archive, name, data)
            sha = checksum(developer)
            developer.with_suffix('.zip.sha256').write_text(sha + '  ' + developer.name + '\n')
            report['identity']['developer_bundle']['sha256'] = sha
        broken = dict(entries)
        key = 'Workshop-Developer/DEVELOPER-IDENTITY.json'
        identity = json.loads(broken[key]); identity['source_commit'] = 'f' * 40
        broken[key] = json.dumps(identity).encode(); rewrite(broken)
        with self.assertRaisesRegex(ValueError, 'build identity disagrees'):
            validate_developer(developer, report, require_sidecar=True)
        for name in ('Workshop-Developer/../outside.txt', 'Workshop-Developer/dir\\evil',
                     'Workshop-Developer/extra\x00hidden'):
            broken = dict(entries); broken[name] = b'bad'; rewrite(broken)
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'Unsafe archive path'):
                validate_developer(developer, report, require_sidecar=True)

    def test_only_undeclared_copies_of_known_libraries_leave_the_game_package(self):
        temporary = 'bin/xess/.libxess.dll.Abc123'
        declared = 'bin/xess/.libxess.dll.Keep12'
        unknown = 'bin/xess/.other.dll.Abc123'
        def add(identity, data):
            data[temporary] = data['bin/xess/libxess.dll'][:100]
            data[declared] = data['bin/xess/libxess.dll']
            identity['runtime_files'][declared] = hashlib.sha256(data[declared]).hexdigest()
            data[unknown] = b'unknown file kept for review'
        original = self.fixture.package(modify=add)
        result = split(original, self.folder)
        with zipfile.ZipFile(original) as old, zipfile.ZipFile(result['runtime']) as regular, zipfile.ZipFile(result['developer']) as dev:
            self.assertNotIn('Workshop/' + temporary, regular.namelist())
            self.assertEqual(dev.read('Workshop-Developer/' + temporary), old.read('Workshop/' + temporary))
            for name in (declared, unknown, 'bin/xess/libxess.dll'):
                self.assertEqual(regular.read('Workshop/' + name), old.read('Workshop/' + name))
        validate(Path(result['runtime']), require_sidecar=True)

    def test_both_companions_receive_the_same_reproducible_timestamp(self):
        original = self.complete()
        with patch.dict(os.environ, {'SOURCE_DATE_EPOCH': '1792014307'}):
            first = split(original, self.folder / 'first')
            second = split(original, self.folder / 'second')
        self.assertEqual(first['archive_timestamp_utc'], '2026-10-14T21:45:07Z')
        for kind in ('runtime', 'developer'):
            self.assertEqual(checksum(Path(first[kind])), checksum(Path(second[kind])))
            with zipfile.ZipFile(first[kind]) as archive:
                self.assertTrue(archive.infolist())
                for info in archive.infolist():
                    # DOS ZIP dates have two-second precision. Keep writable
                    # Windows attributes as well as the date in both headers.
                    self.assertEqual(info.date_time, (2026, 10, 14, 21, 45, 6))
                    self.assertEqual(info.create_system, 0)
                    self.assertEqual(info.external_attr, 0x20)
                info = archive.infolist()[0]
                raw = Path(first[kind]).read_bytes()
                dos_time, dos_date = struct.unpack_from('<HH', raw, info.header_offset + 10)
                self.assertEqual(dos_time, (21 << 11) | (45 << 5) | 3)
                self.assertEqual(dos_date, ((2026 - 1980) << 9) | (10 << 5) | 14)
                self.assertIsNone(archive.testzip())

    def test_invalid_epoch_does_not_leave_an_export(self):
        original = self.complete()
        for value in ('', 'not a timestamp', '-1', '0', '4354819200'):
            with self.subTest(value=value), patch.dict(os.environ, {'SOURCE_DATE_EPOCH': value}):
                with self.assertRaisesRegex(ValueError, 'Archive timestamp'):
                    split(original, self.folder)
            self.assertFalse(list(self.folder.glob('*.zip*')))

    def test_verified_checkout_supplies_the_source_commit_date(self):
        original = self.complete()
        from release_integrity import validate as real_validate
        with patch.dict(os.environ, {}, clear=True), \
             patch('split_release.validate', side_effect=lambda path, **kw:
                   real_validate(path, require_sidecar=kw.get('require_sidecar', False))), \
             patch('split_release.subprocess.check_output', return_value='1792014307\n') as git:
            result = split(original, self.folder, repo=self.fixture.root)
        git.assert_called_once_with(['git', 'show', '-s', '--format=%ct', '1' * 40],
                                    cwd=self.fixture.root, text=True)
        self.assertEqual(result['archive_timestamp_utc'], '2026-10-14T21:45:07Z')


class ArchiveTimestamps(unittest.TestCase):
    def test_standalone_writer_uses_current_build_time_instead_of_1980(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True), \
             patch('split_release.time.time', return_value=1792014307):
            package = Path(folder) / 'build.zip'
            write_zip(package, 'Workshop', {'Bloodborne.exe': b'fixture'})
            with zipfile.ZipFile(package) as archive:
                self.assertEqual(archive.infolist()[0].date_time, (2026, 10, 14, 21, 45, 6))
            self.assertEqual(package.with_suffix('.zip.sha256').read_text(),
                             checksum(package) + '  build.zip\n')


if __name__ == '__main__': unittest.main()
