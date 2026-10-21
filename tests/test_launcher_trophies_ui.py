# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Render the real Achievements page and filters without game files or network IO."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import types

source = Path(__file__).resolve().parents[1]/'launcher/bbport_launcher_win.py'
if len(sys.argv) > 1:
    import marshal
    from PyInstaller.archive.readers import CArchiveReader
    launcher = types.ModuleType('launcher_trophies')
    launcher.__file__ = str(source)
    exec(marshal.loads(CArchiveReader(sys.argv[1]).extract('bbport_launcher_win')), launcher.__dict__)
else:
    spec = importlib.util.spec_from_file_location('launcher_trophies', source)
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
launcher.Launcher.detect_gpu = lambda self: None
launcher.Launcher.check_update = lambda self: None


def labels(widget):
    found = []
    if widget.winfo_class() in ('Label', 'TLabel'):
        found.append(str(widget.cget('text')))
    for child in widget.winfo_children():
        found.extend(labels(child))
    return found


checks = 0
with tempfile.TemporaryDirectory(prefix='workshop-trophies-ui-') as directory:
    launcher.DATA_DIR = Path(directory)
    launcher.CONFIG_DIR = Path(directory)/'config'
    launcher.CONFIG_FILE = launcher.CONFIG_DIR/'settings.json'
    os.environ['BB_CONFIG'] = str(Path(directory)/'bbport.ini')
    for language in ('en', 'ru'):
        launcher.LANG = language
        for scale in (1.0, 1.5, 2.0):
            root = tk.Tk()
            try:
                root.tk.call('tk', 'scaling', scale*96/72)
                app = launcher.Launcher(root, tk, ttk, filedialog, messagebox)
                root.geometry(f'{round(980*scale)}x{round(660*scale)}')
                app.show('trophies')
                root.update()
                names = labels(app.trophy_body)
                assert all(trophy[1] in names for trophy in launcher.trophies.TROPHIES)
                assert all(launcher._(*launcher.GRADE_NAMES[grade]) in names
                           for grade in launcher.trophies.GRADES)
                app.tracker.unlocked = {14: 1_700_000_000, 35: 1_700_000_001}
                app.set_trophy_filter('earned')
                root.update()
                names = labels(app.trophy_body)
                assert launcher.trophies.BY_ID[14][1] in names
                assert launcher.trophies.BY_ID[35][1] in names
                assert launcher.trophies.BY_ID[21][1] not in names
                app.set_trophy_filter('locked')
                root.update()
                names = labels(app.trophy_body)
                assert launcher.trophies.BY_ID[14][1] not in names
                assert launcher.trophies.BY_ID[21][1] in names
                app.tracker.unlocked = {trophy[0]: 1_700_000_000
                                       for trophy in launcher.trophies.TROPHIES}
                app.render_trophies()
                root.update()
                assert launcher._('Every trophy is earned. Hail, good hunter.',
                    'Все трофеи получены. Славной охоты.') in labels(app.trophy_body)
                app.tracker.unlocked = {}
                app.set_trophy_filter('earned')
                root.update()
                assert launcher._('No trophies yet. They appear here as soon as the game unlocks them.',
                    'Трофеев пока нет. Они появятся здесь, как только игра их откроет.') in labels(app.trophy_body)
                checks += 1
            finally:
                for pending in root.tk.call('after', 'info'):
                    root.after_cancel(pending)
                root.destroy()
print(f'PASS: Achievements rendering, four grades, earned/locked filters and empty states: {checks} real Tk configurations.')
