# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Profile transaction, recovery and public ABI tests. No NVIDIA GPU is simulated."""
import ctypes
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import nvidia_fg_preset as fg


class Database:
    def __init__(self):
        self.settings = {}
        self.exists = False
        self.opens = self.saves = 0
        self.fail = None
        self.foreign = False

    def driver(self):
        db = self
        class Driver:
            def open(self, executable, name, create):
                db.opens += 1
                if db.foreign:
                    raise fg.ProfileError('External application profile')
                self.local = dict(db.settings)
                if not db.exists and not create:
                    return False
                return True
            def get(self, key):
                return self.local.get(key)
            def set(self, key, value):
                if value is None:
                    self.local.pop(key, None)
                else:
                    self.local[key] = value
            def save(self):
                db.saves += 1
                if db.fail == 'before':
                    raise fg.ProfileError('Save failed')
                db.settings, db.exists = self.local, True
                if db.fail == 'after':
                    raise fg.ProfileError('Interrupted after commit')
            def close(self):
                pass
        return Driver()


class PresetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.exe = self.root / 'My Modded Port' / 'bin' / 'bb-probe.exe'
        self.store = self.root / 'profile-backups'
        self.db = Database()

    def apply(self, value):
        return fg.apply(value, self.exe, self.store, self.db.driver)

    def journal(self):
        return next(self.store.glob('*.json'))

    def test_abi(self):
        # From the public NVAPI header's pack(4) setting and pack(8) profile/app.
        self.assertEqual(ctypes.sizeof(fg.Setting), 12320)
        self.assertEqual(fg.Setting.current.offset, 8220)
        self.assertEqual(ctypes.sizeof(fg.Application), 12296)
        self.assertEqual(ctypes.sizeof(fg.Profile), 4116)
        self.assertEqual(bytes(fg.wide('猟師')), '猟師'.encode('utf-16-le') + bytes(4092))

    def test_default_does_not_load_driver(self):
        self.assertIn('no profile changes', self.apply('default'))
        self.assertEqual(self.db.opens, 0)
        self.assertFalse(self.store.exists())

    def test_choices_and_restore_preserve_other_settings(self):
        self.db.exists = True
        self.db.settings = {123: 456, fg.ENABLE: 0, fg.PRESET: 27}
        for index, preset in enumerate('abc', 1):
            self.assertIn('waiting for runtime confirmation', self.apply(preset))
            self.assertEqual(self.db.settings, {123: 456, fg.ENABLE: 1, fg.PRESET: index})
        self.assertEqual(self.db.opens, 6)
        self.assertIn('restored', self.apply('default'))
        self.assertEqual(self.db.settings, {123: 456, fg.ENABLE: 0, fg.PRESET: 27})
        self.assertFalse(list(self.store.glob('*.json')))

    def test_restore_inherited_settings_by_removing_own_override(self):
        self.apply('c')
        self.assertEqual(self.db.settings, {fg.ENABLE: 1, fg.PRESET: 3})
        self.apply('default')
        self.assertEqual(self.db.settings, {})

    def test_unchanged_choice_does_not_save_driver_again(self):
        self.apply('b')
        self.apply('b')
        self.assertEqual(self.db.saves, 1)

    def test_interruption_before_and_after_driver_commit(self):
        for point in ('before', 'after'):
            with self.subTest(point=point):
                self.db.fail = point
                with self.assertRaises(fg.ProfileError):
                    self.apply('c')
                self.assertEqual(json.loads(self.journal().read_text())['pending'][str(fg.PRESET)], 3)
                self.db.fail = None
                self.apply('default')
                self.assertEqual(self.db.settings, {})
                self.assertFalse(list(self.store.glob('*.json')))

    def test_atomic_backup_must_succeed_before_driver_commit(self):
        with patch.object(fg.os, 'replace', side_effect=OSError('Disk full')):
            with self.assertRaises(OSError):
                self.apply('a')
        self.assertEqual(self.db.saves, 0)
        self.assertFalse(list(self.store.iterdir()))

    def test_external_changes_are_kept(self):
        self.apply('b')
        self.db.settings[fg.PRESET] = 99
        before = dict(self.db.settings)
        with self.assertRaisesRegex(fg.ProfileError, 'outside'):
            self.apply('default')
        self.assertEqual(self.db.settings, before)
        self.assertTrue(self.journal().exists())

    def test_existing_external_application_profile_is_not_modified(self):
        self.db.foreign = True
        with self.assertRaises(fg.ProfileError):
            self.apply('a')
        self.assertEqual(self.db.saves, 0)

    def test_invalid_and_malformed_backups_never_reach_driver(self):
        with self.assertRaises(ValueError):
            self.apply('m')
        self.apply('a')
        self.journal().write_text('{broken')
        before = self.db.opens
        with self.assertRaises(ValueError):
            self.apply('default')
        self.assertEqual(self.db.opens, before)

    def test_missing_original_profile_keeps_backup(self):
        self.apply('c')
        self.db.exists = False
        with self.assertRaisesRegex(fg.ProfileError, 'missing'):
            self.apply('default')
        self.assertTrue(self.journal().exists())

    def test_custom_menu_path_and_safe_failure_message(self):
        config = self.root / 'custom name.ini'
        config.with_suffix('.menu.ini').write_text('frame_generation=nvidia\nnvidia_fg_preset=C\n')
        with patch.object(fg, 'apply', return_value='requested') as apply:
            self.assertEqual(fg.configure_launch(config, self.exe, {'APPDATA': str(self.root)}), 'requested')
            self.assertEqual(apply.call_args.args[0], 'c')
        config.with_suffix('.menu.ini').write_text('frame_generation=fsr\nnvidia_fg_preset=c\n')
        with patch.object(fg, 'apply', side_effect=OSError(r'C:\Users\Private\secret')) as apply:
            result = fg.configure_launch(config, self.exe, {})
            self.assertEqual(apply.call_args.args[0], 'default')
            self.assertNotIn('Private', result)
            self.assertIn('not applied', result)


if __name__ == '__main__':
    unittest.main()
