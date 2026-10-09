# SPDX-License-Identifier: GPL-2.0-or-later
"""Keep the game's background pause outside the process being paused.

Windows suspends the whole native child, including its SDL event loop. The launcher
process can still observe focus and resume it. A small shared clock records paused
time so Bloodborne's timers do not jump when the game resumes.
"""
import ctypes
from ctypes import wintypes
from pathlib import Path
import os
import time

CHANNEL_MAGIC = 0x42424733
CHANNEL_SIZE = 32


class JobLimits(ctypes.Structure):
    # JOBOBJECT_EXTENDED_LIMIT_INFORMATION, Win32 sizes and native x64 alignment.
    _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64),
                ('flags', ctypes.c_uint32), ('minimum_working_set', ctypes.c_size_t),
                ('maximum_working_set', ctypes.c_size_t), ('active_process_limit', ctypes.c_uint32),
                ('affinity', ctypes.c_size_t), ('priority_class', ctypes.c_uint32),
                ('scheduling_class', ctypes.c_uint32), ('io_counters', ctypes.c_uint64 * 6),
                ('process_memory_limit', ctypes.c_size_t), ('job_memory_limit', ctypes.c_size_t),
                ('peak_process_memory', ctypes.c_size_t), ('peak_job_memory', ctypes.c_size_t)]


def menu_mode(config, read_text=None):
    try:
        path = Path(config).with_suffix('.menu.ini')
        text = read_text(path) if read_text else path.read_text(encoding='utf-8')
        for line in text.splitlines():
            key, sep, value = line.strip().partition('=')
            if sep and key == 'background_mode':
                return value if value in ('run', 'pause', '30', '60') else 'run'
    except (OSError, UnicodeError):
        pass
    return 'run'


class PauseController:
    """Transition policy, also exercised without Windows or a running game."""
    def __init__(self, suspend, resume, publish, clock=time.monotonic_ns):
        self.suspend, self.resume, self.publish, self.clock = suspend, resume, publish, clock
        self.started = None
        self.paused_ns = 0

    def update(self, focused, mode, window_exists=True):
        pause = window_exists and not focused and mode == 'pause'
        if pause and self.started is None:
            self.suspend()
            self.started = self.clock()
        elif not pause and self.started is not None:
            # Publish BEFORE resuming: every guest thread sees the adjusted clock.
            total = self.paused_ns + max(0, self.clock() - self.started)
            self.publish(total)
            self.resume()
            self.paused_ns = total
            self.started = None

    def close(self):
        self.update(True, 'run')


class BackgroundMonitor:
    def __init__(self, config, env):
        self.config = config
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.user = ctypes.WinDLL('user32', use_last_error=True)
        self.nt = ctypes.WinDLL('ntdll')
        self.mapping = self.view = self.child = self.controller = self.job = None
        self.window = None
        self.bindings()
        self.name = f'Local\\bbport-background-{os.getpid()}-{os.urandom(16).hex()}'
        self.mapping = self.kernel.CreateFileMappingW(wintypes.HANDLE(-1), None, 0x04, 0,
                                                      CHANNEL_SIZE, self.name)
        if not self.mapping:
            raise ctypes.WinError(ctypes.get_last_error())
        self.view = self.kernel.MapViewOfFile(self.mapping, 0x0002, 0, 0, CHANNEL_SIZE)
        if not self.view:
            self.kernel.CloseHandle(self.mapping)
            self.mapping = None
            raise ctypes.WinError(ctypes.get_last_error())
        ctypes.memset(self.view, 0, CHANNEL_SIZE)
        ctypes.c_uint32.from_address(self.view).value = CHANNEL_MAGIC
        env['BB_BACKGROUND_CHANNEL'] = self.name

    def bindings(self):
        signatures = (
            (self.kernel.CreateFileMappingW, wintypes.HANDLE,
             [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
              wintypes.DWORD, wintypes.LPCWSTR]),
            (self.kernel.MapViewOfFile, ctypes.c_void_p,
             [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_size_t]),
            (self.kernel.UnmapViewOfFile, wintypes.BOOL, [ctypes.c_void_p]),
            (self.kernel.CloseHandle, wintypes.BOOL, [wintypes.HANDLE]),
            (self.kernel.CreateFileW, wintypes.HANDLE,
             [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
              wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]),
            (self.kernel.ReadFile, wintypes.BOOL,
             [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
              ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]),
            (self.kernel.CreateJobObjectW, wintypes.HANDLE, [ctypes.c_void_p, wintypes.LPCWSTR]),
            (self.kernel.SetInformationJobObject, wintypes.BOOL,
             [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]),
            (self.kernel.AssignProcessToJobObject, wintypes.BOOL,
             [wintypes.HANDLE, wintypes.HANDLE]),
            (self.user.GetForegroundWindow, wintypes.HWND, []),
            (self.user.GetWindowThreadProcessId, wintypes.DWORD,
             [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]),
            (self.user.IsWindow, wintypes.BOOL, [wintypes.HWND]),
            (self.user.IsWindowVisible, wintypes.BOOL, [wintypes.HWND]),
            (self.user.GetClientRect, wintypes.BOOL, [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]),
            (self.nt.NtSuspendProcess, ctypes.c_long, [wintypes.HANDLE]),
            (self.nt.NtResumeProcess, ctypes.c_long, [wintypes.HANDLE]),
        )
        for function, result, arguments in signatures:
            function.restype, function.argtypes = result, arguments
        self.enum_callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        self.user.EnumWindows.restype = wintypes.BOOL
        self.user.EnumWindows.argtypes = [self.enum_callback, wintypes.LPARAM]

    def owned_window(self, hwnd):
        pid = wintypes.DWORD()
        self.user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value == self.child.pid

    def find_window(self):
        if self.window and self.user.IsWindow(self.window):
            return True
        self.window = None
        def visit(hwnd, _):
            rect = wintypes.RECT()
            if (self.owned_window(hwnd) and self.user.IsWindowVisible(hwnd)
                    and self.user.GetClientRect(hwnd, ctypes.byref(rect))
                    and rect.right > 16 and rect.bottom > 16):
                self.window = hwnd
                return False
            return True
        self.user.EnumWindows(self.enum_callback(visit), 0)
        return self.window is not None

    def process_operation(self, operation):
        status = operation(wintypes.HANDLE(int(self.child._handle)))
        if status < 0:
            raise OSError(f'Background pause failed (NTSTATUS 0x{status & 0xffffffff:08x})')

    def publish(self, ns):
        # Aligned 64-bit store, read atomically by the x64 native process.
        ctypes.c_uint64.from_address(self.view + 8).value = ns

    def read_settings(self, path):
        # FILE_SHARE_DELETE permits the game's atomic settings-file replacement.
        handle = self.kernel.CreateFileW(str(path), 0x80000000, 7, None, 3, 0x80, None)
        if handle == wintypes.HANDLE(-1).value:
            return ''
        try:
            buffer = ctypes.create_string_buffer(16384)
            count = wintypes.DWORD()
            if not self.kernel.ReadFile(handle, buffer, len(buffer), ctypes.byref(count), None):
                return ''
            return buffer.raw[:count.value].decode('utf-8')
        finally:
            self.kernel.CloseHandle(handle)

    def wait(self, child):
        self.child = child
        # An abruptly closed launcher must not leave a permanently suspended game.
        # Assign only our own child; a host job can decline nested assignment.
        job = self.kernel.CreateJobObjectW(None, None)
        if job:
            limits = JobLimits()
            limits.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if (self.kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits))
                    and self.kernel.AssignProcessToJobObject(job, wintypes.HANDLE(int(child._handle)))):
                self.job = job
            else:
                self.kernel.CloseHandle(job)
        self.controller = PauseController(
            lambda: self.process_operation(self.nt.NtSuspendProcess),
            lambda: self.process_operation(self.nt.NtResumeProcess), self.publish)
        try:
            while child.poll() is None:
                exists = self.find_window()
                focused = self.owned_window(self.user.GetForegroundWindow())
                self.controller.update(focused, menu_mode(self.config, self.read_settings), exists)
                # Keep focus detection independent of the child's frozen SDL event loop.
                time.sleep(0.05)
            return child.returncode
        finally:
            if child.poll() is None:
                self.controller.close()

    def close(self):
        try:
            if self.child and self.child.poll() is None and self.controller:
                self.controller.close()
        finally:
            if self.job:
                self.kernel.CloseHandle(self.job)
                self.job = None
            if self.view:
                self.kernel.UnmapViewOfFile(self.view)
                self.view = None
            if self.mapping:
                self.kernel.CloseHandle(self.mapping)
                self.mapping = None


def run_game(command, *, config, env, **kwargs):
    """Launch the same native EXE, with a live focus supervisor on Windows."""
    import subprocess
    monitor = BackgroundMonitor(config, env) if os.name == 'nt' else None
    try:
        child = subprocess.Popen(command, env=env, **kwargs)
        return monitor.wait(child) if monitor else child.wait()
    finally:
        if monitor:
            monitor.close()
