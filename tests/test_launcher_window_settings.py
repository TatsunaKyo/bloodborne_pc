"""Launcher/overlay preferences and shared controls, without starting a game or display server."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import tkinter as tk
import types

source = Path(__file__).resolve().parents[1] / 'launcher/bbport_launcher_win.py'
if len(sys.argv) > 1:
    import marshal
    from PyInstaller.archive.readers import CArchiveReader
    launcher = types.ModuleType('bbport_launcher_window_test')
    launcher.__file__ = str(source)
    code = marshal.loads(CArchiveReader(sys.argv[1]).extract('bbport_launcher_win'))
    exec(code, launcher.__dict__)
else:
    spec = importlib.util.spec_from_file_location('bbport_launcher_window_test', source)
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)


class Widget:
    """Only the widget protocol used by the real builder; variable traces run in real Tcl."""
    nodes = []

    def __init__(self, parent=None, **kwargs):
        self.parent, self.kwargs, self.bindings, self.index, self.rows = parent, kwargs, {}, 0, 0
        self.nodes.append(self)

    def grid(self, **kwargs):
        if self.parent:
            self.parent.rows = max(self.parent.rows, kwargs.get('row', 0) + 1)

    def pack(self, **kwargs): pass
    def columnconfigure(self, *args, **kwargs): pass
    def grid_size(self): return (2, self.rows)
    def bind(self, event, callback): self.bindings[event] = callback
    def configure(self, **kwargs): self.kwargs.update(kwargs)
    def current(self, index=None):
        if index is not None: self.index = index
        return self.index
    def choose(self, index):
        self.index = index
        self.bindings['<<ComboboxSelected>>'](None)
    def invoke(self):
        variable = self.kwargs['variable']
        variable.set(not variable.get())


interpreter = tk.Tcl()
tk_api = types.SimpleNamespace(
    Frame=Widget, Canvas=Widget, TclError=tk.TclError,
    BooleanVar=lambda **kwargs: tk.BooleanVar(master=interpreter, **kwargs),
    StringVar=lambda **kwargs: tk.StringVar(master=interpreter, **kwargs),
    DoubleVar=lambda **kwargs: tk.DoubleVar(master=interpreter, **kwargs))
ttk_api = types.SimpleNamespace(Frame=Widget, Label=Widget, Combobox=Widget,
                                Checkbutton=Widget, Button=Widget, Scale=Widget, Progressbar=Widget)


def build(settings):
    obj = launcher.Launcher.__new__(launcher.Launcher)
    obj.tk, obj.ttk, obj.dpi = tk_api, ttk_api, 1
    obj.app = {**launcher.APP_DEFAULTS, **settings}
    obj.ini, obj.ini_lines = launcher.load_ini()
    obj.menu = launcher.menu_values(obj.app)
    obj.menu_baseline = dict(obj.menu)
    obj.vars, obj.pages, obj.content = {}, {}, Widget()
    obj.mod_order, obj.patch_vars = [], {}
    obj.scrolled_page = lambda *args: Widget()
    obj.version_warning = lambda *args: None
    obj.refresh_status = lambda *args: None
    obj.build_play()
    home_choice = next(w for w in Widget.nodes if 'values' in w.kwargs and
                       w.kwargs['values'][0] in ('Windowed', 'Оконный'))
    obj.build_graphics()
    obj.build_display()
    display_choice = [w for w in Widget.nodes if 'values' in w.kwargs and
                      w.kwargs['values'][0] in ('Windowed', 'Оконный')][-1]
    return obj, home_choice, display_choice


with tempfile.TemporaryDirectory(prefix='bbport-launcher-') as directory:
    root = Path(directory)
    launcher.DATA_DIR = root
    launcher.CONFIG_DIR = root / 'launcher'
    launcher.CONFIG_FILE = launcher.CONFIG_DIR / 'settings.json'
    config = root / 'custom settings.ini'
    previous = os.environ.get('BB_CONFIG')
    os.environ['BB_CONFIG'] = str(config)
    menu = launcher.menu_path()
    assert menu == root / 'custom settings.menu.ini'
    try:
        for fullscreen in (False, True):
            assert launcher.menu_values({'fullscreen': fullscreen})['window_mode'] == (
                'fullscreen' if fullscreen else 'windowed')
        menu.write_text('# keep this\nfuture_option=abc\nwindow_mode=launcher\nmenu_language=ru\n')
        assert launcher.menu_values({'window_mode': 'borderless'})['window_mode'] == 'borderless'
        launcher.save_menu({'borderless_vsync': '1'})
        assert '# keep this' in menu.read_text() and 'future_option=abc' in menu.read_text()
        assert launcher.load_menu()['menu_language'] == 'ru'
        menu.write_text('menu_language=invalid\nwindow_mode=invalid\nborderless_vsync=bad\n')
        assert launcher.load_menu() == launcher.MENU_DEFAULTS

        # Migrate the original FPS setting, then prefer the shared in-game setting.
        config.write_text('show_fps=0\n')
        menu.write_text('dlss_preset=default\n')
        assert launcher.load_menu()['show_fps'] == '0'
        menu.write_text('show_fps=1\n')
        assert launcher.load_menu()['show_fps'] == '1'
        config.write_text('show_fps=1\n')
        for value, expected in [('DEFAULT', 'default'), ('0', 'default'), ('E', 'e'), ('5', 'e'),
                                ('F', 'f'), ('6', 'f'), ('J', 'j'), ('10', 'j'), ('K', 'k'),
                                ('11', 'k'), ('L', 'l'), ('12', 'l'), ('M', 'm'), ('13', 'm'),
                                ('a', 'default'), ('9', 'default'), ('14', 'default'),
                                ('unknown', 'default')]:
            menu.write_text(f'dlss_preset={value}\n')
            assert launcher.load_menu()['dlss_preset'] == expected

        for language in ('en', 'ru'):
            launcher.LANG = language
            Widget.nodes.clear()
            menu.write_text('menu_language=en\nwindow_mode=borderless\nborderless_vsync=0\n')
            obj, home, display = build({'fullscreen': False})
            assert home.current() == display.current() == 1
            assert obj.borderless_vsync_check.kwargs['state'] == 'normal'
            assert obj.presentation_choice.kwargs['state'] == 'disabled'
            assert obj.vars['menu_language'].get() == 'en'
            dlss_choices = obj.dlss_preset_choices
            assert len(dlss_choices) == 2
            assert all(box.kwargs['state'] == 'readonly' for box in dlss_choices)
            assert [key for key, _text in launcher.DLSS_PRESETS] == ['default', 'e', 'f', 'j', 'k', 'm', 'l']
            other_upscaler = obj.vars['upscaler'].get()
            dlss_choices[0].choose(5)  # Can save M even while FSR is selected.
            obj.collect()
            assert launcher.load_menu()['dlss_preset'] == 'm'
            assert obj.vars['upscaler'].get() == other_upscaler
            assert launcher.load_ini()[0]['upscaler'] == other_upscaler
            assert all(box.current() == 5 for box in dlss_choices)
            obj.vars['upscaler'].set('dlss')
            assert all(box.kwargs['state'] == 'readonly' for box in dlss_choices)
            quality = obj.vars['preset'].get()
            resolution = obj.vars['output_res'].get()
            for index, (key, _labels) in enumerate(launcher.DLSS_PRESETS):
                dlss_choices[index % 2].choose(index)
                assert obj.vars['dlss_preset'].get() == key
                assert all(box.current() == index for box in dlss_choices)
                obj.collect()
                assert launcher.load_menu()['dlss_preset'] == key
                assert obj.vars['preset'].get() == quality
                assert obj.vars['output_res'].get() == resolution
            obj.vars['upscaler'].set('fsr3')
            assert all(box.kwargs['state'] == 'readonly' for box in dlss_choices)
            obj.vars['dlss_preset'].set('default')
            overlay_checks = [w for w in Widget.nodes if 'variable' in w.kwargs and
                              w.kwargs['variable'] is obj.vars['show_fps']]
            assert len(overlay_checks) == 3  # Play, Graphics, Display & FPS.
            for box in overlay_checks:
                previous_flag = obj.vars['show_fps'].get()
                box.invoke()
                assert obj.vars['show_fps'].get() != previous_flag
                obj.collect()
                assert launcher.load_menu()['show_fps'] == launcher.load_ini()[0]['show_fps']
            obj.vars['show_fps'].set(True)
            for index, mode in enumerate(('windowed', 'borderless', 'fullscreen')):
                home.choose(index)
                assert obj.vars['window_mode'].get() == mode and display.current() == index
                assert obj.borderless_vsync_check.kwargs['state'] == ('normal' if index == 1 else 'disabled')
                assert obj.presentation_choice.kwargs['state'] == ('disabled' if index == 1 else 'readonly')
                obj.collect()
                assert launcher.menu_values(obj.app)['window_mode'] == mode
                env = launcher.game_environment(obj.app)
                assert env['BB_LAUNCHER_WINDOW_MODE'] == mode
                assert env['BB_FULLSCREEN'] == ('0' if mode == 'windowed' else '1')
                assert json.loads(launcher.CONFIG_FILE.read_text())['window_mode'] == mode
            display.choose(1)
            assert home.current() == 1
            obj.borderless_vsync_check.invoke()
            obj.vars['menu_language'].set('ru')
            obj.collect()
            assert launcher.load_menu() == {**launcher.MENU_DEFAULTS, 'window_mode': 'borderless',
                                           'menu_language': 'ru', 'borderless_vsync': '1'}

            # The in-game menu saves new choices while the launcher remains open.
            menu.write_text('# game changed this\nfuture_option=xyz\nmenu_language=en\n'
                            'window_mode=windowed\nborderless_vsync=0\ndlss_preset=k\nshow_fps=0\n')
            obj.collect()
            assert home.current() == display.current() == 0
            assert obj.vars['menu_language'].get() == 'en' and not obj.vars['borderless_vsync'].get()
            assert '# game changed this' in menu.read_text() and 'future_option=xyz' in menu.read_text()
            assert launcher.load_menu()['window_mode'] == 'windowed'
            assert obj.vars['dlss_preset'].get() == 'k'
            assert all(box.current() == 4 for box in dlss_choices)
            assert not obj.vars['show_fps'].get()
            assert launcher.load_ini()[0]['show_fps'] == '0'

            # A deliberate launcher edit merges with other fresh in-game preferences.
            display.choose(1)
            menu.write_text('menu_language=ru\nwindow_mode=fullscreen\nborderless_vsync=1\n'
                            'dlss_preset=m\nshow_fps=1\nfuture_option=abc\n')
            obj.collect()
            assert launcher.load_menu() == {**launcher.MENU_DEFAULTS, 'window_mode': 'borderless',
                                           'menu_language': 'ru', 'borderless_vsync': '1', 'dlss_preset': 'm'}
            assert 'future_option=abc' in menu.read_text()

            # A deliberate preset/OSD edit also preserves other concurrent game changes.
            dlss_choices[1].choose(3)
            overlay_checks[0].invoke()
            menu.write_text('menu_language=en\nwindow_mode=windowed\nborderless_vsync=0\n'
                            'dlss_preset=l\nshow_fps=1\n')
            obj.collect()
            assert launcher.load_menu() == {**launcher.MENU_DEFAULTS, 'window_mode': 'windowed',
                                           'dlss_preset': 'j', 'show_fps': '0'}
            assert launcher.load_ini()[0]['show_fps'] == '0'

            # "Launcher setting" in-game respects the new launcher's borderless mode.
            menu.write_text('window_mode=launcher\nmenu_language=ru\nborderless_vsync=1\n')
            obj.app['window_mode'] = 'borderless'
            obj.refresh_menu_settings()
            assert obj.vars['window_mode'].get() == 'borderless'
            assert launcher.game_environment(obj.app)['BB_LAUNCHER_WINDOW_MODE'] == 'borderless'
    finally:
        if previous is None: os.environ.pop('BB_CONFIG', None)
        else: os.environ['BB_CONFIG'] = previous

print('PASS: launcher controls in Play/Graphics/Display, seven DLSS presets available even with FSR selected, '
      'exact E/F/J/K/M/L order, presets independent of quality/resolution, '
      'shared OSD switch, legacy FPS/fullscreen migration, preservation of concurrent in-game changes, '
      'preset normalization, environment and custom config paths.')
