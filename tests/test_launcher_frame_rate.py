# SPDX-License-Identifier: GPL-2.0-or-later
"""The frame rate the player sets reaches the game (R88: "FPS set to 30 in the launcher does not change in game").

Which value wins: the launcher writes its frame rate (settings.json fps_mode and frame_cap) to bbport.ini before
every start and starts the game with it; run.py takes bbport.ini's at every start, the in-game restart too
(refresh_shared_graphics); the game's PC Settings page writes bbport.ini, and the launcher takes a change from there
unless it has an unsaved one of its own. Two ways lost a choice:
- the game writes the whole file whenever its menu saves anything: a frame rate the launcher saved while the game
  ran was overwritten with the one the game started with, and the launcher took that for the game's choice;
- the in-game restart inherits the previous start's environment, and run.py kept that start's vblank rate.

The launcher's settings live in a Tcl interpreter without a window, its files in a temporary folder."""
from paths import ROOT
import functools
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import tkinter
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(ROOT / 'launcher'))
import bbport_launcher_win as launcher  # noqa: E402
import bbport_textfile as textfile  # noqa: E402

spec = importlib.util.spec_from_file_location('bbport_run_frame_rate_test', ROOT / 'run.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class FramePacingTests(unittest.TestCase):
    def test_every_start_paces_its_own_frame_rate(self):
        env = {}
        for fps, hz in (('uncap', '0'), ('30', '60'), ('90', '90'), ('uncap', '0'), ('60', '60')):
            runner.frame_pacing(env, fps)  # the next one: an in-game restart with this environment
            self.assertEqual(env['BB_VBLANK_HZ'], hz, fps)

    def test_an_explicit_rate_stays(self):
        env = {'BB_VBLANK_HZ': '144'}  # measurements
        for fps in ('uncap', '30'):
            runner.frame_pacing(env, fps)
            self.assertEqual(env['BB_VBLANK_HZ'], '144')
        self.assertNotIn('BB_AUTO_VBLANK', env)


class RunningGameTests(unittest.TestCase):
    """The launcher stays open while the game it started runs; drain_output takes bbport.ini whenever the game
    writes it (sync_ini)."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.ini = self.folder / 'bbport.ini'
        self.ini.write_text('fsr411_backend=vk\nupscaler=fsr3\nfov=43\nfps_mode=uncap\nframe_cap=\n', encoding='utf-8')
        for patcher in (patch.dict(os.environ, {'BB_CONFIG': str(self.ini), 'BB_INPUT_CONFIG': ''}),
                        patch.multiple(launcher, CONFIG_DIR=self.folder, CONFIG_FILE=self.folder / 'settings.json',
                                       LANG='en'),
                        patch.object(textfile, 'REPAIRS', [])):
            patcher.start()
            self.addCleanup(patcher.stop)
        tcl = tkinter.Tcl()
        ui = launcher.Launcher.__new__(launcher.Launcher)
        ui.tk = types.SimpleNamespace(TclError=tkinter.TclError, **{
            kind: functools.partial(getattr(tkinter, kind), tcl) for kind in ('BooleanVar', 'StringVar', 'DoubleVar')})
        ui.app = dict(launcher.APP_DEFAULTS)
        ui.ini, ui.ini_lines = launcher.load_ini(ui.app)
        ui.app = launcher.mirrored(ui.app, ui.ini)
        ui.vars, ui.mod_order, ui.patch_vars = {}, [], {}
        ui.remap_edits, ui.mouse_edited = {}, False
        ui.process = None
        self.ui = ui

    def play(self):
        """Play: the settings saved, the game started with them (as Launcher.play)."""
        self.ui.collect()
        self.ui.remember_game_start()
        self.ui.process = object()

    def game_saves(self, **values):
        """The game's menu saves: every key of the file, these with the game's values."""
        _values, lines = launcher.load_ini()
        launcher.save_ini({key: str(value) for key, value in values.items()}, lines)

    def next_start(self):
        """BB_FPS of the next start from the launcher, after run.py has read bbport.ini."""
        env = launcher.game_environment(self.ui.app, launcher.load_ini()[0])
        runner.refresh_shared_graphics(env, self.ini)
        return env['BB_FPS']

    def shown(self):
        return self.ui.app['fps_mode'], self.ui.var('fps_mode', 'app').get()

    def test_a_frame_rate_set_while_the_game_runs_stays(self):
        self.play()
        self.ui.var('fps_mode', 'app').set('30')
        self.ui.collect()  # the launcher's window closed while the game runs, or a button that saves
        self.game_saves(fps_mode='uncap', fov='50')  # the field of view changed in the game
        self.ui.sync_ini()
        self.assertEqual(self.shown(), ('30', '30'))
        disk = launcher.load_ini()[0]
        self.assertEqual((disk['fps_mode'], disk['fov']), ('30', '50'))  # written again, the game's change kept
        self.assertTrue(any('fps_mode=30' in line for line in textfile.REPAIRS))
        self.game_saves(fps_mode='uncap')  # the game's menu saves again before it ends
        self.ui.process = None
        self.ui.sync_ini()  # the game ended (drain_output)
        self.ui.game_started = None
        self.assertEqual(self.shown(), ('30', '30'))
        self.assertEqual(self.next_start(), '30')

    def test_a_frame_rate_chosen_in_the_game_wins(self):
        self.play()
        self.game_saves(fps_mode='60')
        self.ui.sync_ini()
        self.assertEqual(self.shown(), ('60', '60'))
        self.assertEqual(self.next_start(), '60')
        # The game restarts itself with it (drain_output: "restarting through run.py"); then the launcher's 30.
        self.ui.game_restarts()
        self.ui.var('fps_mode', 'app').set('30')
        self.ui.collect()
        self.game_saves(fps_mode='60', fov='50')
        self.ui.sync_ini()
        self.assertEqual(launcher.load_ini()[0]['fps_mode'], '30')

    def test_back_to_the_start_value_in_the_game_wins(self):
        """The game holds what its menu chose last: Unlocked again after 60 is no old value written back."""
        self.play()
        self.game_saves(fps_mode='60')
        self.ui.sync_ini()
        self.game_saves(fps_mode='uncap')  # no restart: the frame rate changes in the running game
        self.ui.sync_ini()
        self.assertEqual(self.shown(), ('uncap', 'uncap'))
        self.assertEqual(self.next_start(), 'uncap')
        self.assertEqual(textfile.REPAIRS, [])

    def test_a_launcher_choice_after_one_in_the_game_stays(self):
        self.play()
        self.game_saves(fps_mode='60')  # chosen in the game
        self.ui.sync_ini()
        self.ui.var('fps_mode', 'app').set('30')
        self.ui.collect()  # then in the launcher, saved while the game runs
        self.game_saves(fps_mode='60', fov='50')  # the game's next save writes the 60 it holds
        self.ui.sync_ini()
        self.assertEqual(self.shown(), ('30', '30'))
        self.assertEqual(self.next_start(), '30')

    def test_a_restart_seen_before_the_games_save_keeps_its_choice(self):
        """The restart line can come before the 200 ms check of bbport.ini (a busy window): the save it made is
        the game's choice, not the old start's values written back."""
        self.play()
        self.game_saves(fps_mode='30')  # chosen in the game's menu, which restarts the game
        self.ui.game_restarts()
        self.ui.sync_ini()  # the check of bbport.ini, after the line
        self.assertEqual(self.shown(), ('30', '30'))
        self.assertEqual(self.next_start(), '30')
        self.assertEqual(textfile.REPAIRS, [])

    def test_an_unsaved_launcher_choice_waits_for_play(self):
        self.play()
        self.ui.var('fps_mode', 'app').set('30')  # not saved yet
        self.game_saves(fps_mode='60')
        self.ui.sync_ini()
        self.assertEqual(self.shown(), ('uncap', '30'))
        self.ui.process = None
        self.ui.collect()  # Play
        self.assertEqual(self.next_start(), '30')

    def test_a_game_started_elsewhere_is_taken_as_it_wrote(self):
        """Steam or a shortcut: what its menu wrote is the newest choice (no start of the launcher's own)."""
        self.ui.collect()
        self.game_saves(fps_mode='60')
        self.ui.sync_ini()
        self.assertEqual(self.shown(), ('60', '60'))


if __name__ == '__main__':
    unittest.main()
