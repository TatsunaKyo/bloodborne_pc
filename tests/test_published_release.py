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
from verify_published_release import verify, wait_for_assets, main
from split_release import split
import test_release_integrity as fixtures


class PublishedRelease(unittest.TestCase):
    def setUp(self):
        fixture=fixtures.Releases();fixture.setUp();self.addCleanup(fixture.tmp.cleanup)
        self.fixture=fixture
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

    def test_publication_race_waits_for_both_assets_without_a_real_delay(self):
        waiting = copy.deepcopy(self.release); waiting['assets'] = []
        halfway = copy.deepcopy(self.release); halfway['assets'].pop()
        times = [0]
        def pause(seconds): times[0] += seconds
        sequence = iter((halfway, self.release))
        result = wait_for_assets(waiting, lambda: next(sequence), 15,
                                 clock=lambda: times[0], pause=pause)
        self.assertEqual(result, self.release)
        self.assertEqual(times[0], 10)

    def test_missing_assets_fail_at_deadline_and_duplicates_do_not_wait(self):
        missing = copy.deepcopy(self.release); missing['assets'] = []
        times = [0]
        def pause(seconds): times[0] += seconds
        with self.assertRaisesRegex(ValueError, 'Upload the ZIP and matching SHA-256'):
            wait_for_assets(missing, lambda: missing, 7, clock=lambda: times[0], pause=pause)
        self.assertEqual(times[0], 7)
        duplicate = copy.deepcopy(self.release); duplicate['assets'].append(duplicate['assets'][0])
        with self.assertRaisesRegex(ValueError, 'Duplicate release asset'):
            wait_for_assets(duplicate, lambda: self.release, 10)

    def test_wait_rejects_release_switch_and_excessive_wait(self):
        missing = copy.deepcopy(self.release); missing['assets'] = []
        other = copy.deepcopy(self.release); other['tag_name'] = 'windows-v1.6-tatsunakyo.22'
        with self.assertRaisesRegex(ValueError, 'Release changed'):
            wait_for_assets(missing, lambda: other, 10, clock=lambda: 0, pause=lambda seconds: None)
        with self.assertRaises(ValueError): wait_for_assets(self.release, lambda: self.release, 301)

    def test_failed_cli_retains_a_structured_record_for_ci(self):
        output = self.downloads / 'failure.json'
        with patch('sys.argv', ['verify_published_release', '--output', str(output)]), \
             patch('verify_published_release.urllib.request.urlopen', side_effect=OSError('fixture network unavailable')):
            with self.assertRaises(SystemExit) as stop: main()
        self.assertEqual(stop.exception.code, 1)
        result = json.loads(output.read_text())
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['error_type'], 'OSError')

    def test_split_publication_checks_both_archives_and_sidecars(self):
        result = split(self.package, self.fixture.root / 'split')
        package, developer = Path(result['runtime']), Path(result['developer'])
        sources = {p.name: p for p in (package, package.with_suffix('.zip.sha256'),
                                      developer, developer.with_suffix('.zip.sha256'))}
        release = copy.deepcopy(self.release); release['assets'] = []
        for name, path in sources.items():
            release['assets'].append({'name': name, 'state': 'uploaded', 'size': path.stat().st_size,
                'digest': 'sha256:' + checksum(path),
                'browser_download_url': 'https://github.com/TatsunaKyo/bloodborne_pc/releases/download/' +
                    release['tag_name'] + '/' + name})
        def fetch(url, path): shutil.copy2(sources[path.name], path)
        report = verify(release, self.downloads, fetch=fetch)
        self.assertEqual(report['developer_bundle']['sha256'], checksum(developer))
        missing = copy.deepcopy(release); missing['assets'].pop()
        with self.assertRaisesRegex(ValueError, 'Expected one uploaded asset'):
            verify(missing, self.downloads, fetch=fetch)
        developer.write_bytes(b'corrupted upload')
        for record in release['assets']:
            if record['name'] == developer.name:
                record.update(size=developer.stat().st_size, digest='sha256:' + checksum(developer))
        with self.assertRaisesRegex(ValueError, 'Developer bundle checksum mismatch'):
            verify(release, self.downloads, fetch=fetch)

    def test_companion_uploads_use_the_same_bounded_wait(self):
        expected = ('optional-Developer.zip', 'optional-Developer.zip.sha256')
        waiting = copy.deepcopy(self.release)
        ready = copy.deepcopy(waiting)
        ready['assets'] += [{'name': name, 'state': 'uploaded'} for name in expected]
        times = [0]
        result = wait_for_assets(waiting, lambda: ready, 10, expected_names=expected,
                                 clock=lambda: times[0], pause=lambda seconds: times.__setitem__(0, times[0] + seconds))
        self.assertEqual(result, ready); self.assertEqual(times[0], 5)


if __name__=='__main__':unittest.main()
