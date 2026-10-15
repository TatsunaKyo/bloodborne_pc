"""Select NVIDIA FG models through the real Tk popup and check persistence/layout."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import types

source = Path(__file__).resolve().parents[1] / 'launcher/bbport_launcher_win.py'
if len(sys.argv) > 1:
    import marshal
    from PyInstaller.archive.readers import CArchiveReader
    launcher = types.ModuleType('launcher_fg_presets')
    launcher.__file__ = str(source)
    exec(marshal.loads(CArchiveReader(sys.argv[1]).extract('bbport_launcher_win')), launcher.__dict__)
else:
    spec = importlib.util.spec_from_file_location('launcher_fg_presets', source)
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
launcher.Launcher.detect_gpu = lambda self: None
launcher.Launcher.check_update = lambda self: None
checks = 0
with tempfile.TemporaryDirectory(prefix='bbport-fg-preset-ui-') as directory:
    data = Path(directory)
    launcher.DATA_DIR = data
    launcher.CONFIG_DIR = data / 'launcher'
    launcher.CONFIG_FILE = launcher.CONFIG_DIR / 'settings.json'
    os.environ['BB_CONFIG'] = str(data / 'custom.ini')
    for language in ('en', 'ru'):
        launcher.LANG = language
        for scale in (1.0, 1.5, 2.0):
            launcher.menu_path().write_text('frame_generation=off\nnvidia_fg_preset=default\n')
            root = tk.Tk()
            root.tk.call('tk', 'scaling', scale * 96 / 72)
            obj = launcher.Launcher(root, tk, ttk, filedialog, messagebox)
            root.geometry(f'{round(1120*scale)}x{round(740*scale)}+0+0')
            obj.show('frames')
            box = obj.nvidia_fg_preset_row
            try:
                for provider in ('off', 'fsr', 'nvidia', 'off', 'nvidia'):
                    obj.vars['frame_generation'].set(provider)
                    root.update()
                    assert bool(box.winfo_ismapped()) == (provider == 'nvidia')
                    assert bool(box.row_label.winfo_ismapped()) == (provider == 'nvidia')
                    assert bool(box.row_hint.winfo_ismapped()) == (provider == 'nvidia')
                # Bring the real control into the page's viewport before posting its popup.
                page = obj.pages['frames']
                page.viewport.yview_moveto(0)
                root.update()
                y = box.winfo_rooty() - page.settings_body.winfo_rooty()
                page.viewport.yview_moveto(max(0, (y - 80*scale) / page.settings_body.winfo_height()))
                root.update()
                assert box.winfo_rootx() >= page.viewport.winfo_rootx()
                assert box.winfo_rootx()+box.winfo_width() <= page.viewport.winfo_rootx()+page.viewport.winfo_width()
                for index, (key, labels) in enumerate(launcher.NVIDIA_FG_PRESETS):
                    box.event_generate('<ButtonPress-1>', x=box.winfo_width()-8, y=box.winfo_height()//2)
                    box.event_generate('<ButtonRelease-1>', x=box.winfo_width()-8, y=box.winfo_height()//2)
                    root.update()
                    popup = str(root.tk.call('ttk::combobox::PopdownWindow', str(box))) + '.f.l'
                    assert int(root.tk.call('winfo', 'ismapped', popup)) == 1
                    assert tuple(root.tk.call(popup, 'get', 0, 'end')) == tuple(launcher._(*text) for _, text in launcher.NVIDIA_FG_PRESETS)
                    root.tk.call(popup, 'selection', 'clear', 0, 'end')
                    root.tk.call(popup, 'selection', 'set', index)
                    root.tk.call(popup, 'activate', index)
                    root.tk.call('event', 'generate', popup, '<Return>')
                    root.update()
                    assert obj.vars['nvidia_fg_preset'].get() == key
                    obj.collect()
                    assert launcher.load_menu()['nvidia_fg_preset'] == key
                    checks += 1
                pending=[obj.pages['frames']];mod_toggles=[]
                while pending:
                    widget=pending.pop();pending.extend(widget.winfo_children())
                    if isinstance(widget,ttk.Checkbutton) and str(widget.cget('variable'))==str(obj.vars['nvidia_fg_mod']):
                        mod_toggles.append(widget)
                assert len(mod_toggles)==1
                for _ in range(2):
                    before=obj.vars['nvidia_fg_mod'].get();mod_toggles[0].invoke();root.update();obj.collect()
                    assert bool(obj.vars['nvidia_fg_mod'].get()) != bool(before)
                    assert launcher.load_menu()['nvidia_fg_mod']==('0' if before else '1')
                obj.show('overlay');root.update()
                pending=[obj.pages['overlay']];toggles=[]
                while pending:
                    widget=pending.pop();pending.extend(widget.winfo_children())
                    if isinstance(widget,ttk.Checkbutton) and str(widget.cget('variable'))==str(obj.vars['show_fg_preset']):
                        toggles.append(widget)
                assert len(toggles)==1
                for _ in range(2):
                    before=obj.vars['show_fg_preset'].get();toggles[0].invoke();root.update();obj.collect()
                    assert bool(obj.vars['show_fg_preset'].get()) != bool(before)
                    assert launcher.load_menu()['show_fg_preset']==('0' if before else '1')
                    assert launcher.load_menu()['nvidia_fg_preset']==key
                # No hidden-row reuse: following controls occupy distinct grid rows.
                parent = box.master
                rows = [int(w.grid_info()['row']) for w in parent.winfo_children()
                        if w.winfo_manager() == 'grid' and int(w.grid_info().get('column', -1)) == 1]
                assert len(rows) == len(set(rows)), rows
            finally:
                obj.closing = True
                root.destroy()
print(f'PASS: {checks} actual NVIDIA FG preset popup selections, both languages, 100/150/200%, conditional rows and persisted choices; 12 independent FG model OSD toggle/save operations.')
