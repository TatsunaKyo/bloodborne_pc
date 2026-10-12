# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Privacy, bounded collection and actual ZIP failure/recovery regressions."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import support_report as reports


SYSTEM = {'os': {'name': 'Windows 11', 'version': '10.0.26100', 'build': '26100'},
          'gpus': [{'model': 'NVIDIA GeForce RTX 5070 Ti', 'driver_version': '32.0.15.8123',
                    'device_id': 'PRIVATE DEVICE ID'}],
          'hardware_profile': {'cpu_model': ['AMD Ryzen 7 7800X3D'], 'ram_gib': 64,
                               'logical_processors': 16, 'serial': 'PRIVATE SERIAL'},
          'registered_user': 'PRIVATE OWNER'}


class SupportReports(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='workshop-report-')
        self.root = Path(self.temp.name)
        self.port, self.user = self.root / 'port', self.root / 'custom user'
        self.port.mkdir(); self.user.mkdir()
        self.app = {'hdr': True, 'present_mode': 'Immediate', 'real_fps_limit': '75',
                    'game_dir': r'G:\Personal Games\Bloodborne', 'online_password': 'swordfish-private',
                    'online_npid': 'SecretHunter91', 'player_name': 'PrivatePlayer',
                    'extra_env': 'TOKEN=never-include-this', 'backup_folder': r'X:\Private Backups'}
        self.ini = {'upscaler': 'dlss', 'preset': '3', 'output_res': '3840x2160'}
        self.menu = {'frame_generation': 'nvidia', 'nvidia_generated_frames': '1',
                     'generated_fps_limit': '120', 'limit_generated_fps': '1',
                     'reflex': 'on', 'window_mode': 'borderless', 'dlss_preset': 'l'}
        self.identity = {'project': 'Bloodborne: The Crowned Workshop', 'version': '1.6-tatsunakyo.23',
                         'source_commit': 'a' * 40, 'executables': {'Bloodborne.exe': 'b' * 64},
                         'source_directory': r'C:\Users\PrivateOwner\Source', 'token': 'PRIVATE BUILD TOKEN'}
        (self.port / 'BUILD-IDENTITY.json').write_text(json.dumps(self.identity))

    def tearDown(self):
        self.temp.cleanup()

    def report(self, **kwargs):
        return reports.build_report(self.port, self.user, self.app, self.ini, self.menu,
                                    '1.6-tatsunakyo.23', system=SYSTEM, **kwargs)

    def session(self, name='recent', text='', metadata=None):
        folder = self.user / 'diagnostics' / name
        folder.mkdir(parents=True)
        (folder / 'session.log').write_text(text, encoding='utf-8')
        (folder / 'session.json').write_text(json.dumps(metadata or {
            'revision': '1.6-tatsunakyo.23', 'status': 'exited', 'exit_code': 0,
            'duration_seconds': 16.5, 'settings': self.app, 'ini': self.ini, 'menu_at_exit': self.menu}),
            encoding='utf-8')
        return folder

    def all_text(self, report):
        return '\n'.join(data.decode('utf-8') for data in report.entries.values())

    def test_actual_selected_device_and_existing_timings(self):
        self.session(text='[0.1s] GPU_Model: NVIDIA GeForce RTX 5070 Ti\n'
                          '[0.2s] GPU_Vulkan_Driver: NVIDIA 581.23\n'
                          '[5.0s] Frames: fps=75.0 avg=13.33ms p99=17.2ms\n')
        report = self.report()
        data = json.loads(report.entries['report.json'])
        self.assertEqual(data['renderer']['gpu'], 'NVIDIA GeForce RTX 5070 Ti')
        self.assertEqual(data['renderer']['driver'], 'NVIDIA 581.23')
        self.assertEqual(data['renderer']['source'], 'latest available session log')
        metrics = json.loads(report.entries['performance.json'])['observations']
        self.assertEqual(len(metrics), 1)
        self.assertIn('p99=17.2ms', metrics[0]['text'])

    def test_missing_logs_and_identity_still_export(self):
        (self.port / 'BUILD-IDENTITY.json').unlink()
        report = self.report()
        self.assertEqual(len(report.warnings), 2)
        target = self.root / 'report.zip'
        reports.export_report(report, target)
        self.assertTrue(reports.verify_report(target))

    def test_credentials_headers_and_continuations_removed(self):
        self.session(text='Authorization: Bearer unlisted-token\n  another-secret\n'
                          '[1.0s] Runtime: running\n'
                          'online_password: swordfish-private\n'
                          'NPID=SecretHunter91\n'
                          '[2.0s] Frames: fps=75\n'
                          'user_name = PrivatePlayer\n')
        text = self.all_text(self.report())
        for secret in ('unlisted-token', 'another-secret', 'swordfish-private', 'SecretHunter91',
                       'PrivatePlayer', 'never-include-this'):
            self.assertNotIn(secret, text)
        self.assertIn('Frames: fps=75', text)

    def test_custom_windows_paths_unicode_unc_and_accounts(self):
        self.session(text='Runtime: loading G:\\Personal Games\\Bloodborne\\SecretHunter91\\asset.bin\n'
                          'Runtime: failed C:\\Users\\Алексей\\Private Documents\\save.dat\n'
                          'Runtime: share \\\\PrivateServer\\Users\\Alice\\record.json\n'
                          'Runtime: contact person@example.com at https://server/?token=private\n'
                          'Runtime: id S-1-5-21-1234-5678-9999-1001 / 76561198012345678\n')
        text = self.all_text(self.report())
        for private in ('Personal Games', 'Алексей', 'Private Documents', 'PrivateServer', 'Alice',
                        'person@example.com', 'S-1-5-21', '76561198012345678', 'token=private'):
            self.assertNotIn(private, text)

    def test_build_identity_uses_known_binary_names(self):
        self.identity['executables'][r'C:\Users\Alice\Alice-private.exe'] = 'c' * 64
        (self.port / 'BUILD-IDENTITY.json').write_text(json.dumps(self.identity))
        data = json.loads(self.report().entries['build-identity.json'])
        self.assertEqual(data['binary_sha256'], {'Bloodborne.exe': 'b' * 64})
        self.assertNotIn('source_directory', data)
        self.assertNotIn('token', data)

    def test_profile_is_optional_and_submission_never_confirmed(self):
        basic = self.report()
        self.assertNotIn('hardware-submission.json', basic.entries)
        self.assertNotIn('7800X3D', self.all_text(basic))
        profile = self.report(include_profile=True)
        self.assertIn('7800X3D', self.all_text(profile))
        self.assertNotIn('PRIVATE SERIAL', self.all_text(profile))
        self.assertNotIn('PRIVATE OWNER', self.all_text(profile))
        self.assertNotIn('PRIVATE DEVICE ID', self.all_text(profile))
        data = json.loads(profile.entries['hardware-submission.json'])
        self.assertTrue(reports.validate_hardware_submission(data))
        data.update(reviewed=True, status='tested')
        with self.assertRaises(ValueError):
            reports.validate_hardware_submission(data)

    def test_game_save_dump_capture_and_other_json_never_collected(self):
        folder = self.session(text='Runtime: normal exit\n')
        for path in [folder / 'crash.dmp', folder / 'private.json', folder / 'scene_output.raw',
                     self.user / 'userdata0010', self.port / 'eboot.bin']:
            path.write_bytes(b'PRIVATE FILE CONTENT')
        text = self.all_text(self.report())
        self.assertNotIn('PRIVATE FILE CONTENT', text)
        self.assertNotIn('crash.dmp', text)

    def test_malformed_binary_and_json_logs(self):
        folder = self.session()
        (folder / 'session.json').write_text('{broken "online_password": "PRIVATE JSON"')
        (folder / 'session.log').write_bytes(b'Runtime: invalid utf8\xff\x00\nFrames: fps=74\n')
        report = self.report()
        self.assertNotIn('sessions/session-1/session.json', report.entries)
        self.assertNotIn('PRIVATE JSON', self.all_text(report))
        self.assertIn('Frames: fps=74', self.all_text(report))
        self.assertTrue(any('malformed' in w for w in report.warnings))

    def test_recent_limit_and_oversized_log_retains_startup_and_tail(self):
        for number in range(5):
            folder = self.session(str(number), text=f'Runtime: {number}\n')
            os.utime(folder, (100 + number, 100 + number))
        newest = self.user / 'diagnostics/4/session.log'
        newest.write_text('GPU_Model: Test GPU\n' + 'old frame\n' * 100000 + 'Frames: fps=70\n')
        report = self.report()
        self.assertEqual(len([n for n in report.entries if n.endswith('/session.log')]), 3)
        log = report.entries['sessions/session-1/session.log']
        self.assertLess(len(log), reports.MAX_LOG + 256)
        self.assertIn(b'GPU_Model: Test GPU', log)
        self.assertIn(b'Frames: fps=70', log)

    def test_symlinked_logs_and_sessions_are_excluded(self):
        folder = self.session()
        outside = self.root / 'private.log'
        outside.write_text('PRIVATE OUTSIDE CONTENT')
        (folder / 'session.log').unlink()
        try:
            (folder / 'session.log').symlink_to(outside)
        except OSError:
            self.skipTest('Symlink creation unavailable on this host.')
        self.assertNotIn('PRIVATE OUTSIDE CONTENT', self.all_text(self.report()))

    def test_settings_reject_untrusted_keys_and_values(self):
        self.app.update(online_password='keep-out', extra_env='COOKIE=secret', frames_ahead='C:\\Users\\Bob',
                        hdr={'password': 'keep-out'}, real_fps_limit='NaN')
        self.ini.update(upscaler='my-secret-account', sharpness='Infinity')
        fields = json.loads(self.report().entries['report.json'])['selected_settings']
        self.assertNotIn('online_password', fields['launcher'])
        self.assertNotIn('frames_ahead', fields['launcher'])
        self.assertNotIn('hdr', fields['launcher'])
        self.assertNotIn('upscaler', fields['image'])
        self.assertNotIn('sharpness', fields['image'])

    def test_logs_can_be_excluded_before_inspection(self):
        self.session(text='Runtime: recorded data\n')
        report = self.report(include_logs=False)
        self.assertFalse(any(name.endswith('.log') for name in report.entries))
        self.assertEqual(json.loads(report.entries['performance.json'])['observations'], [])

    def test_archive_checksum_manifest_and_safe_names(self):
        report = self.report(include_profile=True)
        target = self.root / 'report.zip'
        reports.export_report(report, target)
        with zipfile.ZipFile(target) as archive:
            self.assertIsNone(archive.testzip())
            manifest = json.loads(archive.read('manifest.json'))
            for record in manifest['files']:
                self.assertEqual(record['sha256'], hashlib.sha256(archive.read(record['path'])).hexdigest())
        with zipfile.ZipFile(target, 'a') as archive:
            archive.writestr('../private.log', 'outside')
        with self.assertRaises(ValueError):
            reports.verify_report(target)

    def test_tampered_content_is_rejected(self):
        report = self.report()
        report.entries['report.json'] = b'{}'
        target = self.root / 'report.zip'
        target.write_bytes(b'previous export')
        with self.assertRaises(ValueError):
            reports.export_report(report, target)
        self.assertEqual(target.read_bytes(), b'previous export')

    def test_interrupted_export_keeps_previous_file_and_cleans_partial(self):
        target = self.root / 'report.zip'
        target.write_bytes(b'previous export')
        with patch.object(zipfile.ZipFile, 'writestr', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                reports.export_report(self.report(), target)
        self.assertEqual(target.read_bytes(), b'previous export')
        self.assertEqual(list(self.root.glob('.support-report-*.partial')), [])

    def test_terminated_export_never_publishes_partial_archive(self):
        target = self.root / 'report.zip'
        target.write_bytes(b'previous export')
        script = ('import os,support_report as s;from pathlib import Path;'
                  f'r=s.build_report({str(self.port)!r},{str(self.user)!r},{{}},{{}},{{}},"test",system={{}});'
                  'os.replace=lambda *a:os._exit(19);'
                  f's.export_report(r,{str(target)!r})')
        environment = {**os.environ, 'PYTHONPATH': str(Path(reports.__file__).parent)}
        result = subprocess.run([sys.executable, '-c', script], env=environment, timeout=20)
        self.assertEqual(result.returncode, 19)
        self.assertEqual(target.read_bytes(), b'previous export')
        partials = list(self.root.glob('.support-report-*.partial'))
        self.assertEqual(len(partials), 1)
        reports.export_report(self.report(), target)
        self.assertTrue(reports.verify_report(target))


if __name__ == '__main__':
    unittest.main()
