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
        for path in ('Workshop/../outside', 'Workshop/NUL.txt', 'Workshop/README.md.', 'Workshop/README.MD',
                     'Workshop/dir\\evil', 'Workshop/extra\x00hidden'):
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
        from unittest.mock import Mock
        for accepted in (False, True):
            with self.subTest(accepted=accepted):
                def complete(identity,data):
                    data['_internal/base_library.zip']=b'fixture base library'
                    data['_internal/python314.dll']=fixtures.pe()
                package=self.fixture.package(modify=complete)
                replies=[package.read_bytes(), ((integrity.checksum(package) if accepted else '0'*64)
                         + '  ' + package.name + '\n').encode()]
                events=[]
                obj=types.SimpleNamespace(updating=False, installing=False, ui_calls=queue.SimpleQueue(),
                    game_running=lambda:False,test_running=lambda:False,update_buttons=Mock(),
                    messagebox=types.SimpleNamespace(askyesno=lambda *a:True,
                        showerror=lambda *a:events.append(('error',a))))
                obj.update_failed=types.MethodType(launcher.Launcher.update_failed,obj)
                obj.start_installer=lambda version,installer,folder,new,say,failed:events.append(('verified',new))
                class Thread:
                    def __init__(self,*,target,daemon):self.target=target
                    def start(self):self.target()
                def response(*a,**kw):
                    reply=io.BytesIO(replies.pop(0));reply.headers={'Content-Length':str(len(reply.getvalue()))}
                    return reply
                with patch.object(launcher,'FROZEN',True), patch.object(launcher,'UPDATE_DIR',self.fixture.root/'updates'), \
                     patch.object(launcher.threading,'Thread',Thread), \
                     patch.object(launcher.bbport_tls,'urlopen',side_effect=response), \
                     patch.object(launcher,'update_installer',return_value=self.fixture.root/'installer.exe'), \
                     patch.object(launcher.subprocess,'Popen') as execute:
                    launcher.Launcher.install_version(obj,'1.6-tatsunakyo.22',
                        'https://example.invalid/'+package.name,'https://example.invalid/release',Mock(),Mock())
                    while not obj.ui_calls.empty():obj.ui_calls.get()()
                execute.assert_not_called()  # the installer handoff is the next separate stage
                self.assertEqual(events[0][0],'verified' if accepted else 'error',events)
                if accepted:
                    self.assertTrue((events[0][1]/'Bloodborne.exe').is_file())
                else:
                    self.assertFalse(any(launcher.UPDATE_DIR.glob('*/new')))


if __name__=='__main__':
    unittest.main()
