# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Verified closed-game snapshots and journaled restoration of the original save tree."""
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import zipfile

from save_access import JOURNAL_NAME, SaveAccess, SaveBusyError, open_save_read

MAX_FILES = 10000
MAX_SAVE_BYTES = 8 * 1024 ** 3
MAX_FILE_BYTES = 1024 ** 3
MAX_MANIFEST = 2 * 1024 ** 2
CHUNK = 1024 ** 2
BACKUP_KIND = 'crowned-workshop-save-backup'


class SaveManagerError(RuntimeError):
    pass


class InvalidBackupError(SaveManagerError):
    pass


def _json(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def _sync_directory(path):
    if os.name != 'nt':
        descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _atomic_json(path, value):
    descriptor, name = tempfile.mkstemp(prefix='.save-journal-', suffix='.partial', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(_json(value)); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
        _sync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _safe_relative(name):
    if not isinstance(name, str) or not name or '\\' in name or '\x00' in name or len(name) > 1000:
        raise InvalidBackupError('Invalid save path in the backup.')
    path = PurePosixPath(name)
    parts = path.parts
    if path.is_absolute() or name != path.as_posix() or parts[0] != 'savedata':
        raise InvalidBackupError('The backup must contain only relative savedata paths.')
    for part in parts:
        if part in ('.', '..') or part.endswith((' ', '.')) or len(part) > 255 or re.search(r'[<>:"|?*\x00-\x1f]', part):
            raise InvalidBackupError('Unsafe save filename in the backup.')
        if re.fullmatch(r'(?i)(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', part):
            raise InvalidBackupError('Reserved Windows filename in the backup.')
    if len(parts) >= 2 and not re.fullmatch(r'\d{1,10}', parts[1]):
        raise InvalidBackupError('Invalid save user directory.')
    if len(parts) >= 3 and not re.fullmatch(r'[A-Z0-9_\-]{1,16}(?:\.memory)?', parts[2]):
        raise InvalidBackupError('Invalid save title directory.')
    return path


def _plain(path, directory=False):
    info = path.lstat()
    valid = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    if not valid or getattr(info, 'st_file_attributes', 0) & 0x400:
        raise SaveManagerError('Save trees and backups must not contain links or junctions.')
    return info


def _scan(root):
    tree = root / 'savedata'
    if not tree.exists():
        if tree.is_symlink():
            raise SaveManagerError('The saves tree must not be a link.')
        return [], []
    _plain(tree, directory=True)
    directories, files = ['savedata'], []

    def failed(error):
        raise error
    for parent, names, filenames in os.walk(tree, followlinks=False, onerror=failed):
        parent = Path(parent)
        for name in sorted(names):
            path = parent / name
            _plain(path, directory=True)
            relative = path.relative_to(root).as_posix(); _safe_relative(relative)
            directories.append(relative)
            if len(directories) > MAX_FILES:
                raise SaveManagerError('The saves tree contains too many directories.')
        for name in sorted(filenames):
            path = parent / name
            info = _plain(path)
            relative = path.relative_to(root).as_posix(); _safe_relative(relative)
            if info.st_size > MAX_FILE_BYTES:
                raise SaveManagerError('A save file exceeds the backup size limit.')
            files.append((relative, info.st_size, info.st_mtime_ns, info.st_ino, info.st_dev))
            if len(files) > MAX_FILES:
                raise SaveManagerError('The saves tree contains too many files.')
    if sum(f[1] for f in files) > MAX_SAVE_BYTES:
        raise SaveManagerError('The saves tree exceeds the backup size limit.')
    return sorted(directories), sorted(files)


def _validate_manifest(manifest):
    if not isinstance(manifest, dict) or manifest.get('schema_version') != 1 or manifest.get('kind') != BACKUP_KIND:
        raise InvalidBackupError('Unsupported or missing save backup manifest.')
    if manifest.get('category') not in ('auto', 'manual', 'rollback') or not re.fullmatch(r'[a-f0-9]{24}', str(manifest.get('id', ''))):
        raise InvalidBackupError('Invalid save backup identity.')
    if not re.fullmatch(r'[a-f0-9]{64}', str(manifest.get('root_id', ''))):
        raise InvalidBackupError('Invalid save-folder identity.')
    if not isinstance(manifest.get('label'), str) or len(manifest['label']) > 80:
        raise InvalidBackupError('Invalid snapshot label.')
    try:
        created = datetime.fromisoformat(manifest.get('created_utc', ''))
        if created.tzinfo is None:
            raise ValueError()
    except (TypeError, ValueError) as error:
        raise InvalidBackupError('Invalid snapshot creation time.') from error
    directories, files = manifest.get('directories'), manifest.get('files')
    if not isinstance(directories, list) or not isinstance(files, list) or len(files) > MAX_FILES or len(directories) > MAX_FILES:
        raise InvalidBackupError('Invalid save backup inventory.')
    names, folded = set(), set()
    for name in directories:
        _safe_relative(name)
        if name in names or name.casefold() in folded:
            raise InvalidBackupError('Duplicate or case-conflicting backup path.')
        names.add(name); folded.add(name.casefold())
    if 'savedata' not in names:
        raise InvalidBackupError('Missing savedata root.')
    total = 0
    for record in files:
        if not isinstance(record, dict):
            raise InvalidBackupError('Malformed save backup file record.')
        path = _safe_relative(record.get('path'))
        name = path.as_posix()
        if name in names or name.casefold() in folded or path.parent.as_posix() not in set(directories):
            raise InvalidBackupError('Duplicate file or missing parent directory.')
        names.add(name); folded.add(name.casefold())
        size, modified = record.get('size'), record.get('mtime_ns')
        if type(size) is not int or not 0 <= size <= MAX_FILE_BYTES or type(modified) is not int or modified < 0:
            raise InvalidBackupError('Invalid backup file size or timestamp.')
        if not re.fullmatch(r'[a-f0-9]{64}', str(record.get('sha256', ''))):
            raise InvalidBackupError('Missing or invalid save checksum.')
        total += size
    if total > MAX_SAVE_BYTES:
        raise InvalidBackupError('Save backup exceeds the size limit.')
    for name in directories:
        if name != 'savedata' and PurePosixPath(name).parent.as_posix() not in set(directories):
            raise InvalidBackupError('Missing backup directory parent.')
    return manifest


def verify_backup(path):
    path = Path(path)
    _plain(path)
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            names = [i.filename for i in infos]
            if len(infos) > MAX_FILES + 1 or len(set(names)) != len(names) or 'manifest.json' not in names:
                raise InvalidBackupError('Incomplete or duplicate save backup entries.')
            manifest_info = archive.getinfo('manifest.json')
            if manifest_info.file_size > MAX_MANIFEST:
                raise InvalidBackupError('Save manifest is too large.')
            manifest = _validate_manifest(json.loads(archive.read(manifest_info)))
            expected = {'manifest.json', *[record['path'] for record in manifest['files']]}
            if set(names) != expected:
                raise InvalidBackupError('Missing or unexpected save backup file.')
            for info in infos:
                mode = info.external_attr >> 16
                if stat.S_IFMT(mode) not in (0, stat.S_IFREG) or info.flag_bits & 1:
                    raise InvalidBackupError('Linked, special or encrypted backup entries are unsupported.')
            for record in manifest['files']:
                info = archive.getinfo(record['path'])
                if info.file_size != record['size']:
                    raise InvalidBackupError('Save backup size mismatch.')
                digest, size = hashlib.sha256(), 0
                with archive.open(info) as stream:
                    while block := stream.read(CHUNK):
                        digest.update(block); size += len(block)
                        if size > record['size']:
                            raise InvalidBackupError('Save backup entry exceeds its declared size.')
                if size != record['size'] or digest.hexdigest() != record['sha256']:
                    raise InvalidBackupError('Save backup checksum mismatch.')
        return manifest
    except (zipfile.BadZipFile, UnicodeError, ValueError, KeyError, TypeError, RecursionError, NotImplementedError) as error:
        raise InvalidBackupError('The save backup is incomplete, corrupt or unsupported.') from error


def _digest(stream):
    digest = hashlib.sha256(); size = 0
    stream.seek(0)
    while block := stream.read(CHUNK):
        digest.update(block); size += len(block)
    return digest.hexdigest(), size


def _tree_matches(root, manifest):
    directories, files = _scan(root)
    if directories != sorted(manifest['directories']) or {f[0] for f in files} != {r['path'] for r in manifest['files']}:
        return False
    for record in manifest['files']:
        with open_save_read(root / record['path']) as stream:
            digest, size = _digest(stream)
        if digest != record['sha256'] or size != record['size']:
            return False
    return True


class SaveManager:
    def __init__(self, user_dir):
        self.root = Path(user_dir).resolve()
        self.backups = self.root / 'save-backups'
        self.journal = self.root / JOURNAL_NAME
        self.root_id = hashlib.sha256(os.path.normcase(str(self.root)).encode('utf-8')).hexdigest()

    def _backup_locked(self, label, category, *, allow_empty=False):
        if not isinstance(label, str) or len(label) > 80 or any(ord(c) < 32 for c in label):
            raise SaveManagerError('Use a snapshot name of at most 80 characters.')
        directories, files = _scan(self.root)
        if not directories or not files and not allow_empty:
            return None
        self.backups.mkdir(parents=True, exist_ok=True); _plain(self.backups, directory=True)
        identity = os.urandom(12).hex()
        now = datetime.now(timezone.utc)
        filename = f'{now.strftime("%Y%m%d-%H%M%S")}-{category}-{identity}.zip'
        target = self.backups / filename
        descriptor, name = tempfile.mkstemp(prefix='.save-backup-', suffix='.partial', dir=self.backups)
        temporary = Path(name)
        manifest = {'schema_version': 1, 'kind': BACKUP_KIND, 'id': identity,
                    'created_utc': now.isoformat(timespec='microseconds'), 'root_id': self.root_id,
                    'category': category, 'label': label, 'directories': directories, 'files': []}
        try:
            # Retain every source read handle until publication. On Windows
            # these deny save writers and deletion, in addition to the runtime lease.
            with ExitStack() as stack:
                destination = stack.enter_context(os.fdopen(descriptor, 'w+b'))
                sources = {relative: stack.enter_context(open_save_read(self.root / relative))
                           for relative, *_rest in files}
                with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=3) as archive:
                    for relative, expected_size, modified, _inode, _device in files:
                        source = sources[relative]
                        digest, size = hashlib.sha256(), 0
                        with archive.open(relative, 'w', force_zip64=True) as output:
                            while block := source.read(CHUNK):
                                output.write(block); digest.update(block); size += len(block)
                        if size != expected_size:
                            raise SaveBusyError('A save changed during backup. Close the game/save editor and retry.')
                        manifest['files'].append({'path': relative, 'size': size, 'mtime_ns': modified,
                                                  'sha256': digest.hexdigest()})
                    archive.writestr('manifest.json', _json(manifest))
                destination.flush(); os.fsync(destination.fileno()); destination.close()
                if _scan(self.root) != (directories, files):
                    raise SaveBusyError('The saves tree changed during backup; no snapshot was published.')
                for record in manifest['files']:
                    digest, size = _digest(sources[record['path']])
                    if digest != record['sha256'] or size != record['size']:
                        raise SaveBusyError('A save changed during backup; no snapshot was published.')
                verify_backup(temporary)
                os.replace(temporary, target); _sync_directory(self.backups)
            return target
        finally:
            temporary.unlink(missing_ok=True)

    def snapshot(self, label='Manual snapshot'):
        with SaveAccess(self.root):
            self._recover_locked()
            result = self._backup_locked(label, 'manual')
            if result is None:
                raise SaveManagerError('No save files exist yet. Start and save the game before creating a snapshot.')
            return result

    def list_snapshots(self):
        if not self.backups.exists():
            return []
        _plain(self.backups, directory=True)
        records = []
        for path in sorted(self.backups.glob('*.zip'), reverse=True):
            try:
                manifest = verify_backup(path)
            except (OSError, SaveManagerError, RuntimeError) as error:
                records.append({'path': path, 'status': 'invalid', 'error': str(error)})
            else:
                records.append({'path': path, 'status': 'verified', 'manifest': manifest})
        return records

    def _retention_locked(self, keep, newest):
        if type(keep) is not int or not 1 <= keep <= 100:
            raise SaveManagerError('Keep between 1 and 100 automatic snapshots.')
        candidates = [r for r in self.list_snapshots() if r['status'] == 'verified'
                      and r['path'] != newest and r['manifest']['root_id'] == self.root_id
                      and r['manifest']['category'] == 'auto']
        candidates.sort(key=lambda r: (r['manifest']['created_utc'], r['manifest']['id']), reverse=True)
        for record in candidates[keep - 1:]:
            record['path'].unlink()
        _sync_directory(self.backups) if self.backups.exists() else None

    def prepare_launch(self, *, automatic=True, retention=10):
        if type(retention) is not int or not 1 <= retention <= 100:
            raise SaveManagerError('Keep between 1 and 100 automatic snapshots.')
        with SaveAccess(self.root):
            recovered = self._recover_locked()
            snapshot = self._backup_locked('Before launch', 'auto') if automatic else None
            if snapshot:
                self._retention_locked(retention, snapshot)
            return {'snapshot': snapshot, 'recovered': recovered}

    def _extract(self, backup, destination, manifest):
        destination.mkdir(parents=True, exist_ok=True)
        for relative in sorted(manifest['directories'], key=lambda s: (s.count('/'), s)):
            (destination / relative).mkdir(exist_ok=True)
        with zipfile.ZipFile(backup) as archive:
            for record in manifest['files']:
                path = destination / record['path']
                digest, size = hashlib.sha256(), 0
                with archive.open(record['path']) as source, path.open('xb') as target:
                    while block := source.read(CHUNK):
                        target.write(block); digest.update(block); size += len(block)
                        if size > record['size']:
                            raise InvalidBackupError('The archive changed during restoration.')
                    target.flush(); os.fsync(target.fileno())
                if size != record['size'] or digest.hexdigest() != record['sha256']:
                    raise InvalidBackupError('The archive changed during restoration.')
                os.utime(path, ns=(record['mtime_ns'], record['mtime_ns']))
        if not _tree_matches(destination, manifest):
            raise InvalidBackupError('Extracted save data did not verify.')
        _sync_directory(destination)

    def _journal_state(self):
        _plain(self.journal)
        if self.journal.stat().st_size > 8192:
            raise InvalidBackupError('Interrupted restore journal is too large; saves were left untouched.')
        try:
            data = json.loads(self.journal.read_text(encoding='utf-8'))
            if not isinstance(data, dict) or data.get('schema_version') != 1 or data.get('root_id') != self.root_id:
                raise ValueError()
            if not re.fullmatch(r'[a-f0-9]{24}', data.get('id', '')) or data.get('phase') not in ('prepared', 'committed'):
                raise ValueError()
            if type(data.get('original_exists')) is not bool:
                raise ValueError()
            rollback = data.get('rollback')
            if rollback is not None and not re.fullmatch(r'\d{8}-\d{6}-rollback-[a-f0-9]{24}\.zip', rollback):
                raise ValueError()
            return data
        except (UnicodeError, ValueError, TypeError, RecursionError) as error:
            raise InvalidBackupError('Interrupted restore journal is malformed; saves were left untouched.') from error

    def _finish(self, transaction, *, preserve=False):
        # Remove the journal only after the restored/recovered tree is durable.
        _sync_directory(self.root)
        self.journal.unlink(); _sync_directory(self.root)
        if not preserve:
            shutil.rmtree(transaction)

    def _recover_locked(self):
        if not self.journal.exists() and not self.journal.is_symlink():
            return None
        data = self._journal_state()
        transaction = self.root / ('.workshop-restore-' + data['id'])
        _plain(transaction, directory=True)
        current, previous = self.root / 'savedata', transaction / 'previous'
        target_manifest_path = transaction / 'target-manifest.json'
        _plain(target_manifest_path)
        if target_manifest_path.stat().st_size > MAX_MANIFEST:
            raise InvalidBackupError('Interrupted restore manifest exceeds the limit.')
        try:
            target_manifest = _validate_manifest(json.loads(target_manifest_path.read_text(encoding='utf-8')))
        except (UnicodeError, ValueError, TypeError, RecursionError) as error:
            raise InvalidBackupError('Interrupted restore manifest is corrupt; saves were left untouched.') from error
        if data['phase'] == 'committed' and current.exists() and _tree_matches(self.root, target_manifest):
            self._finish(transaction)
            return 'Completed cleanup of a verified restore.'
        rollback = self.backups / data['rollback'] if data['rollback'] else None
        original_manifest = verify_backup(rollback) if rollback else None
        if previous.exists():
            _plain(previous, directory=True)
            # The rollback ZIP remains independently available even if the old
            # directory has subsequently been damaged by an interrupted operation.
            if original_manifest is None:
                raise InvalidBackupError('Missing rollback identity; existing saves were left untouched.')
            # Check previous without moving it: its archive-relative paths start
            # at savedata, so compare directly with that prefix removed.
            valid_previous = self._previous_matches(previous, original_manifest)
            if not valid_previous:
                recovery = transaction / ('rollback-copy-' + os.urandom(4).hex())
                self._extract(rollback, recovery, original_manifest)
                previous = recovery / 'savedata'
            if current.exists():
                _plain(current, directory=True)
                os.replace(current, transaction / ('rejected-' + os.urandom(4).hex()))
            os.replace(previous, current)
            if not _tree_matches(self.root, original_manifest):
                raise InvalidBackupError('Rollback verification failed; the recovery files were preserved.')
            self._finish(transaction, preserve=True)
            return 'Recovered the previous saves; rollback and recovery files were retained.'
        if data['original_exists']:
            if original_manifest is None:
                raise InvalidBackupError('Missing rollback archive; existing saves were left untouched.')
            if current.exists() and _tree_matches(self.root, original_manifest):
                self._finish(transaction)
                return 'The original saves were already intact.'
            recovery = transaction / ('rollback-copy-' + os.urandom(4).hex())
            self._extract(rollback, recovery, original_manifest)
            if current.exists():
                _plain(current, directory=True)
                os.replace(current, transaction / ('rejected-' + os.urandom(4).hex()))
            os.replace(recovery / 'savedata', current)
            if not _tree_matches(self.root, original_manifest):
                raise InvalidBackupError('Rollback verification failed; recovery files were preserved.')
            self._finish(transaction, preserve=True)
            return 'Recovered the original saves from the verified rollback ZIP.'
        if current.exists():
            _plain(current, directory=True)
            os.replace(current, transaction / ('rejected-' + os.urandom(4).hex()))
        self._finish(transaction, preserve=True)
        return 'Recovered the original empty saves state; recovery files were retained.'

    @staticmethod
    def _previous_matches(previous, manifest):
        expected_files = {PurePosixPath(r['path']).relative_to('savedata').as_posix(): r for r in manifest['files']}
        expected_dirs = {PurePosixPath(d).relative_to('savedata').as_posix() for d in manifest['directories']}
        actual_files, actual_dirs = set(), {'.'}
        for parent, dirs, files in os.walk(previous, followlinks=False):
            parent = Path(parent)
            for name in dirs:
                path = parent / name; _plain(path, directory=True)
                actual_dirs.add(path.relative_to(previous).as_posix())
            for name in files:
                path = parent / name; _plain(path)
                relative = path.relative_to(previous).as_posix(); actual_files.add(relative)
                if relative not in expected_files:
                    return False
                with open_save_read(path) as source:
                    digest, size = _digest(source)
                record = expected_files[relative]
                if digest != record['sha256'] or size != record['size']:
                    return False
        return actual_files == set(expected_files) and actual_dirs == expected_dirs

    def recover(self):
        with SaveAccess(self.root):
            return self._recover_locked()

    def restore(self, backup, *, allow_other_folder=False):
        with SaveAccess(self.root):
            self._recover_locked()
            manifest = verify_backup(backup)
            if manifest['root_id'] != self.root_id and not allow_other_folder:
                raise SaveManagerError('This backup comes from another saves folder. Confirm the import explicitly.')
            identity = os.urandom(12).hex()
            transaction = self.root / ('.workshop-restore-' + identity)
            transaction.mkdir()
            original_exists = (self.root / 'savedata').exists()
            rollback = None
            try:
                self._extract(backup, transaction / 'new', manifest)
                rollback = self._backup_locked(('Before restoring ' + manifest['label'])[:80], 'rollback', allow_empty=True)
                (transaction / 'target-manifest.json').write_bytes(_json(manifest))
                with (transaction / 'target-manifest.json').open('rb') as stream:
                    os.fsync(stream.fileno())
                journal = {'schema_version': 1, 'id': identity, 'root_id': self.root_id,
                           'phase': 'prepared', 'original_exists': original_exists,
                           'rollback': rollback.name if rollback else None}
                _atomic_json(self.journal, journal)
                if original_exists:
                    os.replace(self.root / 'savedata', transaction / 'previous')
                os.replace(transaction / 'new/savedata', self.root / 'savedata')
                _sync_directory(self.root)
                if not _tree_matches(self.root, manifest):
                    raise InvalidBackupError('Installed save data did not verify.')
                journal['phase'] = 'committed'; _atomic_json(self.journal, journal)
            except BaseException:
                if self.journal.exists():
                    self._recover_locked()
                elif transaction.exists():
                    shutil.rmtree(transaction)
                raise
            else:
                self._finish(transaction)
                return {'rollback': rollback, 'snapshot': manifest}


def prepare_launch(user_dir, *, automatic=True, retention=10):
    return SaveManager(user_dir).prepare_launch(automatic=automatic, retention=retention)
