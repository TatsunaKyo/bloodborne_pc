# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Verify both archives retain their contents, dependencies and update compatibility."""
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import test_release_integrity as fixtures
from release_integrity import validate, checksum
from split_release import split, DIAGNOSTICS


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

    def test_existing_outputs_are_not_overwritten(self):
        original = self.complete(); self.folder.mkdir()
        output = self.folder / original.name; output.write_bytes(b'previous candidate')
        with self.assertRaisesRegex(ValueError, 'Output already exists'): split(original, self.folder)
        self.assertEqual(output.read_bytes(), b'previous candidate')

    def test_interrupted_export_leaves_the_complete_input_and_no_partial_archives(self):
        original = self.complete(); before = checksum(original)
        with patch('split_release.write_zip', side_effect=OSError('fixture interrupted write')):
            with self.assertRaises(OSError): split(original, self.folder)
        self.assertEqual(checksum(original), before)
        self.assertFalse(list(self.folder.glob('*.zip*')))


if __name__ == '__main__': unittest.main()
