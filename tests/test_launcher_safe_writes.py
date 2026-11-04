"""Saves and settings written safely (the launcher check of 2026-10-30): files written whole or not at all through
bbport_textfile, a read-only bbport.ini that kept the launcher and Play Bloodborne.exe from starting, and the saves
an unfinished game test of the 1.9.3 test builds left in place of the player's."""
from paths import ROOT
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(ROOT / 'launcher'))
import bbport_input_config as config  # noqa: E402
import bbport_launcher_win as L  # noqa: E402
import bbport_steam as steam  # noqa: E402
import bbport_textfile as textfile  # noqa: E402

FULL = OSError(28, 'No space left on device')


class Folder(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        repairs = mock.patch.object(textfile, 'REPAIRS', [])
        repairs.start()
        self.addCleanup(repairs.stop)


class WriteBytesTests(Folder):
    def test_the_bytes_as_they_are_and_nothing_beside(self):
        path = self.folder / 'userdata0000'
        textfile.write_bytes(path, b'a\nb\r\n\x00')
        self.assertEqual(path.read_bytes(), b'a\nb\r\n\x00')  # no newline turned into \r\n
        self.assertEqual(os.listdir(self.folder), ['userdata0000'])

    def test_a_write_cut_off_leaves_the_old_file(self):
        path = self.folder / 'shortcuts.vdf'
        path.write_bytes(b'old')
        with mock.patch.object(textfile.os, 'replace', side_effect=FULL):
            with self.assertRaises(OSError):
                textfile.write_bytes(path, b'new')
        self.assertEqual(path.read_bytes(), b'old')
        self.assertEqual(os.listdir(self.folder), ['shortcuts.vdf'])  # the temporary file is gone

    def test_a_file_held_for_a_moment_is_tried_again(self):
        path, real, held = self.folder / 'userdata0000', os.replace, [PermissionError(32, 'in use')] * 2

        def replace(source, target):
            if held:
                raise held.pop()
            return real(source, target)
        with mock.patch.object(textfile.os, 'replace', side_effect=replace), \
                mock.patch.object(textfile.time, 'sleep') as waited:
            textfile.write_bytes(path, b'new')
        self.assertEqual((path.read_bytes(), waited.call_count), (b'new', 2))


class SteamShortcutTests(Folder):
    """Steam's shortcuts.vdf holds every non-Steam game of the player's, not only this one."""

    def setUp(self):
        super().setUp()
        self.vdf = self.folder / 'config' / 'shortcuts.vdf'
        steam.add_shortcut(self.vdf, 'Other', r'C:\Other\o.exe', r'C:\Other', '')
        self.first = self.vdf.read_bytes()

    def names(self):
        root = steam.parse(self.vdf.read_bytes())[0]
        return [dict((key, value) for _kind, key, value in entry[2])['AppName'] for entry in root[0][2]]

    def test_added_with_a_copy_of_the_old_file(self):
        self.assertEqual(steam.add_shortcut(self.vdf, 'Bloodborne', r'C:\bb\Play Bloodborne.exe', r'C:\bb', ''),
                         'added')
        self.assertEqual(self.names(), ['Other', 'Bloodborne'])
        self.assertEqual(self.vdf.with_name('shortcuts.vdf.bak').read_bytes(), self.first)
        self.assertEqual(sorted(os.listdir(self.vdf.parent)), ['shortcuts.vdf', 'shortcuts.vdf.bak'])

    def test_a_write_cut_off_keeps_the_players_other_games(self):
        with mock.patch.object(textfile.os, 'replace', side_effect=FULL):
            with self.assertRaises(OSError):
                steam.add_shortcut(self.vdf, 'Bloodborne', r'C:\bb\Play Bloodborne.exe', r'C:\bb', '')
        self.assertEqual(self.vdf.read_bytes(), self.first)
        self.assertEqual(self.names(), ['Other'])


class Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class LauncherFileTests(Folder):
    """mods.json, patches.json and input.ini (the Dark Souls III layout) were written in place."""

    def setUp(self):
        super().setUp()
        self.ini = self.folder / 'bbport.ini'
        self.ini.write_text('upscaler=fsr3\nfsr411_backend=vk\n', encoding='utf-8')
        for patch in (mock.patch.dict(os.environ, {'BB_CONFIG': str(self.ini)}),
                      mock.patch.multiple(L, DATA_DIR=self.folder, CONFIG_DIR=self.folder / 'launcher',
                                          CONFIG_FILE=self.folder / 'launcher' / 'settings.json')):
            patch.start()
            self.addCleanup(patch.stop)
        ui = self.ui = L.Launcher.__new__(L.Launcher)
        ui.app = dict(L.APP_DEFAULTS)
        ui.ini, ui.ini_lines = dict(L.INI_DEFAULTS), []
        ui.vars, ui.remap_edits, ui.mouse_edited, ui.mouse_settings = {}, {}, False, {}
        ui.mod_order, ui.mod_vars = ['b-mod', 'a-mod'], {'a-mod': Var(True), 'b-mod': Var(False)}
        ui.patch_vars = {'60fps': Var(True)}
        ui.messagebox = mock.Mock()
        ui.remap_ini_path = self.folder / 'input.ini'
        ui.remap_ini_path.write_text(config.DEFAULT_INPUT_INI, encoding='utf-8')
        ui.remap_lines = config.load_input_ini(ui.remap_ini_path)[1]

    def test_mods_and_patches_are_written_whole(self):
        with mock.patch.object(L.textfile, 'write', wraps=L.textfile.write) as write:
            self.ui.collect()
        written = [Path(call.args[0]).name for call in write.call_args_list]
        self.assertIn('mods.json', written)
        self.assertIn('patches.json', written)
        self.assertEqual(json.loads((self.folder / 'mods.json').read_text(encoding='utf-8')),
                         {'order': ['b-mod', 'a-mod'], 'disabled': ['b-mod']})
        self.assertEqual(json.loads((self.folder / 'patches.json').read_text(encoding='utf-8')),
                         {'enabled': ['60fps'], 'disabled': []})

    def test_a_write_cut_off_keeps_the_mods_order(self):
        mods = self.folder / 'mods.json'
        mods.write_text('{"order": ["a-mod", "b-mod"], "disabled": []}', encoding='utf-8')
        real = os.replace

        def replace(source, target):
            if Path(target).name == 'mods.json':
                raise FULL
            return real(source, target)
        with mock.patch.object(textfile.os, 'replace', side_effect=replace):
            with self.assertRaises(OSError):
                self.ui.collect()
        self.assertEqual(json.loads(mods.read_text(encoding='utf-8'))['order'], ['a-mod', 'b-mod'])
        self.assertFalse(mods.with_name('mods.json.tmp').exists())

    def test_the_layout_is_written_whole(self):
        with mock.patch.object(L.textfile, 'write', wraps=L.textfile.write) as write:
            self.assertTrue(self.ui.write_layout())
        self.assertEqual([Path(call.args[0]) for call in write.call_args_list], [self.ui.remap_ini_path])
        self.assertEqual(config.keyboard_layout(self.ui.remap_ini_path.read_text(encoding='utf-8').splitlines()),
                         'ds3')

    def test_a_layout_that_cannot_be_written_leaves_input_ini(self):
        before = self.ui.remap_ini_path.read_bytes()
        with mock.patch.object(textfile.os, 'replace', side_effect=FULL):
            self.assertFalse(self.ui.write_layout())
        self.ui.messagebox.showerror.assert_called_once()
        self.assertEqual(self.ui.remap_ini_path.read_bytes(), before)


@unittest.skipUnless(os.name == 'nt', 'a read-only file can be replaced on Linux')
class ReadOnlyIniTests(Folder):
    """A read-only or locked bbport.ini stopped the launcher in the one-time move of older settings, and Play
    Bloodborne.exe (--play) when the file lacked a value it adds."""

    def setUp(self):
        super().setUp()
        self.ini = self.folder / 'bbport.ini'
        for patch in (mock.patch.dict(os.environ, {'BB_CONFIG': str(self.ini)}),
                      mock.patch.object(textfile.time, 'sleep')):
            patch.start()
            self.addCleanup(patch.stop)
        self.addCleanup(lambda: self.ini.exists() and os.chmod(self.ini, stat.S_IREAD | stat.S_IWRITE))

    def read_only(self, text):
        self.ini.write_text(text, encoding='utf-8')
        os.chmod(self.ini, stat.S_IREAD)

    def test_the_older_settings_hold_for_this_start(self):
        self.read_only('upscaler=fsr3\nfsr411_backend=vk\n')
        values, _lines = L.load_ini({'object_motion_cache': True})
        self.assertEqual(values['object_motion_cache'], '1')
        self.assertEqual(len(textfile.REPAIRS), 1)
        self.assertIn('cannot be written', textfile.REPAIRS[0])
        self.assertIn('object_motion_cache=1', textfile.REPAIRS[0])
        L.load_ini({'object_motion_cache': True})
        self.assertEqual(len(textfile.REPAIRS), 1)  # one line for the log, however often it is read
        self.assertEqual(self.ini.read_text(encoding='utf-8'), 'upscaler=fsr3\nfsr411_backend=vk\n')

    def test_a_hand_edit_that_cannot_be_repaired_leaves_no_pile_of_copies(self):
        """The repair of a hand edit kept a copy as .bad before writing: with the file read-only, every load
        (several per session) made one more, .bad2, .bad3, … and the log said nothing."""
        self.read_only('upscaler=fsr3\nfsr411_backend=vk\nsharpness=0,5\n')
        for _load in range(3):
            self.assertEqual(L.load_ini()[0]['sharpness'], '0.50')  # as meant, for this start
        self.assertEqual(os.listdir(self.folder), ['bbport.ini'])
        self.assertEqual(self.ini.read_text(encoding='utf-8'), 'upscaler=fsr3\nfsr411_backend=vk\nsharpness=0,5\n')
        self.assertEqual(len(textfile.REPAIRS), 1)
        self.assertIn('cannot be written', textfile.REPAIRS[0])
        self.assertIn('sharpness=0.50', textfile.REPAIRS[0])

    def test_play_bloodborne_exe_starts_the_game_anyway(self):
        self.read_only('upscaler=fsr3\n')  # no fsr411_backend: --play adds it
        user = self.folder / 'user'
        settings = {**L.APP_DEFAULTS, 'user_dir': str(user)}
        process = mock.Mock(stdout=io.BytesIO(b'Game: started\n'))
        process.wait.return_value = 0
        with mock.patch.object(L, 'attach_stdio'), mock.patch.object(L, 'game_underway', return_value=False), \
                mock.patch.object(L, 'misplaced_saves', return_value=(None, None)), \
                mock.patch.object(L.saves, 'auto_backup'), mock.patch.object(L.display, 'Placer'), \
                mock.patch.object(L.trophies, 'Tracker'), mock.patch.object(L, 'remember_window'), \
                mock.patch.object(L.bbport_fsr411, 'default_backend', return_value='vk'), \
                mock.patch.object(L.subprocess, 'Popen', return_value=process) as start:
            self.assertEqual(L.play_without_window(settings), 0)
        start.assert_called_once()
        log = (user / 'last_run.log').read_text(encoding='utf-8')
        self.assertIn('cannot be written', log)
        self.assertIn('fsr411_backend=vk', log)
        self.assertIn('Game: started', log)
        self.assertEqual(self.ini.read_text(encoding='utf-8'), 'upscaler=fsr3\n')


class BenchmarkBackupTests(Folder):
    """The route benchmark of the 1.9.3 test builds left its own save in place of the player's when it did not
    finish; the launcher deleted that save before it put the player's back, and a file in use left part of it."""

    def setUp(self):
        super().setUp()
        self.user = self.folder / 'user'
        self.live, self.backup = self.user / 'savedata', self.user / 'savedata.benchmark-backup'

    @staticmethod
    def save(folder, who):
        (folder / '1' / 'CUSA00207' / 'SPRJ0005').mkdir(parents=True)
        (folder / '1' / 'CUSA00207' / 'SPRJ0005' / 'userdata0000').write_text(who, encoding='utf-8')

    @staticmethod
    def who(folder):
        return (folder / '1' / 'CUSA00207' / 'SPRJ0005' / 'userdata0000').read_text(encoding='utf-8')

    def test_the_players_saves_come_back_and_the_tests_are_kept(self):
        self.save(self.live, 'test')
        self.save(self.backup, 'player')
        L.restore_benchmark_backup(self.user)
        self.assertEqual(self.who(self.live), 'player')
        self.assertEqual(self.who(self.user / 'savedata.benchmark'), 'test')
        self.assertFalse(self.backup.exists())
        self.assertEqual(len(textfile.REPAIRS), 1)
        self.assertIn('are back', textfile.REPAIRS[0])
        # Another time: the save put aside before stays, this one gets a name of its own.
        self.save(self.backup, 'player again')
        L.restore_benchmark_backup(self.user)
        self.assertEqual(self.who(self.live), 'player again')
        self.assertEqual(sorted(p.name.startswith('savedata.benchmark ') for p in self.user.iterdir()),
                         [False, False, True])
        self.assertEqual(self.who(self.user / 'savedata.benchmark'), 'test')

    def test_nothing_happens_without_a_backup(self):
        self.save(self.live, 'player')
        L.restore_benchmark_backup(self.user)
        self.assertEqual((self.who(self.live), textfile.REPAIRS, sorted(os.listdir(self.user))),
                         ('player', [], ['savedata']))

    def test_without_saves_in_place_the_backup_is_renamed(self):
        self.save(self.backup, 'player')
        L.restore_benchmark_backup(self.user)
        self.assertEqual((self.who(self.live), sorted(os.listdir(self.user))), ('player', ['savedata']))

    @unittest.skipUnless(os.name == 'nt', 'only Windows keeps a folder with a file open in it from being renamed')
    def test_saves_in_use_stay_as_they_are(self):
        self.save(self.live, 'test')
        self.save(self.backup, 'player')
        with open(self.live / '1' / 'CUSA00207' / 'SPRJ0005' / 'userdata0000', 'rb'):
            L.restore_benchmark_backup(self.user)
        self.assertEqual((self.who(self.live), self.who(self.backup)), ('test', 'player'))
        self.assertIn('could not be put back', textfile.REPAIRS[0])
        self.assertIn('the next start tries again', textfile.REPAIRS[0])

    def test_the_saves_in_place_go_back_when_the_players_cannot_come(self):
        self.save(self.live, 'test')
        self.save(self.backup, 'player')
        real = Path.rename

        def rename(path, target):
            if path.name == 'savedata.benchmark-backup':
                raise PermissionError(13, 'Access is denied')
            return real(path, target)
        with mock.patch.object(L.Path, 'rename', autospec=True, side_effect=rename):
            L.restore_benchmark_backup(self.user)
        self.assertEqual((self.who(self.live), self.who(self.backup)), ('test', 'player'))
        self.assertFalse((self.user / 'savedata.benchmark').exists())
        self.assertIn('could not be put back', textfile.REPAIRS[0])

    def test_a_saves_folder_that_cannot_be_reached_does_not_stop_the_launcher(self):
        """Path.is_dir() raises for more than a missing folder (a network drive that refuses the sign-in): the
        check was inside the old try, and main() must still go on to the window or --play."""
        self.save(self.backup, 'player')
        with mock.patch.object(L.Path, 'is_dir', side_effect=OSError(1326, 'The user name or password is incorrect')):
            L.restore_benchmark_backup(self.user)
        self.assertEqual((self.who(self.backup), textfile.REPAIRS, sorted(os.listdir(self.user))),
                         ('player', [], ['savedata.benchmark-backup']))

    def test_the_launcher_puts_them_back_at_every_start(self):
        source = (ROOT / 'launcher' / 'bbport_launcher_win.py').read_text(encoding='utf-8')
        main = source[source.index('def main():'):source.index("    # Without a usable game folder there is nothing to play yet")]
        self.assertIn("restore_benchmark_backup(Path(settings.get('user_dir') or DATA_DIR / 'user'))", main)
        self.assertNotIn('rmtree', main)  # the saves in place are never deleted


if __name__ == '__main__':
    unittest.main()
