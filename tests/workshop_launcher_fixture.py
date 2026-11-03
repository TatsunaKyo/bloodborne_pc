"""Disposable real-Tk fixture shared by Workshop launcher integration checks."""
from contextlib import contextmanager, ExitStack
import json
import os
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import ttk, filedialog
from unittest.mock import patch, Mock
from test_launcher_startup import load_launcher


@contextmanager
def launcher_window(executable=None, *, language="en", scale=1.0):
    module = load_launcher(executable)
    with tempfile.TemporaryDirectory(prefix='workshop-launcher-') as temporary, ExitStack() as stack:
        folder = Path(temporary)
        settings = {'setup_done': True, 'ui_mode': 'expert', 'check_updates': False,
                    'ui_language': language, 'user_dir': str(folder / 'user')}
        config = folder / 'bbport.ini'
        config.write_text('upscaler=dlss\npreset=3\noutput_res=3840x2160\nframe_cap=60\n')
        config.with_suffix('.menu.ini').write_text('xess_preset=5\ndlss_preset=l\nframe_generation=off\n')
        stack.enter_context(patch.dict(os.environ, {'BB_CONFIG': str(config)}))
        for name, value in {'DATA_DIR': folder, 'CONFIG_DIR': folder / 'config',
                            'CONFIG_FILE': folder / 'config/settings.json', 'LANG': language}.items():
            stack.enter_context(patch.object(module, name, value))
        (folder / 'config').mkdir()
        module.CONFIG_FILE.write_text(json.dumps(settings))
        for name in ('detect_gpu', 'check_update', 'maybe_open_setup', 'maybe_show_news',
                     'window_chrome', 'temporary_warning'):
            stack.enter_context(patch.object(module.Launcher, name, lambda *a, **kw: None, create=True))
        errors = []
        stack.enter_context(patch.object(module.Launcher, 'callback_error',
            lambda self, kind, value, trace: errors.append(value)))
        root = tk.Tk()
        root.tk.call('tk', 'scaling', scale * 96 / 72)
        try:
            app = module.Launcher(root, tk, ttk, filedialog, Mock())
            root.update()
            yield module, app, root, config
            assert not errors, errors
        finally:
            for timer in root.tk.call('after', 'info'):
                # Let the widget that registered the Python callback delete its Tcl command.
                root.tk.call('after', 'cancel', timer)
            root.destroy()


def reveal(root, page, widget):
    canvas = page.viewport
    canvas.yview_moveto(0)
    root.update_idletasks()
    canvas.yview_scroll(widget.winfo_rooty() - canvas.winfo_rooty() - 12, 'units')
    root.update()


def select_popup(root, box, labels, index):
    # Use the native Tcl combobox popdown and its selection event, not var.set().
    root.tk.call('ttk::combobox::Post', str(box))
    popdown = root.tk.call('ttk::combobox::PopdownWindow', str(box))
    popup = f'{popdown}.f.l'
    root.update()
    assert int(root.tk.call('winfo', 'ismapped', popup)) == 1
    assert tuple(root.tk.call(popup, 'get', 0, 'end')) == tuple(labels)
    root.tk.call(popup, 'selection', 'clear', 0, 'end')
    root.tk.call(popup, 'selection', 'set', index)
    root.tk.call('ttk::combobox::LBSelected', popup)
    root.update()
