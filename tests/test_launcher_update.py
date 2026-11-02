"""The launcher's own update can never leave a broken installation (R74; launcher/bbport_update.py, install_version,
install_update and main in launcher/bbport_launcher_win.py). Up to 1.9.6 it copied the new version file by file over
the installation: a file in use stayed old, and 1.9.5's Python 3.12 files mixed with 1.9.6's 3.14 ("Failed to import
encodings module"). A second start during the update deleted the files it copied from."""
from paths import ROOT
import hashlib
import io
import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import time
import tkinter
import types
import unittest
import uuid
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(ROOT / 'launcher'))
sys.path.insert(0, str(ROOT / 'scripts'))
import bbport_launcher_win as L  # noqa: E402
import bbport_update as U  # noqa: E402

PACKAGE = ('Bloodborne.exe', 'Play Bloodborne.exe', 'run.py', '_internal/base_library.zip', 'bin/bb-probe.exe',
           'scripts/prepare.py', 'patches/Bloodborne.xml', 'launcher/bloodborne.ico')


def version(folder, tag, python='python314.dll', manifest=False):
    """A packaged port's program files, each saying which version it is."""
    folder = Path(folder)
    for name in PACKAGE + (f'_internal/{python}',):
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(f'{tag} {name}', encoding='utf-8')
    if manifest:
        files = {name: hashlib.sha256((folder / name).read_bytes()).hexdigest()
                 for name in ('run.py', 'bin/bb-probe.exe', 'scripts/prepare.py')}
        (folder / 'bbport-files.json').write_text(json.dumps({'version': tag, 'files': files}), encoding='utf-8')
    return folder


def read(path):
    return Path(path).read_text(encoding='utf-8')


def a_link(path):
    return bool(os.lstat(path).st_file_attributes & 0x400)


class Inline:
    """threading.Thread that runs its target at start(), in the test's thread."""

    def __init__(self, target=None, daemon=None):
        self.target = target

    def start(self):
        self.target()


class PackageTests(unittest.TestCase):
    """The download is checked before anything is unpacked or replaced."""

    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp, True)

    def package(self, names=('Bloodborne.exe', '_internal/base_library.zip', '_internal/python314.dll'),
                inside='bbport-windows/'):
        archive = self.temp / 'update.zip'
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as package:
            for name in names:
                package.writestr(inside + name, f'contents of {name} ' * 50)
        return archive

    def test_a_complete_package_and_its_folder(self):
        archive = self.package()
        self.assertEqual(U.check_package(archive), 'bbport-windows/')
        digest = 'sha256:' + hashlib.sha256(archive.read_bytes()).hexdigest()
        self.assertEqual(U.check_package(archive, digest), 'bbport-windows/')
        self.assertEqual(U.check_package(self.package(inside='')), '')

    def test_a_download_github_lists_differently(self):
        with self.assertRaises(U.BadDownload):
            U.check_package(self.package(), 'sha256:' + '0' * 64)

    def test_missing_python_or_launcher(self):
        for missing in ('_internal/base_library.zip', '_internal/python314.dll', 'Bloodborne.exe'):
            names = [n for n in ('Bloodborne.exe', '_internal/base_library.zip', '_internal/python314.dll')
                     if n != missing]
            with self.subTest(missing=missing), self.assertRaises(U.BadDownload) as caught:
                U.check_package(self.package(names))
            self.assertIn(missing.split('/')[-1].replace('python314', 'python3*'), str(caught.exception))

    def test_a_cut_off_or_damaged_download(self):
        archive = self.package()
        data = archive.read_bytes()
        archive.write_bytes(data[:len(data) // 2])
        with self.assertRaises(U.BadDownload):
            U.check_package(archive)
        # A changed byte inside a member: its checksum no longer matches (testzip).
        archive = self.package()
        data = bytearray(archive.read_bytes())
        with zipfile.ZipFile(archive) as package:
            info = package.getinfo('bbport-windows/_internal/base_library.zip')
        start = info.header_offset + 30 + len(info.filename.encode()) + len(info.extra)
        data[start + 5] ^= 0xFF
        archive.write_bytes(bytes(data))
        with self.assertRaises(U.BadDownload):
            U.check_package(archive)

    def test_the_game_zip_digest_is_noted(self):
        asset = {'name': L.update_package_name('9.9.9-tatsunakyo.99'), 'browser_download_url': 'https://example.invalid/d.zip',
                 'digest': 'sha256:' + 'a' * 64}
        self.assertEqual(L.parse_release({'tag_name': 'windows-v9.9.9-tatsunakyo.99', 'assets': [asset]})[1], asset['browser_download_url'])
        self.assertEqual(L.ASSET_DIGESTS[asset['browser_download_url']], asset['digest'])

    def test_the_package_files_are_listed_for_the_installer(self):
        archive = self.package(('Bloodborne.exe', '_internal/base_library.zip', '_internal/python314.dll',
                                'README.md'))
        with zipfile.ZipFile(archive, 'a') as package:
            package.writestr('beside-the-folder.txt', 'not part of the port')
            package.writestr('bbport-windows/empty/', '')
            listed = U.listed_files(package, 'bbport-windows/')
        self.assertEqual(sorted(listed), ['Bloodborne.exe', 'README.md', '_internal/base_library.zip',
                                          '_internal/python314.dll'])
        self.assertEqual(listed['README.md'], len('contents of README.md ' * 50))
        (self.temp / 'files.json').write_text(json.dumps(listed), encoding='utf-8')
        self.assertEqual(U.read_listed(self.temp / 'files.json'), listed)
        self.assertIsNone(U.read_listed(None))  # started by 1.9.6: no list
        self.assertIsNone(U.read_listed(self.temp / 'missing.json'))


@unittest.skipUnless(os.name == 'nt', 'Windows renames and locks')
class SwapTests(unittest.TestCase):
    """The installer puts the new version in place by renaming, and undoes all of it when one file is in use."""

    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp, True)
        self.make(self.temp / 'BBPort')
        self.said = []
        self.name = f'Local\\bbport-test-{uuid.uuid4().hex}'
        for patch in (mock.patch.object(U, 'TRIES', 2), mock.patch.object(U, 'PAUSE', 0.01)):
            patch.start()
            self.addCleanup(patch.stop)

    def make(self, target):
        self.target = version(target, 'old', 'python312.dll')
        (self.target / 'user' / 'savedata').mkdir(parents=True)
        (self.target / 'user' / 'savedata' / 'userdata0000').write_text('my hunter', encoding='utf-8')
        (self.target / 'bbport.ini').write_text('[graphics]\n', encoding='utf-8')
        (self.target / 'patches' / 'my-own.xml').write_text('mine', encoding='utf-8')
        (self.target / 'notes.txt').write_text('the player put this here', encoding='utf-8')
        self.source = version(target.parent / 'download' / 'bbport-windows', 'new', manifest=True)
        (self.source / 'bbport.ini').write_text('[defaults of the package]\n', encoding='utf-8')

    def install(self, listed=None):
        return U.install(self.source, self.target, None, 0, self.said.append, L.USER_FILES, seconds=5, listed=listed)

    def assert_old(self):
        self.assertEqual(read(self.target / 'Bloodborne.exe'), 'old Bloodborne.exe')
        self.assertEqual(read(self.target / 'bin' / 'bb-probe.exe'), 'old bin/bb-probe.exe')
        self.assertEqual(read(self.target / 'run.py'), 'old run.py')
        self.assertTrue((self.target / '_internal' / 'python312.dll').is_file())
        self.assertFalse((self.target / '_internal' / 'python314.dll').exists())

    def assert_new(self):
        self.assertEqual(read(self.target / 'Bloodborne.exe'), 'new Bloodborne.exe')
        self.assertEqual(read(self.target / 'bin' / 'bb-probe.exe'), 'new bin/bb-probe.exe')
        self.assertEqual(read(self.target / 'run.py'), 'new run.py')
        # One Python only: the old one's files do not stay beside the new one's.
        self.assertEqual(sorted(p.name for p in (self.target / '_internal').iterdir()),
                         ['base_library.zip', 'python314.dll'])

    def assert_player_files(self):
        self.assertEqual(read(self.target / 'user' / 'savedata' / 'userdata0000'), 'my hunter')
        self.assertEqual(read(self.target / 'bbport.ini'), '[graphics]\n')
        self.assertEqual(read(self.target / 'patches' / 'my-own.xml'), 'mine')
        self.assertEqual(read(self.target / 'notes.txt'), 'the player put this here')

    def assert_no_leftovers(self):
        self.assertEqual([p.name for p in self.target.glob('.update-*')], [])

    def test_the_new_version_replaces_the_old_one_whole(self):
        self.assertEqual(self.install(), [])
        self.assert_new()
        self.assert_player_files()
        self.assert_no_leftovers()
        self.assertEqual(self.said[-1], L._('Putting the new version in place…'))

    def test_the_launchers_two_halves_go_last_one_right_after_the_other(self):
        self.assertEqual(U.order(['run.py', 'Bloodborne.exe', '_internal', 'bin', 'scripts']),
                         ['bin', 'run.py', 'scripts', '_internal', 'Bloodborne.exe'])

    def test_a_file_in_use_undoes_everything(self):
        for held in ('bin/bb-probe.exe', '_internal/python312.dll', 'Bloodborne.exe'):
            # bin goes first; _internal after everything else; Bloodborne.exe last of all.
            with self.subTest(held=held):
                with open(self.target / held, 'rb'):
                    with self.assertRaises(U.UpdateFailed) as caught:
                        self.install()
                self.assertNotIsInstance(caught.exception, U.RollbackFailed)
                self.assertIn(Path(held).name, str(caught.exception))
                self.assert_old()
                self.assert_player_files()
                self.assert_no_leftovers()

    def test_an_undo_that_fails_once_is_tried_again(self):
        real, failed = U.rename, []

        def rename(source, destination, tries, pause):
            if Path(source) == self.target / 'scripts' and Path(destination).parent.name == U.OLD:
                raise PermissionError(5, 'Access is denied', str(source))  # the swap meets a held folder
            if Path(source) == self.target / 'bin' and Path(destination).parent.name == U.NEW and not failed:
                failed.append(source)  # and its undo an antivirus scan, once
                raise PermissionError(5, 'Access is denied', str(source))
            real(source, destination, tries, pause)
        with mock.patch.object(U, 'rename', rename), self.assertRaises(U.UpdateFailed) as caught:
            self.install()
        self.assertNotIsInstance(caught.exception, U.RollbackFailed)
        self.assertIn('scripts', str(caught.exception))
        self.assert_old()
        self.assert_player_files()
        self.assert_no_leftovers()

    def test_when_undoing_fails_too_the_next_start_puts_it_right(self):
        real = U.rename

        def rename(source, destination, tries, pause):
            if Path(source) == self.target / 'scripts' and Path(destination).parent.name == U.OLD:
                raise PermissionError(5, 'Access is denied', str(source))
            if Path(source) == self.target / 'bin' and Path(destination).parent.name == U.NEW:
                raise PermissionError(5, 'Access is denied', str(source))
            real(source, destination, tries, pause)
        with mock.patch.object(U, 'rename', rename), self.assertRaises(U.RollbackFailed) as caught:
            self.install()
        self.assertIn('bin', str(caught.exception))
        self.assertTrue((caught.exception.old / U.JOURNAL).is_file())  # kept for the next start
        notes = U.clear_leftovers(self.target, None, self.name)
        self.assertIn('undone', notes[0])
        self.assert_old()
        self.assert_player_files()
        self.assert_no_leftovers()

    def test_an_incomplete_copy_is_not_put_in_place(self):
        (self.source / 'bin' / 'bb-probe.exe').write_text('cut off', encoding='utf-8')  # not what the list says
        with self.assertRaises(U.UpdateFailed) as caught:
            self.install()
        self.assertIn('bb-probe.exe', str(caught.exception))
        self.assert_old()
        self.assertFalse((self.target / U.NEW).exists())

    def test_a_file_gone_from_the_unpacked_package_is_noticed(self):
        listed = {name: (self.source / name).stat().st_size for name in PACKAGE}
        listed['_internal/_ssl.pyd'] = 1234  # in the zip, then taken away (an antivirus, a cleanup)
        listed['tools/legacy-cpu-plan.json'] = 10  # a whole folder of it
        listed['user/savedata/userdata0000'] = 5  # the player's: never copied, never missed
        with self.assertRaises(U.UpdateFailed) as caught:
            self.install(listed)
        self.assertIn('_ssl.pyd', str(caught.exception))
        self.assertIn('legacy-cpu-plan.json', str(caught.exception))
        self.assertNotIn('userdata', str(caught.exception))
        self.assert_old()
        self.assert_no_leftovers()
        del listed['_internal/_ssl.pyd'], listed['tools/legacy-cpu-plan.json']
        self.install(listed)
        self.assert_new()

    def test_a_failed_copy_removes_its_own_folder(self):
        (self.target / U.NEW).mkdir()
        with open(self.target / U.NEW / 'held.txt', 'w'):  # a leftover that cannot go: the copy goes to -2
            (self.source / 'bin' / 'bb-probe.exe').write_text('cut off', encoding='utf-8')
            with self.assertRaises(U.UpdateFailed):
                self.install()
            self.assertEqual([p.name for p in self.target.glob('.update-*')], [U.NEW])

    def test_a_copy_that_takes_too_long_stops_before_anything_is_renamed(self):
        with self.assertRaises(U.UpdateFailed) as caught:
            U.stage(self.source, self.target, L.USER_FILES, seconds=-1)
        self.assertIn(L._('copying the new files did not finish in {} minutes').split('{}')[0], str(caught.exception))
        self.assert_old()
        self.assert_no_leftovers()

    def test_old_only_files_stay_except_in_internal(self):
        (self.target / 'bin' / 'nvngx_dlss.dll').write_text('a newer DLSS', encoding='utf-8')
        (self.target / 'fsr4_shaders').mkdir()
        (self.target / 'fsr4_shaders' / 'rcas.spv').write_text('downloaded', encoding='utf-8')
        self.install()
        self.assertEqual(read(self.target / 'bin' / 'nvngx_dlss.dll'), 'a newer DLSS')
        self.assertEqual(read(self.target / 'fsr4_shaders' / 'rcas.spv'), 'downloaded')
        self.assertFalse((self.target / '_internal' / 'python312.dll').exists())

    def test_a_junction_stays_a_junction(self):
        import _winapi
        elsewhere = self.temp / 'elsewhere'
        elsewhere.mkdir()
        (elsewhere / 'big.bin').write_bytes(b'x' * 1000)
        _winapi.CreateJunction(str(elsewhere), str(self.target / 'patches' / 'linked'))
        self.install()
        self.assert_new()
        self.assertTrue(a_link(self.target / 'patches' / 'linked'))  # not a copy of what it points to
        self.assertEqual(os.path.realpath(self.target / 'patches' / 'linked'), os.path.realpath(elsewhere))
        self.assertEqual((elsewhere / 'big.bin').stat().st_size, 1000)  # and the old link's removal kept it
        self.assert_no_leftovers()

    def test_a_folder_named_in_other_scripts(self):
        self.make(self.temp / 'Игры 血源 게임' / 'BBPort')
        self.install()
        self.assert_new()
        self.assert_player_files()
        self.assert_no_leftovers()

    def test_the_locked_file_is_named(self):
        with open(self.target / 'bin' / 'bb-probe.exe', 'rb'):
            self.assertEqual(U.locked_file(self.target / 'bin'), self.target / 'bin' / 'bb-probe.exe')
        self.assertIsNone(U.locked_file(self.target / 'bin'))


# The installer stopped for good at one rename (Task Manager, an antivirus, a power cut): no undo, no cleanup.
KILLED = r'''
import os, sys, types
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import bbport_update as U
U.bind(types.SimpleNamespace(_=lambda *texts: texts[0]))
real, stop = U.rename, Path(sys.argv[4])
def rename(source, destination, tries, pause):
    if Path(source) == stop:
        os._exit(9)
    real(source, destination, tries, pause)
U.rename = rename
U.swap(sys.argv[2], sys.argv[3])
'''


@unittest.skipUnless(os.name == 'nt', 'Windows renames and named objects')
class InterruptedTests(unittest.TestCase):
    """A swap stopped halfway is finished or undone at the next start from its journal, never deleted. (It borrows
    SwapTests' installation and checks.)"""

    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp, True)
        self.name = f'Local\\bbport-test-{uuid.uuid4().hex}'

    def killed_at(self, where):
        """A fresh installation, its update staged and swapped until the rename of `where` (in .update-new)."""
        folder = self.temp / uuid.uuid4().hex[:8]
        SwapTests.make(self, folder / 'BBPort')
        staging = U.stage(self.source, self.target, L.USER_FILES)
        code = subprocess.run([sys.executable, '-c', KILLED, str(ROOT / 'launcher'), str(staging), str(self.target),
                               str(staging / where)], timeout=120).returncode
        self.assertEqual(code, 9)

    def test_stopped_halfway_and_put_right_at_the_next_start(self):
        for where, outcome in (('bin', 'old'), ('_internal', 'old'), ('Bloodborne.exe', 'new')):
            with self.subTest(where=where):
                self.killed_at(where)
                self.assertFalse((self.target / where).exists())  # the R74 state: a folder or the launcher gone
                notes = U.clear_leftovers(self.target, None, self.name)
                self.assertIn('completed' if outcome == 'new' else 'undone', notes[0])
                (SwapTests.assert_new if outcome == 'new' else SwapTests.assert_old)(self)
                SwapTests.assert_player_files(self)
                SwapTests.assert_no_leftovers(self)

    def test_stopped_after_the_last_rename(self):
        folder = self.temp / 'done'
        SwapTests.make(self, folder / 'BBPort')
        staging = U.stage(self.source, self.target, L.USER_FILES)
        names = U.order(p.name for p in staging.iterdir())
        existed = [name for name in names if (self.target / name).exists()]
        old = U.swap(staging, self.target)
        U.write_journal(old, staging, names, existed)  # stopped before the journal went
        notes = U.clear_leftovers(self.target, None, self.name)
        self.assertIn('completed', notes[0])
        SwapTests.assert_new(self)
        SwapTests.assert_no_leftovers(self)

    def test_the_next_installer_puts_it_right_first(self):
        self.killed_at('bin')
        U.install(self.source, self.target, None, 0, lambda text: None, L.USER_FILES, seconds=5)
        SwapTests.assert_new(self)
        SwapTests.assert_player_files(self)
        SwapTests.assert_no_leftovers(self)

    def test_without_a_journal_nothing_the_installation_lacks_is_deleted(self):
        SwapTests.make(self, self.temp / 'old-code' / 'BBPort')
        (self.target / U.OLD).mkdir()
        os.rename(self.target / 'bin', self.target / U.OLD / 'bin')  # what an installer without a journal left
        shutil.copytree(self.target / 'scripts', self.target / U.OLD / 'scripts')
        notes = U.clear_leftovers(self.target, None, self.name)
        self.assertIn('bin', notes[0])
        SwapTests.assert_old(self)
        SwapTests.assert_no_leftovers(self)

    def test_a_held_file_keeps_the_journal_for_a_later_start(self):
        self.killed_at('bin')
        # bbport-files.json went in before bin (order()); held, it cannot go back into .update-new yet.
        with open(self.target / 'bbport-files.json', 'rb'), mock.patch.object(U, 'TRIES', 1):
            notes = U.clear_leftovers(self.target, None, self.name)
        self.assertIn('kept for the next start', notes[0])
        self.assertTrue((self.target / U.OLD / U.JOURNAL).is_file())
        self.assertTrue((self.target / U.NEW).is_dir())
        self.assertIn('undone', U.clear_leftovers(self.target, None, self.name)[0])
        SwapTests.assert_old(self)
        SwapTests.assert_no_leftovers(self)


@unittest.skipUnless(os.name == 'nt', 'Windows processes and named objects')
class WaitTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp, True)

    def test_programs_started_from_the_installation_are_waited_for_and_named(self):
        ping = self.temp / 'bin' / 'ping.exe'
        ping.parent.mkdir()
        shutil.copy2(Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32' / 'PING.EXE', ping)
        process = subprocess.Popen([str(ping), '-n', '30', '127.0.0.1'], stdout=subprocess.DEVNULL,
                                   creationflags=L.NO_WINDOW)
        self.addCleanup(process.wait)
        self.addCleanup(process.kill)
        for _ in range(50):
            if U.programs_under(self.temp):
                break
            time.sleep(0.1)
        self.assertEqual([pid for pid, _path in U.programs_under(self.temp)], [process.pid])
        said = []
        with self.assertRaises(U.UpdateFailed) as caught:
            U.wait_for_programs(self.temp, None, 0, said.append, seconds=0.5, pause=0.1)
        self.assertIn('ping.exe', str(caught.exception))
        self.assertIn(L._('Waiting for {} to close…').format('ping.exe'), said)
        self.assertEqual(U.programs_under(self.temp / 'elsewhere'), [])

    def test_the_old_launcher_closes_once_the_installer_holds_the_mutex(self):
        name = f'Local\\bbport-test-{uuid.uuid4().hex}'
        holder = subprocess.Popen([sys.executable, '-c', 'import ctypes, time; ctypes.windll.kernel32.CreateMutexW('
                                   f'None, False, {name!r}); time.sleep(30)'])
        self.addCleanup(holder.wait)
        self.addCleanup(holder.kill)
        self.assertIsNone(U.wait_for_installer(holder, name, seconds=30))
        # An installer an antivirus stopped: the launcher stays open and says so.
        quitter = subprocess.Popen([sys.executable, '-c', 'raise SystemExit(3)'])
        self.assertEqual(U.wait_for_installer(quitter, name + '-other', seconds=30), '3')
        # One that never answers is stopped, and gone before its folder is cleared.
        sleeper = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
        self.addCleanup(sleeper.kill)
        self.assertEqual(U.wait_for_installer(sleeper, name + '-other', seconds=0.3), 'timeout')
        self.assertIsNotNone(sleeper.poll())

    def test_a_start_during_an_install_brings_the_installers_window_forward(self):
        name = f'Local\\bbport-test-{uuid.uuid4().hex}'
        self.assertFalse(U.to_front(name))  # no installer window: main() shows a note that closes by itself
        asked = queue.Queue()
        self.assertTrue(L.bring_to_front_on_request(lambda: asked.put(True), name))
        self.assertTrue(U.to_front(name))
        self.assertTrue(asked.get(timeout=10))


@unittest.skipUnless(os.name == 'nt', 'Windows named objects')
class LeftoverTests(unittest.TestCase):
    """The leftovers go at a normal start, never while an installer runs."""

    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp, True)
        self.port = version(self.temp / 'BBPort', 'new')
        self.downloads = self.temp / 'bbport-update'
        for folder in (self.port / '.update-old' / '_internal', self.port / '.update-old-2',
                       self.port / '.update-new' / 'bin', self.downloads / 'v1.9.7-x' / 'new'):
            folder.mkdir(parents=True)
        self.name = f'Local\\bbport-test-{uuid.uuid4().hex}'

    def test_kept_while_an_update_is_being_installed(self):
        self.assertTrue(U.hold_mutex(self.name))
        try:
            self.assertFalse(U.hold_mutex(self.name))  # a second installer is turned away
            self.assertTrue(U.underway(self.name))
            self.assertIsNone(U.clear_leftovers(self.port, self.downloads, self.name))
            self.assertTrue((self.port / '.update-new' / 'bin').is_dir())
            self.assertTrue((self.downloads / 'v1.9.7-x' / 'new').is_dir())
        finally:
            U.release_mutex()
        self.assertFalse(U.underway(self.name))

    def test_cleared_at_a_normal_start(self):
        notes = U.clear_leftovers(self.port, self.downloads, self.name)
        self.assertEqual(len(notes), 3)  # one log line each
        self.assertTrue(all(note.startswith('Update: .update-') and note.endswith('removed') for note in notes))
        self.assertEqual([p.name for p in self.port.glob('.update-*')], [])
        self.assertFalse(self.downloads.exists())
        self.assertTrue((self.port / 'Bloodborne.exe').is_file())

    def test_never_the_folder_the_port_runs_from(self):
        port = self.downloads / 'v1.9.7-x' / 'new'
        self.assertEqual(U.clear_leftovers(port, self.downloads, self.name), [])
        self.assertTrue(port.is_dir())


class MainTests(unittest.TestCase):
    """main(): a start during an install deletes nothing and exits at once; the leftovers go only after
    one_launcher, and they and the installer's outcome go into the next game's log."""

    def run_main(self, underway, first, front=True, result=None):
        calls = mock.Mock()
        calls.one_launcher.return_value = first
        calls.to_front.return_value = front
        calls.clear_leftovers.return_value = ['Update: .update-old removed']
        self.repairs = []
        environment = {'BB_UPDATE_RESULT': result} if result else {}
        patches = [mock.patch.object(L.sys, 'argv', ['Bloodborne.exe']), mock.patch.object(L, 'FROZEN', True),
                   mock.patch.object(L, 'LANG', L.LANG), mock.patch.dict(L.saves.WORDS),  # main sets both
                   mock.patch.object(L, 'load_settings', return_value={}),
                   mock.patch.object(L, 'settled_online', return_value={}),
                   mock.patch.object(L, 'one_launcher', calls.one_launcher),
                   mock.patch.object(L.updater, 'underway', return_value=underway),
                   mock.patch.object(L.updater, 'to_front', calls.to_front),
                   mock.patch.object(L.updater, 'notice', calls.notice),
                   mock.patch.object(L.updater, 'clear_leftovers', calls.clear_leftovers),
                   mock.patch.object(L.textfile, 'REPAIRS', self.repairs),
                   mock.patch.dict(os.environ, environment),
                   mock.patch.object(L, 'Launcher', calls.Launcher),
                   mock.patch.object(L, 'bring_to_front_on_request', calls.bring_to_front),
                   mock.patch('tkinter.Tk', calls.Tk)]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        try:
            L.main()
        except SystemExit:
            pass
        self.calls = calls
        return [call[0] for call in calls.mock_calls if call[0] in ('one_launcher', 'to_front', 'notice',
                                                                   'clear_leftovers')]

    def test_a_start_during_an_install_deletes_nothing(self):
        self.assertEqual(self.run_main(underway=True, first=True), ['to_front'])
        # No installer window to bring forward: a note that does not keep this start open for long.
        self.assertEqual(self.run_main(underway=True, first=True, front=False), ['to_front', 'notice'])
        self.assertEqual(self.calls.notice.call_args.kwargs, {'seconds': 4})

    def test_a_second_window_deletes_nothing(self):
        self.assertEqual(self.run_main(underway=False, first=False), ['one_launcher'])

    def test_the_leftovers_go_after_one_launcher(self):
        self.assertEqual(self.run_main(underway=False, first=True), ['one_launcher', 'clear_leftovers'])

    def test_what_the_update_did_goes_into_the_log(self):
        self.run_main(underway=False, first=True, result='Update: a link kept\nUpdate: version 9.9.9-tatsunakyo.99 installed')
        self.assertEqual(self.repairs, ['Update: .update-old removed', 'Update: a link kept',
                                        'Update: version 9.9.9-tatsunakyo.99 installed'])
        self.assertNotIn('BB_UPDATE_RESULT', os.environ)  # not passed on to the game


class InstallerTests(unittest.TestCase):
    """--install-update: one installer at a time; the launcher it starts again, and what it tells the player and
    the log."""

    def run_installer(self, failure=None, mutex=True):
        calls = mock.Mock()

        def install(source, target, launcher, pid, say, user_files, listed=None):
            calls.install(source, target, pid, listed)
            say('Copying the new files…')
            if failure:
                raise failure
            return ['Update: a link kept']
        listed = Path(tempfile.mkdtemp()) / 'files.json'
        self.addCleanup(shutil.rmtree, listed.parent, True)
        listed.write_text(json.dumps({'Bloodborne.exe': 5}), encoding='utf-8')
        environment = {'BB_UPDATE_FROM': r'C:\temp\bbport-update\v9\new\bbport-windows', 'BB_UPDATE_VERSION': '9.9.9-tatsunakyo.99',
                       'BB_UPDATE_FILES': str(listed)}
        patches = [mock.patch.object(L.updater, 'install', install),
                   mock.patch.object(L.updater, 'hold_mutex', return_value=mutex),
                   mock.patch.object(L.updater, 'release_mutex', calls.release_mutex),
                   mock.patch.object(L.updater, 'open_process', return_value=None),
                   mock.patch.object(L.updater, 'notice', calls.notice),
                   mock.patch.object(L.updater, 'to_front', calls.to_front),
                   mock.patch.object(L.subprocess, 'Popen', calls.Popen),
                   mock.patch.object(L.webbrowser, 'open', calls.browser),
                   mock.patch.object(L.ctypes, 'windll', types.SimpleNamespace(shcore=types.SimpleNamespace(SetProcessDpiAwareness=calls.dpi)), create=True),
                   mock.patch('tkinter.Tk', side_effect=tkinter.TclError('no display')),  # the window's fallback
                   mock.patch.dict(os.environ, environment)]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.calls = calls
        return L.install_update(r'C:\Games\BBPort', '1234')

    def started(self):
        self.calls.Popen.assert_called_once()
        args, kwargs = self.calls.Popen.call_args
        self.assertEqual(args[0], [str(Path(r'C:\Games\BBPort') / 'Bloodborne.exe')])
        self.assertFalse({'BB_UPDATE_FROM', 'BB_UPDATE_VERSION', 'BB_UPDATE_FILES'} & set(kwargs['env']))
        return kwargs['env']['BB_UPDATE_RESULT'].splitlines()

    def test_installed(self):
        self.assertEqual(self.run_installer(), 0)
        source, target, pid, listed = self.calls.install.call_args[0]
        self.assertEqual((Path(str(source).replace('\\', '/')).name, target, pid, listed), ('bbport-windows', Path(r'C:\Games\BBPort'), 1234,
                                                              {'Bloodborne.exe': 5}))
        self.assertEqual(self.started(), ['Update: a link kept', 'Update: version 9.9.9-tatsunakyo.99 installed'])
        self.calls.notice.assert_not_called()
        self.calls.release_mutex.assert_called_once_with()

    def test_undone_the_old_launcher_opens_again(self):
        self.assertEqual(self.run_installer(U.UpdateFailed('bin is in use by another program')), 1)
        self.calls.notice.assert_called_once()
        self.assertIn('bin is in use', self.calls.notice.call_args[0][0])
        self.assertEqual(self.calls.notice.call_args.kwargs, {'error': True})
        self.assertIn('was not installed, the installed version was kept (bin is in use', self.started()[-1])
        self.calls.browser.assert_not_called()

    def test_not_even_undone_no_launcher_and_the_releases_page(self):
        self.assertEqual(self.run_installer(U.RollbackFailed(r'C:\Games\BBPort\bin')), 1)
        self.calls.Popen.assert_not_called()
        self.calls.browser.assert_called_once_with(L.RELEASES_PAGE)
        self.calls.notice.assert_called_once()

    def test_stopped_otherwise_it_still_says_so(self):
        self.assertEqual(self.run_installer(KeyboardInterrupt()), 1)
        self.assertIn('KeyboardInterrupt', self.started()[-1])

    def test_a_second_installer_only_brings_the_first_forward(self):
        self.assertEqual(self.run_installer(mutex=False), 1)
        self.calls.install.assert_not_called()
        self.calls.to_front.assert_called_once_with()
        self.calls.Popen.assert_not_called()


class ProgressWindowTests(unittest.TestCase):
    """The installer's window never stands in the way of the install, and it closes whatever the work did."""

    def test_without_tk_the_work_runs_all_the_same(self):
        with mock.patch('tkinter.Tk', side_effect=tkinter.TclError('no display')):
            self.assertEqual(L.progress_window('Installing', lambda say: 'done'), ('done', None))

            def stopped(say):
                raise SystemExit(5)
            value, failure = L.progress_window('Installing', stopped)
        self.assertIsNone(value)
        self.assertIsInstance(failure, SystemExit)

    def test_a_window_tk_cannot_draw(self):
        root = mock.Mock()
        with mock.patch('tkinter.Tk', return_value=root), \
                mock.patch('tkinter.Label', side_effect=tkinter.TclError('bad font')):
            self.assertEqual(L.progress_window('Installing', lambda say: 'done'), ('done', None))
        root.destroy.assert_called_once_with()
        root.mainloop.assert_not_called()


def bare_launcher():
    ui = L.Launcher.__new__(L.Launcher)
    ui.process = None
    ui.updating, ui.installing, ui.versions_listed = False, False, True
    ui.update_button, ui.version_install = mock.Mock(), mock.Mock()
    ui.version_window = mock.Mock()
    ui.messagebox = mock.Mock()
    ui.messagebox.askyesno.return_value = True
    ui.ui_calls = queue.Queue()
    ui.root, ui.status = mock.Mock(), mock.Mock()
    return ui


def run_ui_calls(ui):
    while not ui.ui_calls.empty():
        ui.ui_calls.get_nowait()()


class OneUpdateTests(unittest.TestCase):
    """The side box's Update and Other versions' Install: one update at a time, never during a game or a game test."""

    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp, True)
        for patch in (mock.patch.object(L, 'FROZEN', True), mock.patch.object(L, 'game_underway', return_value=False),
                      mock.patch.object(L.threading, 'Thread'), mock.patch.object(L.workshop, 'fetch_checksum', return_value='fixture checksum'),
                      mock.patch.object(L, 'verify_update_archive', return_value='bbport-windows'),
                      mock.patch.object(L, 'UPDATE_DIR', self.temp / 'up')):
            patch.start()
            self.addCleanup(patch.stop)

    def test_one_update_at_a_time(self):
        ui = bare_launcher()
        self.assertTrue(ui.install_version('9.9.9-tatsunakyo.99', 'https://example.invalid/a.zip', 'p', mock.Mock(), mock.Mock()))
        self.assertTrue(ui.updating)
        ui.update_button.configure.assert_called_with(state='disabled')
        ui.version_install.configure.assert_called_with(state='disabled')
        # The other button, before it was greyed out: nothing happens, nothing is asked.
        self.assertFalse(ui.install_version('9.9.8', 'https://example.invalid/b.zip', 'p', mock.Mock(), mock.Mock()))
        self.assertEqual(ui.messagebox.askyesno.call_count, 1)
        failed = mock.Mock()
        ui.update_failed(failed, 'the download is damaged')
        self.assertFalse(ui.updating)
        failed.assert_called_once_with()
        ui.update_button.configure.assert_called_with(state='normal')
        ui.version_install.configure.assert_called_with(state='normal')
        ui.messagebox.showerror.assert_called_once()

    def test_not_during_a_game_test_or_a_game(self):
        ui = bare_launcher()
        ui.bench = types.SimpleNamespace(finished=False)
        self.assertFalse(ui.install_version('9.9.9-tatsunakyo.99', 'https://example.invalid/a.zip', 'p', mock.Mock(), mock.Mock()))
        ui.bench = None
        with mock.patch.object(L, 'game_underway', return_value=True):
            self.assertFalse(ui.install_version('9.9.9-tatsunakyo.99', 'https://example.invalid/a.zip', 'p', mock.Mock(),
                                                mock.Mock()))
        self.assertEqual(ui.messagebox.showinfo.call_count, 2)
        ui.messagebox.askyesno.assert_not_called()
        self.assertFalse(ui.updating)

    def download(self, ui, answer, failed=None):
        """install_version with its download thread run inline; GitHub answers `answer` (bytes or an exception)."""
        def urlopen(request, timeout=None):
            if isinstance(answer, Exception):
                raise answer
            response = io.BytesIO(answer)
            response.headers = {'Content-Length': str(len(answer))}
            return response
        installer = self.temp / 'up' / 'installer' / 'Bloodborne.exe'
        with mock.patch.object(L.threading, 'Thread', Inline), mock.patch.object(L.bbport_tls, 'urlopen', urlopen), \
                mock.patch.object(L, 'update_installer', return_value=installer):
            self.assertTrue(ui.install_version('9.9.9-tatsunakyo.99', 'https://example.invalid/a.zip', 'p', mock.Mock(),
                                               failed or mock.Mock()))

    def test_a_failed_download_leaves_no_folder(self):
        for answer in (OSError('connection reset'), b'not a zip at all'):
            with self.subTest(answer=answer):
                ui, failed = bare_launcher(), mock.Mock()
                self.download(ui, answer, failed)
                run_ui_calls(ui)
                failed.assert_called_once_with()
                self.assertFalse(ui.updating)
                self.assertEqual(list((self.temp / 'up').iterdir()), [])  # neither the zip nor what was unpacked

    def test_the_download_is_checked_listed_and_handed_to_the_installer(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as package:
            for name in ('Bloodborne.exe', '_internal/base_library.zip', '_internal/python314.dll', 'bin/a.dll'):
                package.writestr('bbport-windows/' + name, name * 3)
        ui = bare_launcher()
        self.download(ui, data.getvalue())
        folder = next((self.temp / 'up').iterdir())
        self.assertFalse((folder / 'update.zip').exists())
        self.assertEqual(json.loads(read(folder / 'files.json'))['bin/a.dll'], len('bin/a.dll' * 3))
        process = mock.Mock()
        with mock.patch.object(L.subprocess, 'Popen', return_value=process) as popen, \
                mock.patch.object(L.updater, 'wait_for_installer', return_value=None), \
                mock.patch.object(L.threading, 'Thread', Inline):
            # The progress lines, then start_installer; once the installer holds the update mutex, this launcher
            # closes the usual way (settings, tray icon): close, not root.destroy.
            call = None
            while call != ui.close:
                call = ui.ui_calls.get_nowait()
                if call != ui.close:
                    call()
        self.assertEqual(popen.call_args[0][0][:2], [str(self.temp / 'up' / 'installer' / 'Bloodborne.exe'),
                                                     '--install-update'])
        env = popen.call_args.kwargs['env']
        self.assertEqual((env['BB_UPDATE_FROM'], env['BB_UPDATE_FILES'], env['BB_UPDATE_VERSION']),
                         (str(folder / 'new' / 'bbport-windows'), str(folder / 'files.json'), '9.9.9-tatsunakyo.99'))
        self.assertTrue(ui.installing)
        ui.root.destroy.assert_not_called()

    def test_a_game_started_during_the_download_is_waited_for(self):
        ui, say = bare_launcher(), mock.Mock()
        folder = self.temp / 'up' / 'v9.9.9-x'
        with mock.patch.object(L, 'game_underway', return_value=True), \
                mock.patch.object(L.subprocess, 'Popen') as popen:
            ui.start_installer('9.9.9-tatsunakyo.99', folder / 'installer' / 'Bloodborne.exe', folder, folder / 'new', say,
                               mock.Mock())
        popen.assert_not_called()
        self.assertFalse(ui.installing)
        say.assert_called_with(L._('Version {} is downloaded: it installs once the game is closed.').format('9.9.9-tatsunakyo.99'))
        delay, again = ui.root.after.call_args[0]
        self.assertEqual(delay, 2000)
        with mock.patch.object(L.subprocess, 'Popen') as popen, \
                mock.patch.object(L.updater, 'wait_for_installer', return_value=None):
            again()
        popen.assert_called_once()

    def test_an_installer_that_did_not_start_leaves_no_folder(self):
        ui, failed = bare_launcher(), mock.Mock()
        ui.updating = True
        folder = self.temp / 'up' / 'v9.9.9-x'
        (folder / 'installer').mkdir(parents=True)
        with mock.patch.object(L.subprocess, 'Popen'), mock.patch.object(L.threading, 'Thread', Inline), \
                mock.patch.object(L.updater, 'wait_for_installer', return_value='timeout'):
            ui.start_installer('9.9.9-tatsunakyo.99', folder / 'installer' / 'Bloodborne.exe', folder, folder / 'new', mock.Mock(),
                               failed)
        run_ui_calls(ui)
        failed.assert_called_once_with()
        self.assertFalse(folder.exists())
        self.assertFalse(ui.updating or ui.installing)
        self.assertIn('timeout', ui.messagebox.showerror.call_args[0][1])

    def test_no_game_or_game_test_starts_while_the_installer_starts(self):
        ui = bare_launcher()
        ui.installing, ui.fsr411_downloading = True, False
        with mock.patch.object(L.subprocess, 'Popen') as popen:
            ui.play()
            ui.run_bug_benchmark()
            ui.start_benchmark()
        popen.assert_not_called()
        ui.messagebox.showinfo.assert_not_called()  # a line in the status, nothing that stops the closing
        self.assertEqual(ui.status.configure.call_count, 3)

    def test_every_version_is_installed_by_a_copy_of_this_launcher(self):
        # A release built without bbport_update (an older one, or from a branch without it) copies itself file by
        # file and never takes the update mutex: never its own launcher, whatever version it is.
        internal, exe = self.temp / 'port' / '_internal', self.temp / 'port' / 'Bloodborne.exe'
        internal.mkdir(parents=True)
        (internal / 'python314.dll').write_text('this one', encoding='utf-8')
        exe.write_text('this launcher', encoding='utf-8')
        for number, folder in enumerate((self.temp / 'newer', self.temp / 'older')):
            with self.subTest(folder=folder.name), mock.patch.object(L.sys, '_MEIPASS', str(internal), create=True), \
                    mock.patch.object(L.sys, 'executable', str(exe)):
                installer = L.update_installer(folder)
            self.assertEqual(installer, folder / 'installer' / 'Bloodborne.exe')
            self.assertEqual(read(installer), 'this launcher')
            self.assertTrue((installer.parent / '_internal' / 'python314.dll').is_file())


if __name__ == '__main__':
    unittest.main()
