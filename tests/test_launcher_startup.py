# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Exercise main(), then cold-start the frozen process on Windows; never launch a game."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import tkinter as tk
import types
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_launcher(executable=None):
    source = ROOT / 'launcher/bbport_launcher_win.py'
    if executable:
        import marshal
        from PyInstaller.archive.readers import CArchiveReader
        module = types.ModuleType('launcher_startup')
        module.__file__ = str(source)
        exec(marshal.loads(CArchiveReader(str(executable)).extract('bbport_launcher_win')), module.__dict__)
        return module
    spec = importlib.util.spec_from_file_location('launcher_startup', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def exercise_main(module, folder, expect_error=False):
    profile = folder / 'profile'; profile.mkdir()
    config = profile / 'settings.json'
    missing_game = folder / 'no game files'
    data = folder / 'port data'; data.mkdir()
    results = []
    real_tk = tk.Tk
    real_init = module.Launcher.__init__
    for language, arguments in (('en', []), ('ru', []), ('en', ['--play']), ('ru', ['--play'])):
        config.write_text(json.dumps({'ui_language': language, 'check_updates': False,
                                     'game_dir': str(missing_game), 'user_dir': str(data / 'user')}))
        apps, windows, failures = [], [], []

        def create_window(*args, **kwargs):
            window = real_tk(*args, **kwargs)
            windows.append(window)

            def inspect_and_close():
                try:
                    assert len(apps) == 1, 'The real Launcher constructor did not finish.'
                    app = apps[0]
                    assert window.winfo_ismapped()
                    assert window.title() == 'Bloodborne: The Crowned Workshop — TatsunaKyo'
                    assert app.current_page == 'play'
                    assert app.brand_version.cget('text') == 'v' + module.VERSION
                    assert app.quick_dlss_row.winfo_exists()
                    assert app.nav['frames'].winfo_exists()
                    assert app.brand_author.cget('text') == 'by TatsunaKyo'
                    assert app.process is None and not app.downloading
                    assert module.LANG == language
                    # Close through the normal handler, including settings persistence.
                    for timer in window.tk.call('after', 'info'):
                        window.after_cancel(timer)
                    app.close()
                    results.append({'language': language, 'arguments': arguments,
                                    'frozen_main': True, 'first_event_cycle': True,
                                    'normal_close': True})
                except BaseException as error:
                    failures.append(error)
                    if window.winfo_exists():
                        window.destroy()

            window.after(100, inspect_and_close)
            return window

        def construct(self, *args, **kwargs):
            real_init(self, *args, **kwargs)
            apps.append(self)

        with patch.object(module, 'FROZEN', True), patch.object(module, 'PORT_DIR', ROOT), \
             patch.object(module, 'DATA_DIR', data), patch.object(module, 'CONFIG_DIR', profile), \
             patch.object(module, 'CONFIG_FILE', config), \
             patch.object(module.Launcher, 'detect_gpu', lambda self: None), \
             patch.object(module.Launcher, 'check_update', lambda self: None), \
             patch.object(module.Launcher, '__init__', construct), \
             patch.object(module, 'play_without_window', side_effect=AssertionError('Test attempted to launch a game')), \
             patch.object(sys, 'argv', ['Bloodborne.exe', *arguments]), \
             patch.dict(os.environ, {'BB_CONFIG': str(data / 'bbport.ini')}), \
             patch.object(tk, 'Tk', create_window):
            try:
                module.main()
            except NameError as error:
                if expect_error and "'UPDATE_DIR'" in str(error):
                    assert not windows
                    print('PASS: original Revision 26 executable reproduces UPDATE_DIR crash before the first window.')
                    return []
                raise
            finally:
                for window in windows:
                    try:
                        for timer in window.tk.call('after', 'info'):
                            window.after_cancel(timer)
                        window.destroy()
                    except tk.TclError:
                        pass
        assert not expect_error, 'Broken control unexpectedly completed startup.'
        if failures:
            raise failures[0]
        assert len(results) >= 1 and json.loads(config.read_text())['ui_language'] == language
    assert len(results) == 4
    print('PASS: real main() from ' + ('compiled' if hasattr(module, '__spec__') and module.__spec__ is None else 'source') +
          ' launcher: four frozen normal/--play startups, English/Russian, first event cycle and normal close.')
    return results


def cold_start_windows(executable, folder):
    """Run the bootloader and its normal entry point, without --script or imported main()."""
    import ctypes
    from ctypes import wintypes
    port = folder / 'Crowned Workshop test'; port.mkdir()
    shutil.copy2(executable, port / 'Bloodborne.exe')
    shutil.copytree(executable.parent / '_internal', port / '_internal')
    for name in ('scripts', 'tools', 'launcher', 'docs/assets'):
        shutil.copytree(ROOT / name, port / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    results = []
    for language, arguments in (('en', []), ('ru', ['--play'])):
        profile = folder / ('cold-' + language); profile.mkdir()
        config = profile / 'bbport-launcher/settings.json'; config.parent.mkdir()
        config.write_text(json.dumps({'ui_language': language, 'check_updates': False,
                                     'game_dir': str(folder / 'no game files'),
                                     'user_dir': str(profile / 'user')}))
        environment = dict(os.environ, APPDATA=str(profile), BB_DATA_DIR=str(profile),
                           BB_CONFIG=str(profile / 'bbport.ini'))
        process = subprocess.Popen([str(port / 'Bloodborne.exe'), *arguments], cwd=port, env=environment)
        windows = []

        @callback_type
        def locate(handle, _parameter):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(handle, ctypes.byref(pid))
            if pid.value == process.pid and user32.IsWindowVisible(handle):
                title = ctypes.create_unicode_buffer(512)
                user32.GetWindowTextW(handle, title, len(title))
                if title.value == 'Bloodborne: The Crowned Workshop — TatsunaKyo':
                    windows.append(handle)
            return True

        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                assert process.poll() is None, 'Frozen launcher exited before opening its window.'
                windows.clear(); user32.EnumWindows(locate, 0)
                if windows:
                    break
                time.sleep(0.05)
            assert windows, 'Frozen normal startup did not open the expected launcher window.'
            time.sleep(0.5)
            assert process.poll() is None
            rectangle = wintypes.RECT()
            assert user32.GetWindowRect(windows[0], ctypes.byref(rectangle))
            assert rectangle.right - rectangle.left >= 980 and rectangle.bottom - rectangle.top >= 660
            assert user32.PostMessageW(windows[0], 0x0010, 0, 0), 'Could not close the launcher window.'
            assert process.wait(timeout=15) == 0, 'Frozen launcher failed on normal close.'
            results.append({'language': language, 'arguments': arguments,
                            'native_windows_process': True, 'normal_entry_point': True,
                            'window_opened': True, 'exit_code': 0})
        finally:
            if process.poll() is None:
                process.kill(); process.wait(timeout=10)
    print('PASS: two actual Windows EXE cold starts through the bootloader and normal main(), including --play fallback; window opened and closed with exit code 0.')
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('executable', nargs='?', type=Path)
    parser.add_argument('--expect-update-dir-error', action='store_true')
    args = parser.parse_args()
    executable = args.executable.resolve() if args.executable else None
    module = load_launcher(executable)
    with tempfile.TemporaryDirectory(prefix='workshop-launcher-startup-') as folder:
        root = Path(folder)
        imported = exercise_main(module, root, expect_error=args.expect_update_dir_error)
        cold = cold_start_windows(executable, root) if os.name == 'nt' and executable and not args.expect_update_dir_error else []
    if not args.expect_update_dir_error:
        output = ROOT / 'out/verification'; output.mkdir(parents=True, exist_ok=True)
        (output / ('launcher-startup-revision' + module.VERSION.rsplit('.', 1)[-1] + '.json')).write_text(
            json.dumps({'version': module.VERSION, 'compiled_entry': bool(executable),
                        'main_cases': imported, 'native_windows_cold_starts': cold}, indent=2) + '\n')


if __name__ == '__main__':
    main()
