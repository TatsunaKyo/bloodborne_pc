"""Exercise the real Tk launcher layout; requires a display, never starts the game."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import tkinter as tk
from tkinter import font
from tkinter import ttk, filedialog, messagebox
import types

source = Path(__file__).resolve().parents[1] / 'launcher/bbport_launcher_win.py'
if len(sys.argv) > 1:
    import marshal
    from PyInstaller.archive.readers import CArchiveReader
    launcher = types.ModuleType('launcher_geometry')
    launcher.__file__ = str(source)
    exec(marshal.loads(CArchiveReader(sys.argv[1]).extract('bbport_launcher_win')), launcher.__dict__)
else:
    spec = importlib.util.spec_from_file_location('launcher_geometry', source)
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
launcher.Launcher.detect_gpu = lambda self: None
launcher.Launcher.check_update = lambda self: None
original_tk = tk.Tk
results = []
revision = launcher.VERSION.rsplit('.', 1)[-1]

def rectangle(widget):
    return (widget.winfo_rootx(), widget.winfo_rooty(), widget.winfo_width(), widget.winfo_height())

def overlaps(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]

with tempfile.TemporaryDirectory(prefix='bbport-geometry-') as directory:
    root_dir = Path(directory)
    launcher.DATA_DIR = root_dir
    launcher.CONFIG_DIR = root_dir / 'launcher'
    launcher.CONFIG_FILE = launcher.CONFIG_DIR / 'settings.json'
    os.environ['BB_CONFIG'] = str(root_dir / 'bbport.ini')
    for language in ('en', 'ru'):
        launcher.LANG = language
        for scale in (1.0, 1.25, 1.5, 1.75, 2.0):
            root = original_tk()
            root.tk.call('tk', 'scaling', scale * 96 / 72)
            text_font = font.Font(root, family='Segoe UI', size=10)
            assert not text_font.metrics('fixed') and text_font.metrics('linespace') >= round(12 * scale), 'Install a proportional scalable font before running geometry tests.'
            obj = launcher.Launcher(root, tk, ttk, filedialog, messagebox)
            obj.checks['game'].configure(text='✓ Game version 01.09: every patch available')
            obj.checks['saves'].configure(text='✓ Saves found in G:\\bbport-windows\\user')
            obj.gpu_text = '✓ Graphics card: NVIDIA GeForce RTX 5070 Ti, discrete, 15995 MiB'
            try:
                for size in ((980, 660), (1120, 740), (1280, 850)):
                    root.geometry(f'{round(size[0]*scale)}x{round(size[1]*scale)}+0+0')
                    for provider, fg in (('fsr4', 'off'), ('dlss', 'off'), ('dlss', 'nvidia'),
                                         ('xess', 'nvidia'), ('fsr3', 'fsr'), ('dlss', 'nvidia')):
                        obj.vars['upscaler'].set(provider)
                        obj.vars['frame_generation'].set(fg)
                        root.update()
                        # The longer project identity must fit at the minimum window
                        # size too, without pushing navigation or the menu hint out.
                        side_rect = rectangle(obj.side)
                        for label in (obj.brand_title, obj.brand_author, obj.brand_origin,
                                      obj.brand_version, obj.brand_mark, obj.side_note, *obj.nav.values()):
                            bounds = rectangle(label)
                            assert label.winfo_ismapped(), (language, scale, size, label.cget('text'))
                            assert bounds[0] >= side_rect[0] and bounds[0]+bounds[2] <= side_rect[0]+side_rect[2]
                            assert bounds[1] >= side_rect[1] and bounds[1]+bounds[3] <= side_rect[1]+side_rect[3], (language,scale,size,label.cget('text'),bounds,side_rect)
                        for label in (obj.brand_title, obj.brand_author, obj.brand_origin, obj.brand_version):
                            face = font.Font(root, font=label.cget('font'))
                            available = label.winfo_width()
                            for line in str(label.cget('text')).splitlines():
                                assert face.measure(line) <= available, (scale, size, line, face.measure(line), available)
                            assert label.winfo_height() >= face.metrics('linespace') * len(str(label.cget('text')).splitlines())
                        assert obj.brand_author.cget('text') == 'by TatsunaKyo'
                        assert obj.brand_title.cget('text').replace('\n',' ') == 'BLOODBORNE: THE CROWNED WORKSHOP'
                        # Check live hero typography at compact/high-DPI sizes, including
                        # vertical separation from the game-folder hint and actual artwork.
                        hero_rect = rectangle(obj.banner)
                        text_boxes = [obj.banner.bbox(item) for item in obj.banner.find_withtag('workshop-type')]
                        assert len(obj.banner.find_withtag('workshop-art')) == 1
                        for box in text_boxes:
                            assert box[0] >= 0 and box[1] >= 0 and box[2] <= hero_rect[2] and box[3] <= hero_rect[3], (language,scale,size,box,hero_rect)
                        for i, box in enumerate(text_boxes):
                            a = (box[0], box[1], box[2]-box[0], box[3]-box[1])
                            for other in text_boxes[i+1:]:
                                b = (other[0],other[1],other[2]-other[0],other[3]-other[1])
                                assert not overlaps(a,b), (language,scale,size,box,other)
                        quick = obj.quick_dlss_row.master
                        controls = [w for w in quick.winfo_children()
                                    if w.winfo_class() == 'TCombobox' and w.winfo_ismapped()]
                        rects = [rectangle(w) for w in controls]
                        page_rect = rectangle(obj.pages['play'])
                        quick_rect = rectangle(quick)
                        for label in obj.checks.values():
                            assert not overlaps(rectangle(label), quick_rect), (language, scale, size, label.cget('text'), rectangle(label), quick_rect, label.cget('wraplength'))
                        for widget in quick.winfo_children():
                            if widget.winfo_ismapped():
                                bounds=rectangle(widget)
                                assert bounds[0]+bounds[2] <= page_rect[0]+page_rect[2], (language,scale,size,widget.cget('text') if widget.winfo_class()!='TCombobox' else widget.get(),bounds,page_rect)
                                assert bounds[1]+bounds[3] <= page_rect[1]+page_rect[3], (language,scale,size,bounds,page_rect)
                        assert len(set(r[0] for r in rects)) == 1, (language, scale, size, provider, fg, rects)
                        for i, a in enumerate(rects):
                            for b in rects[i+1:]:
                                assert not overlaps(a, b), (language, scale, size, provider, fg, a, b)
                        for widget, visible in ((obj.quick_dlss_row, provider == 'dlss'),
                                                (obj.quick_xess_row, provider == 'xess'),
                                                (obj.quick_preset_row, provider != 'xess'),
                                                (obj.quick_fg_multiplier_row, fg == 'nvidia')):
                            assert bool(widget.winfo_ismapped()) == visible
                            assert bool(widget.row_label.winfo_ismapped()) == visible
                        checkbox_labels = [w.cget('text') for w in quick.winfo_children()
                                           if w.winfo_class() == 'TCheckbutton']
                        assert launcher._('Show performance overlay', 'Показывать статистику') in checkbox_labels
                        assert launcher._('Show DLSS preset in overlay', 'Показывать пресет DLSS в статистике') not in checkbox_labels
                        results.append({'language':language, 'scale':scale, 'window':size,
                                        'upscaler':provider, 'fg':fg, 'control_rectangles':rects,
                                        'font':text_font.actual(), 'font_metrics':text_font.metrics(),
                                        'root_rectangle':rectangle(root), 'link_rectangle':rectangle(obj.overlay_link)})
                    owners = {key: [category for category, _widget in locations]
                              for key, locations in obj.setting_locations.items()}
                    assert all(len(locations) == 1 for locations in owners.values()), owners
                    mapping_file = source.parents[1] / f'out/verification/menu{revision}/settings-categories.json'
                    assert mapping_file.is_file(), 'Run the ImGui category fixture before the compiled launcher geometry test.'
                    native = json.loads(mapping_file.read_text())
                    shared = set(owners).intersection(native)
                    assert len(shared) >= 35, (len(shared), owners, native)
                    assert all(owners[key][0] == native[key] for key in shared), {
                        key: (owners[key], native[key]) for key in shared if owners[key][0] != native[key]}
                    for category in ('image', 'frames', 'window', 'overlay', 'cheats', 'effects', 'advanced'):
                        obj.show(category); root.update()
                        view = rectangle(obj.pages[category].viewport)
                        for key, locations in obj.setting_locations.items():
                            for owner, widget in locations:
                                if owner == category and widget.winfo_ismapped():
                                    bounds = rectangle(widget)
                                    assert bounds[0] >= view[0] and bounds[0]+bounds[2] <= view[0]+view[2], (language, scale, size, category, key, bounds, view)
                    (source.parents[1] / f'out/verification/launcher-categories-revision{revision}.json').write_text(
                        json.dumps({'owners':owners, 'shared_count':len(shared), 'shared_native':{key:native[key] for key in sorted(shared)}}, indent=2)+'\n')
                    # Clicking the link returns to the overlay group even after scrolling.
                    root.focus_force()
                    obj.nav['image'].focus_set()
                    root.update()
                    assert root.focus_get() == obj.nav['image']
                    obj.nav['image'].event_generate('<Return>')
                    root.update()
                    assert obj.current_page == 'image'
                    obj.show('overlay')
                    obj.pages['overlay'].scroll(100)
                    obj.show('play')
                    root.update()
                    obj.overlay_link.event_generate('<Button-1>')
                    root.update()
                    assert obj.current_page == 'overlay'
                    # The new graph is a real shared checkbox on Overlay.
                    graph = obj.frametime_graph_check
                    assert graph.grid_info()['column'] == 0 and graph.grid_info()['columnspan'] == 2
                    assert graph.winfo_width() <= obj.pages['overlay'].winfo_width()
                    previous = obj.vars['show_frametime_graph'].get()
                    graph.invoke(); root.update()
                    assert obj.vars['show_frametime_graph'].get() != previous
                    graph.invoke(); root.update()
                    assert obj.vars['show_frametime_graph'].get() == previous
                    if language == 'en' and scale == 1.0 and size == (1280, 850):
                        from PIL import ImageGrab
                        for page in ('image','frames','window','overlay','cheats','effects','advanced'):
                            obj.show(page); obj.pages[page].scroll_to_top(); root.update()
                            bounds=rectangle(root)
                            ImageGrab.grab(bbox=(bounds[0],bounds[1],bounds[0]+bounds[2],bounds[1]+bounds[3]),
                                           xdisplay=os.environ['DISPLAY']).save(source.parents[1] / f'out/verification/launcher-{page}-revision{revision}.png')
                    obj.show('play')
                    root.update()
                    if language == 'en' and scale == 1.5 and size == (1280, 850):
                        from PIL import ImageGrab
                        bounds=rectangle(root)
                        ImageGrab.grab(bbox=(bounds[0],bounds[1],bounds[0]+bounds[2],bounds[1]+bounds[3]),
                                       xdisplay=os.environ['DISPLAY']).save(source.parents[1] / f'out/verification/launcher-play-revision{revision}.png')
            finally:
                for callback in root.tk.call('after', 'info'):
                    root.after_cancel(callback)
                root.destroy()
    tk.Tk = original_tk

output = source.parents[1] / f'out/verification/launcher-geometry-revision{revision}.json'
output.write_text(json.dumps({'cases':results, 'checks':'real Tk widgets: complete sidebar identity, visible navigation, aligned columns, distinct rows, conditional controls and overlay link'},indent=2)+'\n')
print(f'PASS: {len(results)} real Tk layouts in English/Russian at 100/125/150/175/200% scaling; readable sidebar identity, visible navigation, no overlapping dropdowns, matching columns, correct conditional labels and working overlay link.')
