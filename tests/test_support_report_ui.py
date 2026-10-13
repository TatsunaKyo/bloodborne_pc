# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Exercise actual report controls, privacy options, inspection and export in Tk."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import tkinter as tk
from tkinter import ttk
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / 'launcher/bbport_launcher_win.py'
if len(sys.argv) > 1:
    import marshal
    import types
    from PyInstaller.archive.readers import CArchiveReader
    launcher = types.ModuleType('support_ui_launcher'); launcher.__file__ = str(source)
    exec(marshal.loads(CArchiveReader(sys.argv[1]).extract('bbport_launcher_win')), launcher.__dict__)
else:
    spec = importlib.util.spec_from_file_location('support_ui_launcher', source)
    launcher = importlib.util.module_from_spec(spec); spec.loader.exec_module(launcher)
import support_report
launcher.Launcher.detect_gpu = lambda self: None
launcher.Launcher.check_update = lambda self: None
records = []


def wait(root, predicate):
    end = time.monotonic() + 8
    while not predicate():
        root.update()
        if time.monotonic() > end:
            raise AssertionError('Report collection did not finish.')
        time.sleep(.01)
    root.update()


with tempfile.TemporaryDirectory(prefix='workshop-support-ui-') as folder:
    base = Path(folder)
    launcher.DATA_DIR, launcher.CONFIG_DIR = base, base / 'config'
    launcher.CONFIG_FILE = launcher.CONFIG_DIR / 'settings.json'
    os.environ['BB_CONFIG'] = str(base / 'bbport.ini')
    user = base / 'custom saves'; user.mkdir()
    (user / 'last_run.log').write_text('GPU_Model: NVIDIA RTX 5070 Ti\n'
                                     'Password: KEEP THIS PRIVATE\n'
                                     '[5.0s] Frames: fps=75\n')
    hardware = {'os': {'name': 'Windows 11'}, 'gpus': [{'model': 'NVIDIA RTX 5070 Ti', 'driver_version': '581.23'}],
                'hardware_profile': {'cpu_model': ['AMD Ryzen 7 7800X3D'], 'ram_gib': 64}}
    for scale in (1, 1.5, 2):
        for width, height in ((640, 480), (900, 650)):
            root = tk.Tk(); root.tk.call('tk', 'scaling', scale * 96 / 72)
            errors = Mock(); destination = base / 'export.zip'
            dialog_files = Mock(); dialog_files.asksaveasfilename.return_value = str(destination)
            app = launcher.Launcher(root, tk, ttk, dialog_files, errors)
            app.var('user_dir', 'app').set(str(user))
            try:
                with patch.object(support_report, 'detect_system', return_value=hardware), \
                     patch('support_report_ui.webbrowser.open') as browser:
                    dialog = app.generate_support_report()
                    dialog.window.geometry(f'{int(width * scale)}x{int(height * scale)}+0+0')
                    wait(root, lambda: dialog.report is not None)
                    assert browser.call_count == 0, 'Collection must not contact GitHub.'
                    assert 'hardware-submission.json' not in dialog.files.get_children()
                    assert '7800X3D' not in dialog.report.summary
                    assert 'KEEP THIS PRIVATE' not in '\n'.join(d.decode() for d in dialog.report.entries.values())
                    dialog.files.selection_set('logs/last_run.log'); dialog.inspect()
                    assert 'Frames: fps=75' in dialog.preview.get('1.0', 'end')
                    dialog.profile_control.invoke()
                    assert dialog.report is None, 'Old candidate must be invalidated while rebuilding.'
                    wait(root, lambda: dialog.report is not None)
                    assert 'hardware-submission.json' in dialog.files.get_children()
                    data = json.loads(dialog.report.entries['hardware-submission.json'])
                    assert data['reviewed'] is False and data['status'] == 'unverified'
                    dialog.logs_control.invoke(); wait(root, lambda: dialog.report is not None)
                    assert not any(name.endswith('.log') for name in dialog.report.entries)
                    dialog.copy_button.invoke()
                    assert root.clipboard_get() == dialog.report.summary
                    dialog.export_button.invoke()
                    assert support_report.verify_report(destination)
                    errors.showerror.assert_not_called()
                    dialog.issue('bug-report.yml'); dialog.issue('performance-regression.yml')
                    assert browser.call_count == 2
                    root.update()
                    bounds = (dialog.window.winfo_rootx(), dialog.window.winfo_rooty(),
                              dialog.window.winfo_width(), dialog.window.winfo_height())
                    for widget in (dialog.description, dialog.logs_control, dialog.profile_control,
                                   dialog.status_label, dialog.export_button, dialog.copy_button):
                        assert widget.winfo_ismapped()
                        x, y = widget.winfo_rootx(), widget.winfo_rooty()
                        assert x >= bounds[0] and y >= bounds[1]
                        assert x + widget.winfo_width() <= bounds[0] + bounds[2], (scale, width, str(widget))
                        assert y + widget.winfo_height() <= bounds[1] + bounds[3], (scale, height, str(widget))
                    assert not launcher.CONFIG_FILE.exists(), 'Inspecting reports must not rewrite preferences.'
                    style = ttk.Style(root)
                    for states in (('!disabled', '!selected'), ('selected',)):
                        colors = [style.lookup(dialog.files.cget('style'), key, states)
                                  for key in ('background', 'foreground')]
                        def luminance(color):
                            channels = [v / 65535 for v in root.winfo_rgb(color)]
                            linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in channels]
                            return sum(a * b for a, b in zip(linear, (.2126, .7152, .0722)))
                        light, dark = sorted(map(luminance, colors), reverse=True)
                        assert (light + .05) / (dark + .05) >= 4.5, (states, colors)
                    records.append({'scale': scale, 'width': width, 'height': height,
                                    'inspect_export_and_privacy_options': 'passed'})
            finally:
                for callback in root.tk.call('after', 'info'):
                    root.after_cancel(callback)
                root.destroy()
output = ROOT / 'out/verification/support-report-ui.json'
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(records, indent=2) + '\n')
print(f'PASS: {len(records)} actual Tk report layouts, file inspection, opt-in profile, log exclusion, copy/export and manual issue links.')
