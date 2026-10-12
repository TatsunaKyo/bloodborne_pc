# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Verify publication metadata against downloaded archive bytes, without network access."""
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from release_integrity import checksum
from verify_published_release import verify
import test_release_integrity as fixtures


class PublishedRelease(unittest.TestCase):
    def setUp(self):
        fixture=fixtures.Releases();fixture.setUp();self.addCleanup(fixture.tmp.cleanup)
        self.package=fixture.package('1.6-tatsunakyo.21')
        self.sidecar=self.package.with_suffix('.zip.sha256')
        self.sidecar.write_text(checksum(self.package)+'  '+self.package.name+'\n')
        self.release=json.loads((ROOT/'tests/fixtures/release21-stable.json').read_text())
        for record,path in zip(self.release['assets'],(self.package,self.sidecar)):
            record.update(size=path.stat().st_size,digest='sha256:'+checksum(path))
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.downloads=Path(tmp.name)

    def fetch(self,url,path):
        source=self.sidecar if url.endswith('.sha256') else self.package
        shutil.copy2(source,path)

    def test_legacy_stable_and_actual_preview_metadata(self):
        result=verify(self.release,self.downloads,fetch=self.fetch)
        self.assertTrue(result['legacy_stable_preview_tag'])
        self.assertFalse(result['prerelease']);self.assertTrue(result['published'])
        preview=copy.deepcopy(self.release);preview['prerelease']=True
        result=verify(preview,self.downloads,fetch=self.fetch)
        self.assertTrue(result['prerelease']);self.assertFalse(result['legacy_stable_preview_tag'])

    def test_uploaded_bytes_must_match_size_and_github_digest(self):
        for field,value in (('size',0),('digest','sha256:'+'0'*64)):
            release=copy.deepcopy(self.release);release['assets'][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                verify(release,self.downloads,fetch=self.fetch)

    def test_checksum_sidecar_is_verified_independently(self):
        self.sidecar.write_text('0'*64+'  '+self.package.name+'\n')
        self.release['assets'][1].update(size=self.sidecar.stat().st_size,digest='sha256:'+checksum(self.sidecar))
        with self.assertRaises(ValueError):verify(self.release,self.downloads,fetch=self.fetch)

    def test_missing_duplicate_unready_and_foreign_assets_rejected(self):
        def foreign(r):r['assets'][0]['browser_download_url']=r['assets'][0]['browser_download_url'].replace('tatsunakyo.21-preview','tatsunakyo.20-preview')
        mutations=[lambda r:r['assets'].pop(),lambda r:r['assets'].append(r['assets'][0]),
                   lambda r:r['assets'][0].update(state='new'),foreign,
                   lambda r:r.update(assets={}),lambda r:r.update(draft=True),lambda r:r.update(tag_name=None)]
        for mutation in mutations:
            release=copy.deepcopy(self.release);mutation(release)
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                verify(release,self.downloads,fetch=self.fetch)

    def test_public_tag_must_point_to_the_package_source(self):
        with patch('verify_published_release.validate',return_value={'source_commit':'1'*40,'notes':'notes'}), \
             patch('subprocess.check_output',return_value='2'*40+'\n'):
            with self.assertRaisesRegex(ValueError,'source commit disagree'):
                verify(self.release,self.downloads,repo=ROOT,fetch=self.fetch)


if __name__=='__main__':unittest.main()
