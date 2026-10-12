# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Save integrity, real cross-process leases, injected I/O failures and killed restores."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import save_manager as saves
from save_access import SaveAccess, SaveBusyError, JOURNAL_NAME

NATIVE = os.environ.get('BB_SAVE_ACCESS_TEST')


def files_of(root):
    if not (root / 'savedata').exists():
        return {}
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in (root / 'savedata').rglob('*') if p.is_file()}


class SaveManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='workshop-saves-')
        self.root = Path(self.temp.name) / 'custom saves Ω'; self.root.mkdir()
        self.manager = saves.SaveManager(self.root)
        self.data = self.root / 'savedata/0/CUSA03173/SPRJ0005/userdata0010'
        self.data.parent.mkdir(parents=True); self.data.write_bytes(b'original save\x00\x01')
        metadata = self.root / 'savedata/0/CUSA03173/SPRJ0005.sce_sys'
        metadata.mkdir(); (metadata / 'param.bin').write_bytes(b'original metadata')
        memory = self.root / 'savedata/0/CUSA03173.memory'
        memory.mkdir(); (memory / 'memory.dat').write_bytes(b'save memory')
        (self.root / 'savedata/0/CUSA03173/empty-slot').mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def test_manual_snapshot_copies_complete_tree_without_mutating_sources(self):
        before = files_of(self.root)
        (self.root / 'cache').mkdir(); (self.root / 'cache/secret-cache').write_bytes(b'private cache')
        (self.root / 'settings.json').write_bytes(b'private credentials')
        archive = self.manager.snapshot('Before the boss')
        manifest = saves.verify_backup(archive)
        self.assertEqual(manifest['label'], 'Before the boss')
        self.assertEqual(manifest['category'], 'manual')
        self.assertIn('savedata/0/CUSA03173/empty-slot', manifest['directories'])
        with zipfile.ZipFile(archive) as bundle:
            self.assertEqual(set(bundle.namelist()) - {'manifest.json'}, set(before))
            for path, data in before.items(): self.assertEqual(bundle.read(path), data)
        self.assertEqual(files_of(self.root), before)

    def test_restore_creates_verified_rollback_and_can_reverse_it(self):
        archive = self.manager.snapshot('Earlier save')
        earlier = files_of(self.root)
        self.data.write_bytes(b'current progress')
        current = files_of(self.root)
        result = self.manager.restore(archive)
        self.assertEqual(files_of(self.root), earlier)
        self.assertEqual(saves.verify_backup(result['rollback'])['category'], 'rollback')
        self.manager.restore(result['rollback'])
        self.assertEqual(files_of(self.root), current)
        self.assertFalse((self.root / JOURNAL_NAME).exists())

    def test_prelaunch_snapshot_retention_protects_manual_rollback_and_corrupt_files(self):
        manual = self.manager.snapshot('Keep forever')
        rollback = self.manager.restore(manual)['rollback']
        corrupt = self.manager.backups / 'corrupt-auto.zip'; corrupt.write_bytes(b'broken zip')
        newest = None
        for n in range(4):
            self.data.write_bytes(bytes([n]))
            newest = self.manager.prepare_launch(retention=2)['snapshot']
        records = self.manager.list_snapshots()
        autos = [r for r in records if r['status'] == 'verified' and r['manifest']['category'] == 'auto']
        self.assertEqual(len(autos), 2)
        self.assertIn(newest, [r['path'] for r in autos])
        self.assertTrue(manual.exists() and rollback.exists() and corrupt.exists())
        self.assertEqual(next(r for r in records if r['path'] == corrupt)['status'], 'invalid')

    def test_newest_snapshot_is_kept_even_if_system_clock_moves_backwards(self):
        self.manager.prepare_launch(retention=2)
        original = saves.datetime
        with patch.object(saves, 'datetime') as clock:
            clock.now.return_value = original(2001, 1, 1, tzinfo=saves.timezone.utc)
            newest = self.manager.prepare_launch(retention=1)['snapshot']
        autos = [r for r in self.manager.list_snapshots() if r['status'] == 'verified' and r['manifest']['category'] == 'auto']
        self.assertEqual([r['path'] for r in autos], [newest])

    def test_first_launch_and_disabled_automatic_backup(self):
        empty = self.root / 'fresh user'
        result = saves.SaveManager(empty).prepare_launch()
        self.assertIsNone(result['snapshot'])
        result = self.manager.prepare_launch(automatic=False)
        self.assertIsNone(result['snapshot'])
        self.assertFalse(self.manager.backups.exists())

    def test_invalid_retention_or_label_does_not_publish_a_backup(self):
        for keep in (0, 101, '10', True):
            with self.assertRaises(saves.SaveManagerError):self.manager.prepare_launch(retention=keep)
        with self.assertRaises(saves.SaveManagerError):self.manager.snapshot('x' * 81)
        self.assertFalse(self.manager.backups.exists())

    def test_empty_manual_snapshot_is_not_presented_as_progress_backup(self):
        shutil.rmtree(self.root / 'savedata')
        with self.assertRaises(saves.SaveManagerError):self.manager.snapshot('Nothing')

    def test_busy_game_or_other_manager_blocks_all_mutation(self):
        before = files_of(self.root)
        with SaveAccess(self.root, check_game=False):
            with self.assertRaises(SaveBusyError):self.manager.snapshot('Blocked')
            with self.assertRaises(SaveBusyError):self.manager.prepare_launch()
        with patch('save_access.native_game_running', return_value=True):
            with self.assertRaises(SaveBusyError):self.manager.snapshot('Game paused')
        self.assertEqual(files_of(self.root), before)
        self.assertFalse(self.manager.backups.exists())

    def test_custom_folder_import_requires_explicit_choice(self):
        archive = self.manager.snapshot('Import')
        other = self.root.parent / 'another location'; manager = saves.SaveManager(other)
        with self.assertRaises(saves.SaveManagerError):manager.restore(archive)
        self.assertFalse((other / 'savedata').exists())
        manager.restore(archive, allow_other_folder=True)
        self.assertEqual(files_of(other), files_of(self.root))

    def test_corrupt_or_truncated_zip_is_rejected_before_touching_saves(self):
        archive = self.manager.snapshot('Valid')
        archive.write_bytes(archive.read_bytes()[:80])
        before = files_of(self.root)
        with self.assertRaises(saves.InvalidBackupError):self.manager.restore(archive)
        self.assertEqual(files_of(self.root), before)
        self.assertFalse((self.root / JOURNAL_NAME).exists())

    def test_tampered_save_payload_or_extra_entries_are_rejected(self):
        archive = self.manager.snapshot('Valid')
        with zipfile.ZipFile(archive) as bundle:contents = {name: bundle.read(name) for name in bundle.namelist()}
        for variant in ('tampered', 'extra'):
            bad = self.root / (variant + '.zip')
            changed = dict(contents)
            if variant == 'tampered':changed[next(n for n in changed if n != 'manifest.json')] = b'changed'
            else:changed['../../outside'] = b'danger'
            with zipfile.ZipFile(bad, 'w') as bundle:
                for path, data in changed.items():bundle.writestr(path, data)
            with self.assertRaises(saves.InvalidBackupError):saves.verify_backup(bad)

    def test_manifest_rejects_traversal_case_conflicts_and_missing_parents(self):
        archive = self.manager.snapshot('Valid'); original = saves.verify_backup(archive)
        for name in ('savedata/0/CUSA03173/../outside', r'savedata\0\CUSA03173\outside',
                     '/savedata/0/CUSA03173/outside', 'savedata/0/CUSA03173/CON',
                     'savedata/0/CUSA03173/not-a-directory/child'):
            manifest = copy.deepcopy(original); manifest['files'][0]['path'] = name
            with self.assertRaises(saves.InvalidBackupError):saves._validate_manifest(manifest)
        manifest = copy.deepcopy(original)
        record = dict(manifest['files'][0]); record['path'] = record['path'].replace('memory.dat', 'MEMORY.DAT')
        manifest['files'].append(record)
        with self.assertRaises(saves.InvalidBackupError):saves._validate_manifest(manifest)

    def test_symlinked_live_data_and_backup_are_rejected(self):
        archive = self.manager.snapshot('Valid')
        outside = self.root.parent / 'outside'; outside.write_bytes(b'outside data')
        try:
            (self.data.parent / 'linked').symlink_to(outside)
        except OSError:self.skipTest('Symlink creation is unavailable.')
        with self.assertRaises(saves.SaveManagerError):self.manager.snapshot('Unsafe')
        linked = self.root / 'linked.zip'; linked.symlink_to(archive)
        with self.assertRaises(saves.SaveManagerError):saves.verify_backup(linked)

    def test_changed_source_is_rejected_or_windows_writer_is_denied(self):
        old_write = zipfile.ZipFile.writestr
        def writing(archive, *args, **kwargs):
            self.data.write_bytes(b'new data from a concurrent editor')
            return old_write(archive, *args, **kwargs)
        with patch.object(zipfile.ZipFile, 'writestr', writing):
            with self.assertRaises((SaveBusyError, PermissionError)):self.manager.snapshot('Changed source')
        self.assertEqual(list(self.manager.backups.glob('*.zip')), [])
        self.assertEqual(list(self.manager.backups.glob('*.partial')), [])

    def test_write_failure_and_interruption_never_publish_partial_backups(self):
        before = files_of(self.root)
        for error in (OSError('disk full'), KeyboardInterrupt()):
            with patch.object(zipfile.ZipFile, 'open', side_effect=error):
                with self.assertRaises(type(error)):self.manager.snapshot('Interrupted')
            self.assertEqual(list(self.manager.backups.glob('*.zip')), [])
            self.assertEqual(list(self.manager.backups.glob('*.partial')), [])
        self.assertEqual(files_of(self.root), before)

    def test_failed_final_rename_restores_previous_progress(self):
        archive = self.manager.snapshot('Earlier'); self.data.write_bytes(b'current progress')
        before = files_of(self.root); original = os.replace
        def replace(source, target):
            if Path(source).as_posix().endswith('/new/savedata'):
                raise OSError('simulated Windows sharing violation')
            return original(source, target)
        with patch.object(os, 'replace', replace):
            with self.assertRaises(OSError):self.manager.restore(archive)
        self.assertEqual(files_of(self.root), before)
        self.assertFalse((self.root / JOURNAL_NAME).exists())

    def test_failed_commit_journal_rolls_back_current_progress(self):
        archive = self.manager.snapshot('Earlier'); self.data.write_bytes(b'current progress')
        before = files_of(self.root); original = saves._atomic_json
        def write(path, data):
            if data.get('phase') == 'committed':raise OSError('journal flush failed')
            return original(path, data)
        with patch.object(saves, '_atomic_json', write):
            with self.assertRaises(OSError):self.manager.restore(archive)
        self.assertEqual(files_of(self.root), before)

    def interrupted_restore(self, phase):
        archive = self.manager.snapshot('Earlier'); self.data.write_bytes(b'current progress')
        before = files_of(self.root)
        script = ('import os;from pathlib import Path;import save_manager as s;'
                  f'm=s.SaveManager({str(self.root)!r});original=os.replace;phase={phase!r}\n'
                  'def replace(source,target):\n'
                  ' original(source,target)\n'
                  ' if phase=="old_moved" and Path(source)==m.root/"savedata":os._exit(23)\n'
                  ' if phase=="new_installed" and Path(source).as_posix().endswith("/new/savedata"):os._exit(23)\n'
                  'os.replace=replace\n'
                  'if phase=="committed":m._finish=lambda *a,**k:os._exit(23)\n'
                  f'm.restore({str(archive)!r})\n')
        environment = {**os.environ, 'PYTHONPATH': str(ROOT / 'scripts')}
        child = subprocess.run([sys.executable, '-c', script], env=environment, timeout=20,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(child.returncode, 23, child.stderr.decode(errors='replace'))
        self.assertTrue((self.root / JOURNAL_NAME).exists())
        return before

    def test_killed_restore_after_old_tree_move_recovers_before_launch(self):
        before = self.interrupted_restore('old_moved')
        self.assertFalse((self.root / 'savedata').exists())
        result = self.manager.prepare_launch(automatic=False)
        self.assertIsNotNone(result['recovered'])
        self.assertEqual(files_of(self.root), before)

    def test_killed_restore_after_new_tree_install_recovers_previous_progress(self):
        before = self.interrupted_restore('new_installed')
        self.manager.recover()
        self.assertEqual(files_of(self.root), before)

    def test_killed_restore_after_commit_keeps_verified_restored_tree(self):
        self.interrupted_restore('committed')
        restored = files_of(self.root)
        self.manager.recover()
        self.assertEqual(files_of(self.root), restored)
        self.assertFalse((self.root / JOURNAL_NAME).exists())

    def test_damaged_previous_tree_recovers_from_verified_rollback_zip(self):
        before = self.interrupted_restore('old_moved')
        state = json.loads((self.root / JOURNAL_NAME).read_text())
        previous = self.root / ('.workshop-restore-' + state['id']) / 'previous'
        (previous / '0/CUSA03173/SPRJ0005/userdata0010').write_bytes(b'damaged old tree')
        self.manager.recover()
        self.assertEqual(files_of(self.root), before)

    def test_malformed_journal_never_changes_saves(self):
        before = files_of(self.root)
        (self.root / JOURNAL_NAME).write_text('{incomplete journal')
        with self.assertRaises(saves.InvalidBackupError):self.manager.prepare_launch(automatic=False)
        self.assertEqual(files_of(self.root), before)

    def test_interprocess_python_lease_and_release_after_termination(self):
        script = ('import sys,time;from save_access import SaveAccess;'
                  f'l=SaveAccess({str(self.root)!r},check_game=False);l.__enter__();'
                  'print("READY",flush=True);time.sleep(60)')
        environment = {**os.environ, 'PYTHONPATH': str(ROOT / 'scripts')}
        child = subprocess.Popen([sys.executable, '-c', script], env=environment, stdout=subprocess.PIPE)
        try:
            self.assertEqual(child.stdout.readline().strip(), b'READY')
            with self.assertRaises(SaveBusyError):self.manager.snapshot('Blocked')
        finally:
            child.kill(); child.wait(timeout=5); child.stdout.close()
        self.assertTrue(self.manager.snapshot('After process exit').exists())

    @unittest.skipUnless(NATIVE, 'Native lease fixture was not supplied.')
    def test_native_runtime_blocks_manager_until_process_exit(self):
        child = subprocess.Popen([NATIVE, str(self.root), 'hold'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            self.assertEqual(child.stdout.readline().strip(), b'ACQUIRED')
            with self.assertRaises(SaveBusyError):self.manager.snapshot('Blocked native game')
        finally:
            child.kill(); child.wait(timeout=5); child.stdout.close(); child.stderr.close()
        self.assertTrue(self.manager.snapshot('After native exit').exists())

    @unittest.skipUnless(NATIVE, 'Native lease fixture was not supplied.')
    def test_manager_lease_blocks_native_startup_and_pending_restore(self):
        with SaveAccess(self.root, check_game=False):
            result = subprocess.run([NATIVE, str(self.root)], capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 3)
        result = subprocess.run([NATIVE, str(self.root)], capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        (self.root / JOURNAL_NAME).write_text('{}')
        result = subprocess.run([NATIVE, str(self.root)], capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 3)
        self.assertIn(b'Open Save Manager', result.stderr)

    @unittest.skipUnless(os.name == 'nt', 'Windows file-sharing test.')
    def test_active_windows_writer_is_rejected_without_publishing_backup(self):
        with self.data.open('r+b'):
            with self.assertRaises(SaveBusyError):self.manager.snapshot('File still open')
        self.assertEqual(list(self.manager.backups.glob('*.zip')), [])
        self.assertEqual(list(self.manager.backups.glob('*.partial')), [])


if __name__ == '__main__':
    unittest.main()
