"""Open and select the actual XeSS popup on both pages; never starts the game."""
import importlib.util
import json
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
    launcher = types.ModuleType('launcher_xess')
    launcher.__file__ = str(source)
    exec(marshal.loads(CArchiveReader(sys.argv[1]).extract('bbport_launcher_win')), launcher.__dict__)
else:
    spec = importlib.util.spec_from_file_location('launcher_xess', source)
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
launcher.Launcher.detect_gpu = lambda self: None
launcher.Launcher.check_update = lambda self: None
results = []

with tempfile.TemporaryDirectory(prefix='bbport-xess-popup-') as directory:
    data = Path(directory)
    launcher.DATA_DIR = data
    launcher.CONFIG_DIR = data / 'launcher'
    launcher.CONFIG_FILE = launcher.CONFIG_DIR / 'settings.json'
    config = data / 'bbport.ini'
    os.environ['BB_CONFIG'] = str(config)
    for legacy, expected in enumerate(launcher.LEGACY_XESS_PRESETS):
        config.write_text(f'upscaler=xess\npreset={legacy}\n')
        launcher.menu_path().write_text('xess_preset=invalid\n')
        assert launcher.load_menu()['xess_preset'] == expected
    config.write_text('upscaler=xess\npreset=1\nxess_preset=1\n')
    assert launcher.load_menu()['xess_preset'] == '1'
    for invalid in ('-1', '7', '1.5', 'invalid', ''):
        launcher.menu_path().write_text(f'xess_preset={invalid}\n')
        assert launcher.load_menu()['xess_preset'] == '1'
    for language in ('en', 'ru'):
        launcher.LANG = language
        for scale in (1.0, 1.5, 2.0):
            config.write_text('upscaler=dlss\npreset=1\n')
            launcher.menu_path().write_text('xess_preset=2\ndlss_preset=l\n')
            root = tk.Tk()
            root.tk.call('tk', 'scaling', scale * 96 / 72)
            obj = launcher.Launcher(root, tk, ttk, filedialog, messagebox)
            root.geometry(f'{round(1120*scale)}x{round(740*scale)}+0+0')
            try:
                for page, box, generic in (('play', obj.quick_xess_row, obj.quick_preset_row),
                                            ('image', obj.graphics_xess_row, obj.graphics_preset_row)):
                    obj.show(page)
                    if page == 'image':
                        obj.pages[page].scroll_to_top()
                    for provider in ('dlss', 'fsr3', 'taa', 'off', 'fsr4', 'xess'):
                        obj.vars['upscaler'].set(provider)
                        root.update()
                        assert bool(box.winfo_ismapped()) == (provider == 'xess')
                        assert bool(box.row_label.winfo_ismapped()) == (provider == 'xess')
                        assert bool(generic.winfo_ismapped()) == (provider != 'xess')
                        if hasattr(box, 'row_hint'):
                            assert bool(box.row_hint.winfo_ismapped()) == (provider == 'xess')
                            assert bool(generic.row_hint.winfo_ismapped()) == (provider != 'xess')
                    for index, (key, labels) in enumerate(launcher.XESS_PRESETS):
                        # Post through the real arrow click, then select through Tk's listbox binding.
                        box.event_generate('<ButtonPress-1>', x=box.winfo_width()-8, y=box.winfo_height()//2)
                        box.event_generate('<ButtonRelease-1>', x=box.winfo_width()-8, y=box.winfo_height()//2)
                        root.update()
                        popup = root.tk.call('ttk::combobox::PopdownWindow', str(box))
                        listbox = str(popup) + '.f.l'
                        assert int(root.tk.call('winfo', 'ismapped', listbox)) == 1
                        actual = root.tk.call(listbox, 'get', 0, 'end')
                        assert tuple(actual) == tuple(launcher._(*text) for _value, text in launcher.XESS_PRESETS)
                        if language == 'en' and scale == 1.0 and page == 'play' and index == 0:
                            from PIL import ImageGrab
                            ImageGrab.grab(bbox=(0, 0, root.winfo_width(), root.winfo_height()),
                                           xdisplay=os.environ['DISPLAY']).save(source.parents[1] / 'out/verification/launcher-xess-popup-revision15.png')
                        root.tk.call(listbox, 'selection', 'clear', 0, 'end')
                        root.tk.call(listbox, 'selection', 'set', index)
                        root.tk.call(listbox, 'activate', index)
                        root.tk.call(listbox, 'see', index)
                        root.tk.call('event', 'generate', listbox, '<Return>')
                        root.update()
                        assert obj.vars['xess_preset'].get() == key and box.get() == launcher._(*labels)
                        obj.collect()
                        assert launcher.load_menu()['xess_preset'] == key
                        assert obj.vars['preset'].get() == '1' and obj.vars['dlss_preset'].get() == 'l'
                        obj.vars['upscaler'].set('dlss')
                        root.update()
                        assert not box.winfo_ismapped()
                        assert obj.vars['xess_preset'].get() == key and obj.vars['preset'].get() == '1'
                        obj.vars['upscaler'].set('xess')
                        root.update()
                        assert box.winfo_ismapped() and box.get() == launcher._(*labels)
                        results.append({'page': page, 'language': language, 'scale': scale, 'selected': key,
                                        'label': box.get(), 'popup_values': list(actual)})
                # An in-game edit wins when the launcher has not edited the same preference.
                obj.collect()
                launcher.save_menu({'xess_preset': '1', 'background_mode': '30'})
                obj.collect()
                assert obj.vars['xess_preset'].get() == '1'
                assert launcher.load_menu()['xess_preset'] == '1'
                assert launcher.load_menu()['background_mode'] == '30'
                # A deliberate launcher edit changes its quality, preserving other in-game edits.
                obj.vars['xess_preset'].set('5')
                launcher.save_menu({'xess_preset': '6', 'background_mode': '60'})
                obj.collect()
                assert launcher.load_menu()['xess_preset'] == '5'
                assert launcher.load_menu()['background_mode'] == '60'
            finally:
                for callback in root.tk.call('after', 'info'):
                    root.after_cancel(callback)
                root.destroy()

output = source.parents[1] / 'out/verification/launcher-xess-revision15.json'
output.write_text(json.dumps({'cases': results, 'checks': 'actual popup input, all seven entries, both pages, conditional rows/hints, independent saved quality, concurrent game changes'}, indent=2)+'\n')
print(f'PASS: {len(results)} real XeSS popup selections on Play/Image in English/Russian at 100/150/200%; migration, visibility and independent saved preferences pass.')
