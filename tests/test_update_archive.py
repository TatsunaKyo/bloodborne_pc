# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Verify the launcher's actual downloaded-update gate with altered release ZIPs."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
import test_release_integrity as fixtures
integrity = fixtures.integrity

if len(sys.argv) > 1:
    import marshal
    import types
    from PyInstaller.archive.readers import CArchiveReader
    executable = sys.argv.pop(1)
    launcher = types.ModuleType('verified_update_launcher')
    launcher.__file__ = str(ROOT / 'launcher/bbport_launcher_win.py')
    exec(marshal.loads(CArchiveReader(executable).extract('bbport_launcher_win')), launcher.__dict__)
else:
    spec = importlib.util.spec_from_file_location('verified_update_launcher', ROOT / 'launcher/bbport_launcher_win.py')
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)


class UpdateArchive(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.Releases()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def verify(self, path, version='1.6-tatsunakyo.22', sidecar=None):
        sidecar = sidecar if sidecar is not None else integrity.checksum(path) + '  ' + path.name + '\n'
        return launcher.verify_update_archive(path, version, sidecar)

    def test_valid_legacy_and_current_release_formats(self):
        for version in ('1.6-tatsunakyo.21', '1.6-tatsunakyo.25', '1.7-tatsunakyo.1'):
            path = self.fixture.package(version)
            self.assertEqual(self.verify(path, version), 'Workshop')

    def test_corrupt_or_missing_checksum(self):
        path = self.fixture.package()
        for text in ('', '0' * 64 + '  ' + path.name, integrity.checksum(path) + '  wrong.zip',
                     'x' * 4097, None):
            with self.subTest(text=str(text)[:20]), self.assertRaises(ValueError):
                launcher.verify_update_archive(path, '1.6-tatsunakyo.22', text)

    def test_recomputed_checksum_cannot_hide_altered_binary(self):
        path = self.fixture.package(modify=lambda i, d: d.update({'Bloodborne.exe': b'altered'}))
        with self.assertRaises(ValueError):
            self.verify(path)

    def test_wrong_identity_and_missing_runtime(self):
        for mutate in (lambda i, d: i.update(source_commit='bad'),
                       lambda i, d: d.pop('bin/streamline/sl.reflex.dll'),
                       lambda i, d: i.update(release_tag=42)):
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                self.verify(self.fixture.package(modify=mutate))
        with self.assertRaises(ValueError):
            self.verify(self.fixture.package(), '1.6-tatsunakyo.25')

    def test_unsafe_paths_rejected_before_extraction(self):
        for path in ('Workshop/../outside', 'Workshop/NUL.txt', 'Workshop/README.md.', 'Workshop/README.MD'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.verify(self.fixture.package(extra=[(path, b'x')]))

    def test_correctly_hashed_truncated_zip_still_rejected(self):
        import zipfile
        path = self.fixture.package()
        path.write_bytes(path.read_bytes()[:-30])
        with self.assertRaises(zipfile.BadZipFile):
            self.verify(path)

    def test_update_worker_verifies_before_candidate_execution(self):
        import io
        import queue
        import types
        for accepted in (False, True):
            with self.subTest(accepted=accepted):
                package = self.fixture.package()
                staging = self.fixture.root / ('accepted' if accepted else 'rejected')
                staging.mkdir()
                checksum = integrity.checksum(package) if accepted else '0' * 64
                replies = [package.read_bytes(), (checksum + '  ' + package.name + '\n').encode()]
                errors, closed = [], []
                obj = types.SimpleNamespace(process=None, ui_calls=queue.SimpleQueue(),
                    messagebox=types.SimpleNamespace(askyesno=lambda *a: True, showerror=lambda *a: errors.append(a)),
                    update_button=types.SimpleNamespace(configure=lambda **kw: None),
                    update_label=types.SimpleNamespace(configure=lambda **kw: None),
                    root=types.SimpleNamespace(destroy=lambda: closed.append(True)))

                class Thread:
                    def __init__(self, *, target, daemon): self.target = target
                    def start(self): self.target()

                def response(*args, **kwargs):
                    value = io.BytesIO(replies.pop(0))
                    value.headers = {'Content-Length': str(value.getbuffer().nbytes)}
                    return value

                original_mkdtemp = launcher.tempfile.mkdtemp
                def make_stage(*args, **kwargs):
                    return str(staging) if kwargs.get('prefix') == 'crowned-workshop-update-' else original_mkdtemp(*args, **kwargs)

                with patch.object(launcher, 'FROZEN', True), \
                     patch.object(launcher.threading, 'Thread', Thread), \
                     patch.object(launcher.tempfile, 'mkdtemp', side_effect=make_stage), \
                     patch.object(launcher.urllib.request, 'urlopen', side_effect=response), \
                     patch.object(launcher.subprocess, 'Popen') as execute:
                    launcher.Launcher.install_update(obj, '1.6-tatsunakyo.22', 'https://example.invalid/' + package.name,
                                                    'https://example.invalid/release')
                    while not obj.ui_calls.empty(): obj.ui_calls.get()()
                    self.assertEqual(execute.call_count, int(accepted))
                    self.assertEqual(bool(closed), accepted)
                    self.assertEqual(bool(errors), not accepted)
                    if accepted:
                        self.assertEqual(Path(execute.call_args.args[0][0]), staging / 'new/Workshop/Bloodborne.exe')
                    else:
                        self.assertFalse(staging.exists())

    def test_previous_launcher_wait_checks_results_and_preserves_64_bit_handles(self):
        import ctypes
        import types
        from unittest.mock import Mock
        handle = 0x100000001
        for opened, wait, error, expected in ((handle, 0, 0, True), (handle, 258, 0, False),
                                             (handle, 0xffffffff, 0, False), (None, 0, 87, True), (None, 0, 5, False)):
            with self.subTest(opened=opened, wait=wait, error=error):
                api = types.SimpleNamespace(OpenProcess=Mock(return_value=opened),
                    WaitForSingleObject=Mock(return_value=wait), CloseHandle=Mock(), GetLastError=Mock(return_value=error))
                with patch.object(launcher.ctypes, 'windll', types.SimpleNamespace(kernel32=api), create=True):
                    self.assertEqual(launcher.wait_for_previous_launcher(123), expected)
                self.assertIs(api.OpenProcess.restype, ctypes.c_void_p)
                if opened:
                    api.WaitForSingleObject.assert_called_once_with(handle, 60000)
                    api.CloseHandle.assert_called_once_with(handle)
                else:
                    api.WaitForSingleObject.assert_not_called()

    def test_wait_timeout_cannot_start_copying_an_update(self):
        import types
        from unittest.mock import Mock
        message = Mock()
        with patch.object(launcher, 'wait_for_previous_launcher', return_value=False), \
             patch.object(launcher.ctypes, 'windll', types.SimpleNamespace(user32=types.SimpleNamespace(MessageBoxW=message)), create=True), \
             patch.object(launcher.shutil, 'copytree') as copy:
            self.assertEqual(launcher.install_update(self.fixture.root / 'installed', 123), 1)
        copy.assert_not_called()
        message.assert_called_once()


if __name__ == '__main__':
    unittest.main()
