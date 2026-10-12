# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""The launcher and native runtime share one OS lease for a saves directory."""
import ctypes
from contextlib import contextmanager
import os
from pathlib import Path
import stat

LOCK_NAME = '.crowned-workshop-save.lock'
JOURNAL_NAME = '.crowned-workshop-restore.json'


class SaveBusyError(RuntimeError):
    pass


def _kernel():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
                                   ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
    kernel.CreateFileW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel.LockFileEx.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32,
                                  ctypes.c_uint32, ctypes.c_void_p]
    kernel.UnlockFileEx.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                                    ctypes.c_uint32, ctypes.c_void_p]
    kernel.GetFileAttributesW.argtypes = [ctypes.c_wchar_p]
    kernel.GetFileAttributesW.restype = ctypes.c_uint32
    return kernel


class _Overlapped(ctypes.Structure):
    _fields_ = [('Internal', ctypes.c_size_t), ('InternalHigh', ctypes.c_size_t),
                ('Offset', ctypes.c_uint32), ('OffsetHigh', ctypes.c_uint32), ('hEvent', ctypes.c_void_p)]


def native_game_running():
    """Also reject older runtimes that do not yet use the saves-directory lease."""
    if os.name != 'nt':
        return False
    kernel = _kernel()

    class Entry(ctypes.Structure):
        _fields_ = [('dwSize', ctypes.c_uint32), ('cntUsage', ctypes.c_uint32),
                    ('th32ProcessID', ctypes.c_uint32), ('th32DefaultHeapID', ctypes.c_size_t),
                    ('th32ModuleID', ctypes.c_uint32), ('cntThreads', ctypes.c_uint32),
                    ('th32ParentProcessID', ctypes.c_uint32), ('pcPriClassBase', ctypes.c_int32),
                    ('dwFlags', ctypes.c_uint32), ('szExeFile', ctypes.c_wchar * 260)]
    kernel.CreateToolhelp32Snapshot.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    kernel.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    kernel.Process32FirstW.argtypes = [ctypes.c_void_p, ctypes.POINTER(Entry)]
    kernel.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.POINTER(Entry)]
    handle = kernel.CreateToolhelp32Snapshot(2, 0)
    if handle == ctypes.c_void_p(-1).value:
        raise SaveBusyError('Could not check running game processes. Close the game and retry.')
    try:
        entry = Entry(); entry.dwSize = ctypes.sizeof(entry)
        valid = kernel.Process32FirstW(handle, ctypes.byref(entry))
        if not valid and ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES
            raise SaveBusyError('Could not check running game processes. Close the game and retry.')
        while valid:
            if entry.szExeFile.casefold() in ('bb-probe.exe', 'bb-probe'):
                return True
            valid = kernel.Process32NextW(handle, ctypes.byref(entry))
        return False
    finally:
        kernel.CloseHandle(handle)


class SaveAccess:
    def __init__(self, user_dir, *, check_game=True):
        self.root = Path(user_dir).resolve()
        self.check_game, self.handle, self.fd = check_game, None, None

    def __enter__(self):
        if self.check_game and native_game_running():
            raise SaveBusyError('Close all Bloodborne game windows before managing saves.')
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / LOCK_NAME
        if os.name == 'nt':
            self.kernel = _kernel()
            attributes = self.kernel.GetFileAttributesW(str(path))
            if attributes != 0xffffffff and attributes & 0x400:
                raise SaveBusyError('The saves lock must not be a link or junction.')
            # Share read/write but not deletion: another process must open the
            # same file, rather than unlinking a held lease and creating a new one.
            self.handle = self.kernel.CreateFileW(str(path), 0xc0000000, 3, None, 4, 0x80, None)
            if self.handle == ctypes.c_void_p(-1).value:
                self.handle = None
                raise SaveBusyError('Cannot open the saves lock; check the folder permissions.')
            self.overlapped = _Overlapped()
            if not self.kernel.LockFileEx(self.handle, 3, 0, 1, 0, ctypes.byref(self.overlapped)):
                self.kernel.CloseHandle(self.handle); self.handle = None
                raise SaveBusyError('The game or another save operation is using this folder.')
        else:
            import fcntl
            self.fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
            try:
                if not stat.S_ISREG(os.fstat(self.fd).st_mode):
                    raise SaveBusyError('The saves lock must be a regular file.')
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (OSError, SaveBusyError) as error:
                os.close(self.fd); self.fd = None
                raise SaveBusyError('The game or another save operation is using this folder.') from error
        return self

    def __exit__(self, *_args):
        if self.handle is not None:
            self.kernel.UnlockFileEx(self.handle, 0, 1, 0, ctypes.byref(self.overlapped))
            self.kernel.CloseHandle(self.handle); self.handle = None
        if self.fd is not None:
            os.close(self.fd); self.fd = None


@contextmanager
def open_save_read(path):
    """On Windows, retain a read handle that denies writers and deletion."""
    path = Path(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
        raise SaveBusyError('Save files must be regular files, without links or junctions.')
    if os.name == 'nt':
        import msvcrt
        kernel = _kernel()
        handle = kernel.CreateFileW(str(path), 0x80000000, 1, None, 3, 0x80, None)
        if handle == ctypes.c_void_p(-1).value:
            raise SaveBusyError('A save file is open for writing or cannot be read. Close the game and retry.')
        try:
            fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        except BaseException:
            kernel.CloseHandle(handle)
            raise
    else:
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        import fcntl
        try:
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except OSError as error:
            os.close(fd)
            raise SaveBusyError('A save file is being written; close the game/save editor and retry.') from error
    with os.fdopen(fd, 'rb') as stream:
        yield stream
