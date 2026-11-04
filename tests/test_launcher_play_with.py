# SPDX-License-Identifier: GPL-2.0-or-later
"""Controller or keyboard and mouse (the launcher's play_with): which layout input.ini holds, what
the choice writes there (in a temporary folder), and its texts in every language."""
from paths import ROOT
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(ROOT / 'launcher'))
import bbport_input_config as config  # noqa: E402
import bbport_lang  # noqa: E402
import bbport_lang_input  # noqa: E402
import bbport_launcher_win as launcher  # noqa: E402

DEFAULT = config.DEFAULT_INPUT_INI.splitlines()
DS3 = config.apply_layout(DEFAULT)
OWN = [line.replace('circle = space', 'circle = lctrl') for line in DS3]


class LayoutTests(unittest.TestCase):
    def test_shipped_ds3_and_own(self):
        self.assertEqual(config.keyboard_layout(DEFAULT), 'default')
        self.assertEqual(config.keyboard_layout(DS3), 'ds3')
        self.assertEqual(config.keyboard_layout(config.apply_layout(DS3)), 'ds3')
        self.assertEqual(config.keyboard_layout(OWN), 'own')

    def test_the_order_of_an_actions_keys_does_not_count(self):
        swapped = ['r3 = c' if line == 'r3 = q' else 'r3 = q' if line == 'r3 = c' else line for line in DEFAULT]
        self.assertNotEqual(swapped, DEFAULT)
        self.assertEqual(config.keyboard_layout(swapped), 'default')

    def test_controller_lines_and_mouse_settings_do_not_count(self):
        lines = [line.replace('# mouse_to_joystick = right', 'mouse_to_joystick = right')
                 .replace('cross = cross', 'cross = circle') for line in DEFAULT]
        self.assertEqual(config.keyboard_layout(lines), 'default')


class MouseLookSaveTests(unittest.TestCase):
    def test_off_after_the_ds3_layout_keeps_the_f7_hotkey(self):
        """The layout puts mouse_to_joystick after hotkey_toggle_mouse_to_joystick: only the first is
        the mouse look line."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'input.ini'
            path.write_text('\n'.join(DS3) + '\n', encoding='utf-8')
            mouse = config.load_input_ini(path)[4]
            self.assertTrue(mouse['enabled'])
            config.save_mouse_settings(path, dict(mouse, enabled=False), config.load_input_ini(path)[1])
            lines = path.read_text(encoding='utf-8').splitlines()
            self.assertIn('hotkey_toggle_mouse_to_joystick = f7', lines)
            self.assertEqual([line for line in lines if 'mouse_to_joystick =' in line and 'hotkey' not in line],
                             ['# mouse_to_joystick = right'])
            self.assertFalse(config.load_input_ini(path)[4]['enabled'])
            self.assertEqual(config.load_input_ini(path)[2:4], ('f7', 'f8'))


class Questions:
    """messagebox: askyesno answers `answer` and keeps the question."""
    def __init__(self, answer):
        self.answer, self.asked, self.errors = answer, [], []

    def askyesno(self, title, text, **_options):
        self.asked.append(text)
        return self.answer

    def showerror(self, title, text, **_options):
        self.errors.append(text)


@unittest.skipUnless(sys.platform == 'win32', 'Windows launcher widgets')
class ChoiceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        environment = patch.dict(os.environ, {'BB_CONFIG': str(self.folder / 'bbport.ini'), 'BB_INPUT_CONFIG': ''})
        environment.start()
        self.addCleanup(environment.stop)
        profile = patch.multiple(launcher, CONFIG_DIR=self.folder, CONFIG_FILE=self.folder / 'settings.json')
        profile.start()
        self.addCleanup(profile.stop)
        import tkinter as tk
        from tkinter import ttk
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        ui = self.ui = launcher.Launcher.__new__(launcher.Launcher)
        ui.root, ui.tk, ui.ttk, ui.dpi = self.root, tk, ttk, 1
        ui.app = dict(launcher.APP_DEFAULTS, play_with='controller')
        ui.ini, ui.ini_lines = dict(launcher.INI_DEFAULTS), []
        ui.vars, ui.mod_order, ui.patch_vars = {}, [], {}
        ui.remap_ini_path = self.folder / 'input.ini'

    def start(self, lines=None, answer=True):
        """The launcher opened with this input.ini (none: the game has not written one yet)."""
        if lines is not None:
            self.ui.remap_ini_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        self.ui.messagebox = Questions(answer)
        self.ui.remap_bindings, self.ui.remap_lines, self.ui.remap_toggle_key, self.ui.remap_reload_key, \
            self.ui.mouse_settings = config.load_input_ini(self.ui.remap_ini_path)
        self.ui.remap_edits, self.ui.mouse_edited = {}, False

    def saved(self):
        """After the settings are saved (as before PLAY): input.ini's layout, mouse look, play_with."""
        self.ui.collect()
        lines = self.ui.remap_ini_path.read_text(encoding='utf-8').splitlines()
        settings = json.loads((self.folder / 'settings.json').read_text(encoding='utf-8'))
        return config.keyboard_layout(lines), config.read_input_lines(lines)[4]['enabled'], settings['play_with']

    def test_keyboard_on_the_shipped_keys_takes_the_ds3_layout_without_asking(self):
        self.start()
        self.ui.set_play_with('keyboard')
        self.assertEqual(self.ui.messagebox.asked, [])
        self.assertEqual(self.saved(), ('ds3', True, 'keyboard'))

    def test_controller_turns_the_mouse_camera_off_and_keeps_the_keys(self):
        self.start(DS3)
        self.ui.set_play_with('controller')
        self.assertEqual(self.ui.messagebox.asked, [])
        self.assertEqual(self.saved(), ('ds3', False, 'controller'))

    def test_own_keys_are_asked_about_and_no_keeps_them(self):
        self.start(OWN, answer=False)
        self.ui.set_play_with('keyboard')
        self.assertEqual(len(self.ui.messagebox.asked), 1)
        self.assertEqual(self.saved(), ('own', True, 'keyboard'))

    def test_own_keys_yes_takes_the_ds3_layout(self):
        self.start(OWN, answer=True)
        self.ui.set_play_with('keyboard')
        self.assertEqual(self.saved(), ('ds3', True, 'keyboard'))

    def test_key_edits_not_saved_yet_count_as_own_and_both_are_saved(self):
        self.start(answer=False)
        self.ui.remap_edits = {'circle': ['lctrl']}
        self.ui.set_play_with('keyboard')
        self.assertEqual(len(self.ui.messagebox.asked), 1)
        self.assertEqual(self.saved(), ('own', True, 'keyboard'))
        self.assertEqual(self.ui.remap_bindings['circle'], ['lctrl'])

    def test_the_mouse_settings_stay_one_dict(self):
        """The Controls page's widgets write into the dict they were built with: a save keeps it."""
        self.start(DS3)
        held = self.ui.mouse_settings
        self.ui.remap_edits = {'circle': ['lctrl']}
        self.ui.set_play_with('controller')
        self.ui.collect()
        self.assertIs(self.ui.mouse_settings, held)
        self.assertFalse(held['enabled'])

    def test_the_switch_shows_and_makes_the_choice(self):
        self.start()
        switch = self.ui.device_switch(self.ui.ttk.Frame(self.root))
        controller, keyboard = switch.winfo_children()
        keyboard.invoke()
        self.assertEqual(self.ui.var('play_with', 'app').get(), 'keyboard')
        self.assertTrue(self.ui.mouse_settings['enabled'])
        controller.invoke()
        self.assertEqual(self.saved()[1:], (False, 'controller'))


class TextTests(unittest.TestCase):
    def test_every_language_has_every_text(self):
        languages = [code for code, _name in bbport_lang.LANGUAGE_NAMES if code not in ('', 'en')]
        self.assertEqual(set(bbport_lang_input.TEXTS) - {'en'}, set(languages))
        for language in languages:
            table = bbport_lang.table(language)
            for key in bbport_lang_input.KEYS:
                with self.subTest(language=language, text=key[:30]):
                    self.assertTrue(table.get(key))
                    self.assertEqual(table[key].count('\n'), key.count('\n'))


if __name__ == '__main__':
    unittest.main()
