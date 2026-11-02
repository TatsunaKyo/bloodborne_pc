"""The game's monitor and window (launcher/bbport_display.py), the output resolution's own sizes and
the DLC status on Game & language (launcher/bbport_launcher_win.py)."""
from paths import ROOT
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(ROOT / 'launcher'))
sys.path.insert(0, str(ROOT / 'scripts'))
import bbport_display as display  # noqa: E402
import bbport_launcher_win as L  # noqa: E402

SOURCE = (ROOT / 'launcher' / 'bbport_launcher_win.py').read_text(encoding='utf-8')


class SizeTests(unittest.TestCase):
    def test_sizes_the_player_types(self):
        self.assertEqual(display.parse_size('2400x1080'), (2400, 1080))
        self.assertEqual(display.parse_size(' 2400 × 1080 '), (2400, 1080))
        self.assertEqual(display.parse_size('1919*1081'), (1918, 1080))  # even, for the upscalers
        for wrong in ('', 'abc', '100x100', '8000x4000', '1920x', None):
            self.assertIsNone(display.parse_size(wrong), wrong)

    def test_a_window_bigger_than_the_screen_shrinks_in_shape(self):
        self.assertEqual(display.fit((2560, 1440), (2540, 1350)), (2400, 1350))
        self.assertEqual(display.fit((1600, 900), (2540, 1350)), (1600, 900))

    def test_narrower_than_16_9(self):
        self.assertTrue(display.narrower_than_16_9((1920, 1200)))
        self.assertFalse(display.narrower_than_16_9((1920, 1080)))
        self.assertFalse(display.narrower_than_16_9((2400, 1080)))

    def test_the_window_size_the_game_opens_at(self):
        output = (1280, 720)
        self.assertEqual(display.window_target({'window_size': 'output'}, output), output)
        self.assertEqual(display.window_target({'window_size': 'custom', 'window_custom': '1600x900'}, output),
                         (1600, 900))
        self.assertEqual(display.window_target({'window_size': 'last', 'window_last': '1700x950'}, output),
                         (1700, 950))
        self.assertEqual(display.window_target({'window_size': 'last', 'window_last': ''}, output), output)
        self.assertIsNone(display.window_target({'window_size': 'game'}, output))  # left alone


class MonitorTests(unittest.TestCase):
    MONITORS = [display.Monitor('\\\\.\\DISPLAY2', (0, 0, 2560, 1440), (0, 0, 2560, 1392), True, 'MSI G27CQ4'),
                display.Monitor('\\\\.\\DISPLAY1', (-2560, 0, 0, 1440), (-2560, 0, 0, 1392), False, 'MSI G27CQ4')]

    def test_main_monitor_first_then_the_others_with_their_side(self):
        with mock.patch.object(display, 'monitors', return_value=self.MONITORS):
            options = L.monitor_options()
        self.assertEqual([value for value, _t in options], ['', '\\\\.\\DISPLAY1'])
        self.assertIn('2560 × 1440', options[0][1][0])
        self.assertIn('on the left', options[1][1][0])

    def test_a_chosen_monitor_that_is_gone_stays_listed_and_the_main_one_is_used(self):
        with mock.patch.object(display, 'monitors', return_value=self.MONITORS[:1]):
            options = L.monitor_options('\\\\.\\DISPLAY3')
            self.assertEqual(options[-1][0], '\\\\.\\DISPLAY3')
            self.assertIs(display.monitor('\\\\.\\DISPLAY3'), self.MONITORS[0])

    def test_the_output_choice_keeps_any_size(self):
        # the old combobox set every size outside its list to its first entry (1280x720)
        self.assertNotIn("self.choice(f, 'output_res'", SOURCE)
        self.assertIn('self.output_choice(f)', SOURCE)

    def test_a_custom_output_survives_and_the_monitor_choice_gives_way(self):
        try:
            import tkinter as tk
            from tkinter import ttk
            root = tk.Tk()
        except Exception:  # no display (Linux CI)
            self.skipTest('no display')
        root.withdraw()
        self.addCleanup(root.destroy)

        class Stub:
            pass
        s = Stub()
        s.tk, s.ttk, s.root, s.vars = tk, ttk, root, {}
        s.ini = {**L.INI_DEFAULTS, 'output_res': '2400x1080'}
        s.app = dict(L.APP_DEFAULTS)
        s.px = lambda value: value
        for name in ('var', 'size_entry', 'output_choice', 'game_monitor_size'):
            setattr(s, name, getattr(L.Launcher, name).__get__(s))
        s.output_choice(ttk.Frame(root))
        self.assertEqual(s.var('output_res', 'ini').get(), '2400x1080')
        s.var('output_display', 'app').set(True)
        s.var('output_res', 'ini').set('1920x1080')  # another page chose a size: the monitor's no longer
        if s.game_monitor_size() != (1920, 1080):
            self.assertFalse(s.var('output_display', 'app').get())


class DlcTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.user = self.tmp / 'user'

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def status(self, dlc, edition='CUSA00207'):
        with mock.patch.object(L, 'title_id', return_value=edition):
            return L.dlc_status(str(self.tmp / 'game'), str(dlc) if dlc else '', self.user)

    def test_the_old_hunters_in_the_dlc_folder(self):
        (self.tmp / 'dlc' / 'SPEXPANSIONDLC03' / 'sce_sys').mkdir(parents=True)
        self.assertEqual(self.status(self.tmp / 'dlc')[0], 'ok')

    def test_the_mistakes_players_make(self):
        (self.tmp / 'lower' / 'spexpansiondlc03').mkdir(parents=True)
        kind, text = self.status(self.tmp / 'lower')
        self.assertEqual(kind, 'warn')
        self.assertIn('SPEXPANSIONDLC03', text)
        (self.tmp / 'itself' / 'sce_sys').mkdir(parents=True)  # the add-on chosen instead of its folder
        self.assertIn('itself', self.status(self.tmp / 'itself')[1])
        (self.tmp / 'game2').mkdir()
        (self.tmp / 'game2' / 'eboot.bin').write_bytes(b'')
        self.assertIn('game folder', self.status(self.tmp / 'game2')[1])
        self.assertEqual(self.status(self.tmp / 'nowhere')[0], 'warn')
        (self.tmp / 'empty').mkdir()
        self.assertEqual(self.status(self.tmp / 'empty')[0], 'warn')

    def test_the_game_of_the_year_edition_has_it(self):
        self.assertEqual(self.status('', edition='CUSA03173')[0], 'ok')
        self.assertEqual(self.status('')[0], 'none')

    def test_shadps4s_layout_in_the_saves_folder(self):
        (self.user / 'addcont' / 'CUSA00207' / 'SPEXPANSIONDLC03').mkdir(parents=True)
        self.assertEqual(self.status('')[0], 'ok')


if __name__ == '__main__':
    unittest.main()
