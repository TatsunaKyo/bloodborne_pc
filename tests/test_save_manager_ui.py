# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Actual Tk save controls, selected-folder scope, named snapshot and rollback restoration."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import tkinter as tk
from tkinter import ttk
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / 'launcher/bbport_launcher_win.py'
spec = importlib.util.spec_from_file_location('save_ui_launcher', source)
launcher = importlib.util.module_from_spec(spec); spec.loader.exec_module(launcher)
launcher.Launcher.detect_gpu = lambda self: None
launcher.Launcher.check_update = lambda self: None
records = []


def wait(root, predicate):
    until = time.monotonic() + 8
    while not predicate():
        root.update()
        if time.monotonic() > until:raise AssertionError('Save operation did not finish.')
        time.sleep(.01)
    root.update()


with tempfile.TemporaryDirectory(prefix='workshop-save-ui-') as directory:
    base = Path(directory)
    launcher.DATA_DIR, launcher.CONFIG_DIR = base, base / 'config'
    launcher.CONFIG_FILE = launcher.CONFIG_DIR / 'settings.json'
    os.environ['BB_CONFIG'] = str(base / 'bbport.ini')
    for scale in (1, 1.5, 2):
        for width, height in ((640, 500), (900, 650)):
            root = tk.Tk(); root.tk.call('tk', 'scaling', scale * 96 / 72)
            user = base / f'custom folder {scale}-{width}'
            data = user / 'savedata/0/CUSA03173/SPRJ0005/userdata0010'
            data.parent.mkdir(parents=True); data.write_bytes(b'earlier progress')
            errors = Mock(); errors.askyesno.return_value = True
            picker = Mock()
            app = launcher.Launcher(root, tk, ttk, picker, errors)
            app.var('user_dir', 'app').set(str(user))
            try:
                dialog = app.open_save_manager()
                dialog.window.geometry(f'{int(width * scale)}x{int(height * scale)}+0+0')
                wait(root, lambda: not dialog.busy)
                assert dialog.manager.root == user.resolve()
                assert str(user) in dialog.source_label.cget('text')
                assert app.var('save_auto_backup', 'app').get() is True
                dialog.tabs.select(1); root.update()
                app.var('save_backup_retention', 'app').set('500'); dialog.validate_retention()
                assert app.var('save_backup_retention', 'app').get() == '100'
                dialog.auto_control.invoke(); assert app.var('save_auto_backup', 'app').get() is False
                dialog.auto_control.invoke(); assert app.var('save_auto_backup', 'app').get() is True
                dialog.tabs.select(0); root.update()
                dialog.name.set('Before the boss'); dialog.snapshot_button.invoke()
                assert app.save_busy and app.play_button.instate(['disabled'])
                wait(root, lambda: not dialog.busy and bool(dialog.records))
                manual = next((key, item) for key, item in dialog.records.items() if item['manifest']['category'] == 'manual')
                assert manual[1]['manifest']['label'] == 'Before the boss'
                assert data.read_bytes() == b'earlier progress'
                data.write_bytes(b'current progress')
                dialog.files.selection_set(manual[0]); dialog.selection_changed()
                dialog.restore_button.invoke(); wait(root, lambda: not dialog.busy)
                assert data.read_bytes() == b'earlier progress'
                assert any(item['manifest']['category'] == 'rollback' for item in dialog.records.values())
                # The dialog's destination remains fixed if the main selector changes.
                app.var('user_dir', 'app').set(str(base / 'different selected folder'))
                assert dialog.manager.root == user.resolve()
                app.process = object(); dialog.selection_changed()
                assert dialog.restore_button.instate(['disabled'])
                app.process = None
                errors.showerror.assert_not_called()
                root.update()
                bounds = (dialog.window.winfo_rootx(), dialog.window.winfo_rooty(),
                          dialog.window.winfo_width(), dialog.window.winfo_height())
                for widget in (dialog.description, dialog.source_label, dialog.files,
                               dialog.details_label, dialog.snapshot_button, dialog.restore_button,
                               dialog.import_button, dialog.close_button, dialog.status_label):
                    assert widget.winfo_ismapped()
                    x, y = widget.winfo_rootx(), widget.winfo_rooty()
                    assert x >= bounds[0] and y >= bounds[1]
                    assert x + widget.winfo_width() <= bounds[0] + bounds[2], (scale, width, widget)
                    assert y + widget.winfo_height() <= bounds[1] + bounds[3], (scale, height, widget)
                assert dialog.files.winfo_height() >= round(65 * scale), (scale, width, dialog.files.winfo_height())
                records.append({'scale': scale, 'width': width, 'height': height,
                                'snapshot_restore_rollback_and_folder_scope': 'passed'})
            finally:
                for callback in root.tk.call('after', 'info'):root.after_cancel(callback)
                root.destroy()
output = ROOT / 'out/verification/save-manager-ui.json'
output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(records, indent=2) + '\n')
print(f'PASS: {len(records)} actual Tk save layouts, selected folder, settings, named snapshot, verified restore/rollback and game/busy control states.')
