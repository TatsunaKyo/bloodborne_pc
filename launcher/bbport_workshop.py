# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Fork settings and tools layered on the upstream launcher.

Runtime paths are resolved through the live launcher context, including portable
installs and test fixtures. Upstream setup, help, save import and update recovery
remain owned by their original modules.
"""
import ctypes
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import urllib.request
import zipfile


def bind(context):
    global m
    m = context


MENU_DEFAULTS = {'menu_language': 'en', 'window_mode': 'launcher', 'borderless_vsync': '0', 'dlss_preset': 'default', 'xess_preset': '2', 'show_fps': '1', 'show_dlss_preset': '0', 'show_resolution': '0', 'show_fg_preset': '0', 'show_frame_generation': '0', 'show_latency': '0', 'show_frametime_graph': '0', 'background_mode': 'run', 'frame_generation': 'off', 'limit_generated_fps': '0', 'generated_fps_limit': '144', 'reflex': 'off', 'nvidia_generated_frames': '1', 'nvidia_fg_preset': 'default', 'amd_antilag': '0', 'real_fps_limit': '-1', 'nvidia_fg_mod': '0', 'cheat_damage': '1', 'cheat_incoming': '1', 'cheat_echoes': '1', 'cheat_movement': '1', 'cheat_infinite_stamina': '0', 'cheat_no_consume': '0', 'cheat_no_fall_damage': '0'}
MENU_FLAGS = {'borderless_vsync', 'show_fps', 'show_dlss_preset', 'show_resolution', 'show_frame_generation', 'show_fg_preset', 'show_latency', 'show_frametime_graph', 'nvidia_fg_mod', 'cheat_infinite_stamina', 'cheat_no_consume', 'cheat_no_fall_damage', 'limit_generated_fps', 'amd_antilag'}
CHEAT_MULTIPLIERS = [('1', ('Off', 'Выключено'))] + [(str(n), (f'x{n}', f'x{n}')) for n in (2, 4, 8, 16)]
MOVEMENT_MULTIPLIERS = [CHEAT_MULTIPLIERS[0], ('1.5', ('x1.5', 'x1.5'))] + CHEAT_MULTIPLIERS[1:]
FRAME_GENERATORS = [('off', ('Off', 'Выключено')), ('fsr', ('FSR Frame Generation (2x)', 'FSR Frame Generation (2x)')), ('nvidia', ('NVIDIA DLSS Frame Generation / MFG', 'NVIDIA DLSS Frame Generation / MFG')), ('native_fsr', ('FSR FG - Supermedo (SDR)', 'FSR FG - Supermedo (SDR)')), ('native_dlss', ('DLSS FG - Supermedo (SDR, restart)', 'DLSS FG - Supermedo (SDR, restart)'))]
REFLEX_MODES = [('off', ('Off', 'Выключено')), ('on', ('On', 'Включено')), ('boost', ('On + Boost', 'Включено + Boost'))]
NVIDIA_MULTIPLIERS = [(str(n - 1), (f'{n}x', f'{n}x')) for n in range(2, 7)]
NVIDIA_FG_PRESETS = [('default', ('Default (NVIDIA settings)', 'По настройкам NVIDIA')), ('a', ('A', 'A')), ('b', ('B', 'B')), ('c', ('C (Performance / beta)', 'C (производительность / бета)'))]
BACKGROUND_MODES = [('run', ('Keep running', 'Продолжать работу')), ('pause', ('Pause game and rendering', 'Приостановить игру и рендер')), ('30', ('Limit to 30 FPS', 'Лимит 30 FPS')), ('60', ('Limit to 60 FPS', 'Лимит 60 FPS'))]
DLSS_PRESETS = [('default', ('Default (driver)', 'По умолчанию (драйвер)')), ('e', ('E (CNN / legacy)', 'E (CNN / устаревший)')), ('f', ('F (CNN / legacy)', 'F (CNN / устаревший)')), ('j', ('J (Transformer 1st gen)', 'J (Transformer 1-го пок.)')), ('k', ('K (Transformer 1st gen)', 'K (Transformer 1-го пок.)')), ('m', ('M (Transformer 2nd gen)', 'M (Transformer 2-го пок.)')), ('l', ('L (Transformer 2nd gen)', 'L (Transformer 2-го пок.)'))]
WINDOW_MODES = [('windowed', ('Windowed', 'Оконный')), ('borderless', ('Borderless fullscreen', 'Без рамки на весь экран')), ('fullscreen', ('Fullscreen (driver default)', 'Полный экран (настройка драйвера)'))]
MENU_LANGUAGES = [('en', ('English',)), ('ru', ('Русский',))]
XESS_PRESETS = [('0', ('Native AA (×1.0)',)), ('1', ('Ultra Quality Plus (×1.3)',)), ('2', ('Ultra Quality (×1.5)',)), ('3', ('Quality (×1.7)',)), ('4', ('Balanced (×2)',)), ('5', ('Performance (×2.3)',)), ('6', ('Ultra Performance (×3)',))]
LEGACY_XESS_PRESETS = ('0', '2', '3', '4', '6')

def menu_path():
    return m.ini_path().with_suffix('.menu.ini')

def load_menu():
    values = dict(MENU_DEFAULTS)
    ini, ini_lines = m.load_ini()
    values['show_fps'] = ini.get('show_fps', '1')
    try:
        legacy = max(0, min(4, int(ini.get('preset', '0'))))
    except ValueError:
        legacy = 0
    # load_ini fills defaults even when the file predates the separate XeSS control.
    # Only an explicit key should take precedence over the old quality index.
    values['xess_preset'] = ini['xess_preset'] if 'xess_preset' in setting_keys(ini_lines) else LEGACY_XESS_PRESETS[legacy]
    if values['xess_preset'] not in dict(XESS_PRESETS):
        values['xess_preset'] = LEGACY_XESS_PRESETS[legacy]
    try:
        lines = menu_path().read_text(encoding='utf-8').splitlines()
    except OSError:
        lines = []
    if not any((line.strip().startswith('real_fps_limit=') for line in lines)):
        previous = m.load_json(m.CONFIG_FILE, {})
        values['real_fps_limit'] = '75' if previous.get('fps_mode') == '75' else previous.get('frame_cap') or '-1'
    for line in lines:
        if '=' in line and (not line.lstrip().startswith('#')):
            key, value = (part.strip() for part in line.split('=', 1))
            if key in values:
                if key == 'xess_preset' and value not in dict(XESS_PRESETS):
                    continue
                values[key] = value
    if values['menu_language'] not in ('en', 'ru'):
        values['menu_language'] = 'en'
    if values['window_mode'] not in ('launcher', 'windowed', 'borderless', 'fullscreen'):
        values['window_mode'] = 'launcher'
    if values['background_mode'] not in dict(BACKGROUND_MODES):
        values['background_mode'] = 'run'
    if values['frame_generation'] not in dict(FRAME_GENERATORS):
        values['frame_generation'] = 'off'
    try:
        values['generated_fps_limit'] = str(max(30, min(1000, int(float(values['generated_fps_limit'])))))
    except (ValueError, OverflowError):
        values['generated_fps_limit'] = '144'
    if values['reflex'] not in dict(REFLEX_MODES):
        values['reflex'] = 'off'
    try:
        limit = int(values['real_fps_limit'])
        values['real_fps_limit'] = str(limit) if limit in (-1, 0) or 30 <= limit <= 1000 else '-1'
    except (ValueError, TypeError):
        values['real_fps_limit'] = '-1'
    if values['nvidia_generated_frames'] not in dict(NVIDIA_MULTIPLIERS):
        values['nvidia_generated_frames'] = '1'
    values['nvidia_fg_preset'] = values['nvidia_fg_preset'].lower()
    if values['nvidia_fg_preset'] not in dict(NVIDIA_FG_PRESETS):
        values['nvidia_fg_preset'] = 'default'
    for key in MENU_FLAGS:
        values[key] = '1' if values[key] == '1' else '0'
    for key in ('cheat_damage', 'cheat_incoming', 'cheat_echoes', 'cheat_movement'):
        options = MOVEMENT_MULTIPLIERS if key == 'cheat_movement' else CHEAT_MULTIPLIERS
        if values[key] not in dict(options):
            values[key] = '1'
    preset = values['dlss_preset'].lower()
    preset = dict(zip(('0', '5', '6', '10', '11', '12', '13'), ('default', 'e', 'f', 'j', 'k', 'l', 'm'))).get(preset, preset)
    values['dlss_preset'] = preset if preset in dict(DLSS_PRESETS) else 'default'
    return values

def launcher_window_mode(settings):
    mode = settings.get('window_mode')
    return mode if mode in ('windowed', 'borderless', 'fullscreen') else 'fullscreen' if settings.get('fullscreen') else 'windowed'

def menu_values(settings):
    values = load_menu()
    if values['window_mode'] == 'launcher':
        values['window_mode'] = launcher_window_mode(settings)
    return values

def save_menu(changes):
    """Merge only edited controls into the current file; the game may have changed it."""
    if not changes:
        return
    try:
        lines = menu_path().read_text(encoding='utf-8').splitlines()
    except OSError:
        lines = []
    written, output = (set(), [])
    for line in lines:
        key = line.split('=', 1)[0].strip() if '=' in line and (not line.lstrip().startswith('#')) else None
        if key in changes:
            output.append(f'{key}={changes[key]}')
            written.add(key)
        else:
            output.append(line)
    output += [f'{key}={value}' for key, value in changes.items() if key not in written]
    temporary = menu_path().with_suffix('.menu.ini.launcher-tmp')
    temporary.write_text('\n'.join(output) + '\n', encoding='utf-8')
    os.replace(temporary, menu_path())

def geometry_diagnostic_settings(settings, args):
    for mode in ('normal', 'serial', 'capture'):
        if f'--geometry-diagnostic={mode}' in args:
            return {**settings, 'developer_profile': True, '_geometry_diagnostic': mode}
    return settings

def nvidia_diagnostic_settings(settings, args):
    for mode in ('inputs', 'generated-only'):
        if f'--nvidia-diagnostic={mode}' in args:
            return {**settings, 'developer_profile': True, '_nvidia_diagnostic': mode}
    return settings

def traversal_diagnostic_settings(settings, args):
    if '--traversal-diagnostic' in args:
        return {**settings, 'developer_profile': True, '_traversal_diagnostic': True}
    return settings

class DiagnosticSession:
    """One opt-in session, kept after normal exits as well as crashes."""

    def __init__(self, settings):
        self.directory = None
        self.log = None
        self.started = time.monotonic()
        self.metadata = {}
        if not settings.get('developer_profile'):
            return
        root = Path(settings.get('user_dir') or m.DATA_DIR / 'user') / 'diagnostics'
        root.mkdir(parents=True, exist_ok=True)
        self.directory = Path(tempfile.mkdtemp(prefix=time.strftime('%Y%m%d-%H%M%S-'), dir=root))
        keys = ('window_mode', 'fullscreen', 'hdr', 'present_mode', 'fps_mode', 'frame_cap', 'frames_ahead', 'draw_pipe', 'readbacks', 'vk_validation')
        system = {'system': sys.platform, 'architecture_bits': ctypes.sizeof(ctypes.c_void_p) * 8}
        if hasattr(sys, 'getwindowsversion'):
            system['windows_version'] = list(sys.getwindowsversion()[:3])
        self.metadata = {'revision': m.VERSION, 'platform': system, 'started': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'settings': {key: settings.get(key) for key in keys}, 'ini': m.load_ini()[0], 'menu_at_start': menu_values(settings), 'status': 'running'}
        if settings.get('_geometry_diagnostic'):
            self.metadata['geometry_diagnostic'] = settings['_geometry_diagnostic']
        if settings.get('_nvidia_diagnostic'):
            self.metadata['nvidia_diagnostic'] = settings['_nvidia_diagnostic']
        if settings.get('_traversal_diagnostic'):
            self.metadata['traversal_diagnostic'] = True
        self.write_metadata()
        self.log = open(self.directory / 'session.log', 'w', encoding='utf-8', buffering=1)

    def environment(self, env):
        if self.directory:
            env.update(BB_FRAME_STATS='1', BB_GPU_PROFILE='1', BB_DIAGNOSTICS_DIR=str(self.directory.resolve()))
            if self.metadata.get('nvidia_diagnostic') or self.metadata.get('traversal_diagnostic'):
                env['BB_HITCH_TRACE'] = '1'
                env['BB_HITCH_TRACE_PATH'] = str((self.directory / 'cpu-timeline.jsonl').resolve())
                env.pop('BB_GPU_PROFILE', None)
                self.metadata['cpu_hitch_trace'] = {'enabled': True, 'ring_events': 65536, 'gpu_timestamp_profiler': False, 'normal_renderer_preserved': True, 'causal_timeline': True, 'timeline_maximum_bytes': 16 * 1024 * 1024, 'interpretation': 'CPU spans are inclusive and may overlap; they are not GPU durations.'}
                self.record('Traversal CPU trace and bounded dependency timeline active with your current FG setting. Reproduce the hitch and close the game. No key press is required for the log archive.\n')
            if self.metadata.get('nvidia_diagnostic'):
                captures = self.directory / 'fg-inputs'
                captures.mkdir()
                env.update(BB_FG_CAPTURE_TRIGGER=str((self.directory / 'fg-capture.trigger').resolve()), BB_FG_CAPTURE_DIR=str(captures.resolve()))
                self.metadata['frame_capture'] = {'key': 'F8', 'requested_frames': 4, 'position': 'nvidia_tagged_inputs', 'maximum_raw_bytes': 256 * 1024 * 1024, 'normal_renderer_preserved': True}
                self.record('NVIDIA FG diagnostic: ' + self.metadata['nvidia_diagnostic'] + "\nKeep NVIDIA FG enabled. Press F8 while the assets flash, then close the game. The capture includes tagged depth/motion/constants and the real backbuffer; it does not capture NVIDIA's internal generated image. Readbacks can affect timing. CPU flight recording is active; reproduce the traversal hitch before pressing F8.\n")
            if self.metadata.get('geometry_diagnostic') == 'capture':
                captures = self.directory / 'frames'
                captures.mkdir()
                env.update(BB_GEOMETRY_CAPTURE='1', BB_DUMP_FRAMES='8', BB_DUMP_POLL_FRAMES='1', BB_DUMP_TRIGGER=str((self.directory / 'capture.trigger').resolve()), BB_DUMP_DIR=str(captures.resolve()), BB_CAPTURE_TRIGGER=str((self.directory / 'passes.trigger').resolve()), BB_CAPTURE_DIR=str((self.directory / 'passes').resolve()))
                (self.directory / 'passes').mkdir()
                self.record('Frame capture ready: press F8 when assets flash, then close the game. This records eight scene-input/output frames before Frame Generation.\n')
                self.metadata['frame_capture'] = {'key': 'F8', 'requested_frames': 8, 'position': 'before_frame_generation'}
            keys = ('BB_DRAW_PIPE', 'BB_PREP_WORKERS', 'BB_VK_RECORD_THREAD', 'BB_COPY_THREADS', 'BB_FRAME_STATS', 'BB_GPU_PROFILE', 'BB_PIPE_VERIFY', 'BB_GEOMETRY_CAPTURE', 'BB_DUMP_FRAMES', 'BB_DUMP_POLL_FRAMES', 'BB_PIPELINE_CACHE', 'BB_OBJECT_MOTION', 'BB_UPSCALER', 'BB_READBACKS', 'BB_FG_GENERATED_ONLY', 'BB_HITCH_TRACE')
            self.metadata['renderer_environment'] = {key: env[key] for key in keys if key in env}
            self.write_metadata()
            if self.metadata.get('geometry_diagnostic'):
                self.record('Geometry diagnostic: ' + self.metadata['geometry_diagnostic'] + '\n')
        return env

    def write_metadata(self):
        if self.directory:
            target = self.directory / 'session.json'
            temporary = target.with_suffix('.tmp')
            temporary.write_text(json.dumps(self.metadata, indent=2, ensure_ascii=False), encoding='utf-8')
            temporary.replace(target)

    def record(self, text):
        if self.log:
            self.log.write(f'[{time.monotonic() - self.started:10.3f}s] {text}')

    def finish(self, code):
        if self.directory:
            self.metadata.update(status='exited', exit_code=code, duration_seconds=round(time.monotonic() - self.started, 3), menu_at_exit=load_menu())
            self.record(f'Process exited with code {code}\n')
            self.write_metadata()
            self.log.close()
            if self.metadata.get('geometry_diagnostic') == 'capture':
                self.archive_capture()
            if self.metadata.get('nvidia_diagnostic') or self.metadata.get('traversal_diagnostic'):
                self.archive_fg_capture()

    def archive_fg_capture(self):
        from fg_diagnostic import export_capture
        result = export_capture(self.directory, m.PORT_DIR, self.metadata)
        self.metadata.setdefault('frame_capture', {}).update(result)
        self.metadata['diagnostic_archive'] = result
        self.write_metadata()
        if result.get('archive'):
            print('Renderer diagnostic saved: ' + str(self.directory / result['archive']), flush=True)
            if result['status'] == 'logs_only':
                print('CPU logs/settings were saved. No gameplay images were captured; F8 is only needed for NVIDIA image readbacks.', flush=True)
            print('Inspect this private archive before sharing; nothing is uploaded.', flush=True)
        else:
            print('NVIDIA FG diagnostic: ' + result['status'] + '. The individual capture files are retained.', flush=True)

    def archive_capture(self):
        """Bundle the private session's frames after the game has stopped."""
        captures = self.directory / 'frames'
        frames = sorted(captures.glob('*.raw'))
        archive = self.directory / 'Flashing-assets-diagnostic.zip'
        temporary = archive.with_suffix('.tmp')
        try:
            if not frames:
                self.metadata['frame_capture']['status'] = 'no_frames'
                print('No frames captured. Run Capture-Flashing-Assets.cmd and press F8 in the affected scene.', flush=True)
                self.write_metadata()
                return
            inputs = {path.name.split('_')[0] for path in frames if '_input_' in path.name}
            outputs = {path.name.split('_')[0] for path in frames if '_output_' in path.name}
            pairs = len(inputs & outputs)
            self.metadata['frame_capture'].update(status='captured' if pairs == 8 else 'incomplete', raw_files=len(frames), paired_frames=pairs)
            self.write_metadata()
            with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as bundle:
                for path in (self.directory / 'session.log', self.directory / 'session.json', *frames, *sorted((self.directory / 'passes').glob('*'))):
                    if path.is_file():
                        bundle.write(path, path.relative_to(self.directory))
            temporary.replace(archive)
            print(f'Flashing diagnostic saved: {archive}', flush=True)
        except (OSError, zipfile.BadZipFile) as error:
            temporary.unlink(missing_ok=True)
            self.metadata['frame_capture'].update(status='archive_failed', error_type=type(error).__name__)
            self.write_metadata()
            print(f'Cannot package the capture ({error}); the individual files are in {self.directory}.', flush=True)

def version_tuple(text):
    return tuple((int(number) for number in re.findall('\\d+', text or '')))

def update_package_name(version):
    from release_integrity import package_name
    return package_name(version)

def verify_update_archive(archive, version, sidecar):
    """Check the downloaded checksum and release identity before running its code."""
    from release_integrity import checksum, validate
    archive = Path(archive)
    if not isinstance(sidecar, str) or len(sidecar) > 4096:
        raise ValueError('Invalid update checksum file.')
    match = re.fullmatch('([0-9a-fA-F]{64})[ \\t]+\\*?([^\\r\\n]+)\\s*', sidecar.strip())
    if not match or match[2] != archive.name or match[1].lower() != checksum(archive):
        raise ValueError('The downloaded update does not match its SHA-256 checksum.')
    try:
        return validate(archive, expected_version=version)['root']
    except (TypeError, KeyError, SyntaxError) as failure:
        raise ValueError('The update contains malformed release metadata.') from failure

def latest_release():
    """(version, Windows package URL, page URL) of this fork's latest revision."""
    request = urllib.request.Request(m.RELEASES_API, headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'bbport-launcher'})
    with m.bbport_tls.urlopen(request, timeout=15) as response:
        release = json.load(response)
    return parse_release(release)

def parse_release(release):
    if not isinstance(release, dict) or release.get('draft') or release.get('prerelease'):
        raise ValueError('The stable updater does not install drafts or prereleases.')
    tag_name = release.get('tag_name')
    tag = re.fullmatch('windows-v(\\d+(?:\\.\\d+)*)-tatsunakyo\\.(\\d+)(?:-preview)?', tag_name) if isinstance(tag_name, str) else None
    if not tag:
        raise ValueError('The latest release is not a TatsunaKyo Windows revision.')
    version = f'{tag[1]}-tatsunakyo.{tag[2]}'
    package_name = f'Bloodborne-Windows-v{tag[1]}-TatsunaKyo-Revision-{tag[2]}.zip'
    assets = release.get('assets', [])
    if not isinstance(assets, list):
        raise ValueError('Invalid release asset list.')
    packages = [asset for asset in assets if isinstance(asset, dict) and asset.get('name') == package_name and (asset.get('state', 'uploaded') == 'uploaded')]
    url = packages[0].get('browser_download_url') if len(packages) == 1 else None
    if url and (not isinstance(url, str) or not url.startswith('https://')):
        raise ValueError('Invalid Windows package URL.')
    if url:
        if packages[0].get('digest'):
            m.ASSET_DIGESTS[url] = packages[0]['digest']
        sidecars = [asset for asset in assets if isinstance(asset, dict) and asset.get('name') == package_name + '.sha256']
        if len(sidecars) == 1:
            CHECKSUM_URLS[url] = sidecars[0].get('browser_download_url')
    return (version, url, release.get('html_url') or m.RELEASES_PAGE)

def installable_releases():
    """[(version, zip URL, page URL)] of the published releases from OLDEST_INSTALLABLE on, newest
    first (drafts, pre-releases and releases without a zip left out)."""
    request = urllib.request.Request(m.RELEASES_LIST_API, headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'bbport-launcher'})
    with m.bbport_tls.urlopen(request, timeout=15) as response:
        releases = json.load(response)
    if not isinstance(releases, list):
        raise ValueError('Invalid release list.')
    found = {}
    for release in releases:
        try:
            version, url, page = parse_release(release)
        except ValueError:
            continue
        if url and version_tuple(version) >= version_tuple(m.OLDEST_INSTALLABLE):
            found.setdefault(version, (version, url, page))
    return sorted(found.values(), key=lambda item: version_tuple(item[0]), reverse=True)

class WorkshopMixin:

    def dlss_preset_choice(self, parent, width=38):
        box = self.choice(parent, 'dlss_preset', 'menu', DLSS_PRESETS, width)
        if not hasattr(self, 'dlss_preset_choices'):
            self.dlss_preset_choices = []
        self.dlss_preset_choices.append(box)
        upscaler = self.var('upscaler', 'ini')

        def availability(*_args):
            box.configure(state='readonly' if upscaler.get() == 'dlss' else 'disabled')
        upscaler.trace_add('write', availability)
        availability()
        return box

    def frame_generation_choice(self, parent, width=38):
        choices = [(key, ('NVIDIA DLSS FG / MFG', 'NVIDIA DLSS FG / MFG') if key == 'nvidia' else labels) for key, labels in FRAME_GENERATORS] if width < 30 else FRAME_GENERATORS
        box = self.choice(parent, 'frame_generation', 'menu', choices, width=width)
        upscaler = self.var('upscaler', 'ini')

        def availability(*_args):
            box.configure(state='readonly' if upscaler.get() != 'off' else 'disabled')
        upscaler.trace_add('write', availability)
        availability()
        return box

    def fps_cap_control(self, parent, key, store, minimum, maximum, enabled_key=None, options=None):
        """Exact entry and relative dragging: moving one pixel changes one FPS."""
        tk, ttk = (self.tk, self.ttk)
        holder = ttk.Frame(parent)
        value = self.var(key, store)
        draft = tk.StringVar()
        position = tk.DoubleVar()
        labels = {v: m._(*text) for v, text in options or []}
        if options:
            labels['-1'] = m._('Auto', 'Авто')
            labels['0'] = m._('No cap', 'Без ограничения')
        if options:
            entry = ttk.Combobox(holder, textvariable=draft, width=19, values=list(labels.values()), state='normal')
        else:
            entry = ttk.Spinbox(holder, textvariable=draft, from_=minimum, to=maximum, increment=1, width=7)
        entry.pack(side='right', padx=(10, 0))
        slider = ttk.Scale(holder, from_=minimum, to=maximum, variable=position, length=self.px(160))
        slider.pack(side='left', fill='x', expand=True)
        anchor = [0, minimum]

        def number():
            try:
                candidate = int(value.get())
                return min(maximum, 120) if candidate <= 0 else max(minimum, min(maximum, candidate))
            except (ValueError, tk.TclError):
                return min(maximum, 120)

        def commit(_event=None):
            text = draft.get().strip()
            reverse = {label: v for v, label in labels.items()}
            if text in reverse:
                value.set(reverse[text])
            else:
                try:
                    candidate = int(text)
                    ceiling = 1000 if options else maximum
                    floor = 0 if options else minimum
                    value.set(str(max(floor, min(ceiling, candidate))))
                except ValueError:
                    pass
            show()
            return 'break'

        def show(*_args):
            draft.set(labels.get(value.get(), value.get()))
            position.set(number())
            enabled = enabled_key is None or self.var(enabled_key, 'menu').get()
            slider.configure(state='normal' if enabled else 'disabled')
            entry.configure(state='normal' if enabled else 'disabled')

        def press(event):
            anchor[:] = [event.x, number()]
            return 'break'

        def drag(event):
            if enabled_key is None or self.var(enabled_key, 'menu').get():
                step = 0.25 if event.state & 1 else 1.0
                candidate = round(anchor[1] + (event.x - anchor[0]) * step)
                value.set(str(max(minimum, min(maximum, candidate))))
            return 'break'

        def step(amount):
            if enabled_key is None or self.var(enabled_key, 'menu').get():
                value.set(str(max(minimum, min(maximum, number() + amount))))
            return 'break'
        entry.bind('<Return>', commit)
        entry.bind('<FocusOut>', commit)
        if options:
            entry.bind('<<ComboboxSelected>>', commit)
        else:
            entry.configure(command=commit)
        slider.bind('<ButtonPress-1>', press)
        slider.bind('<B1-Motion>', drag)
        slider.bind('<ButtonRelease-1>', lambda _event: 'break')
        slider.bind('<Left>', lambda _event: step(-1))
        slider.bind('<Right>', lambda _event: step(1))
        value.trace_add('write', show)
        if enabled_key:
            self.var(enabled_key, 'menu').trace_add('write', show)
        show()
        if not hasattr(self, 'fps_cap_committers'):
            self.fps_cap_committers = []
        self.fps_cap_committers.append(commit)
        return self.workshop_track_setting(parent, key, holder)

    def support_report_context(self):
        """Read current UI/preferences without changing game, mod or launcher files."""
        app, ini, menu = (dict(self.app), dict(self.ini), dict(self.menu))
        stores = {'app': app, 'ini': ini, 'menu': menu}
        for key, var in self.vars.items():
            try:
                value = var.get()
            except self.tk.TclError:
                continue
            stores[var.store][key] = value
        return {'port_dir': m.PORT_DIR, 'user_dir': Path(app.get('user_dir') or m.DATA_DIR / 'user'), 'settings': app, 'ini': ini, 'menu': menu, 'revision': m.VERSION}

    def generate_support_report(self):
        from support_report_ui import open_support_report
        return open_support_report(self)

    def open_save_manager(self):
        from save_manager_ui import open_save_manager
        return open_save_manager(self)

    def workshop_init(self):
        self.menu = load_menu()
        self.menu_baseline = dict(self.menu)
        # The upstream root INI is authoritative once migrated; legacy menu caps
        # and native provider selections are consumed only for an older file.
        present = {line.split('=', 1)[0].strip() for line in self.ini_lines if '=' in line}
        if 'frame_cap' not in present:
            limit = self.menu['real_fps_limit']
            self.app['frame_cap'] = '' if limit == '-1' else limit
        if 'frame_generation' not in _menu_keys():
            self.menu['frame_generation'] = NATIVE_TO_ROUTE.get(self.ini.get('frame_gen'), 'off')
        if 'reflex' in _menu_keys():
            self.app['low_latency'] = self.menu['reflex'] if self.menu['reflex'] != 'off' else 'on' if self.menu['amd_antilag'] == '1' else 'off'
        if self.app.get('low_latency') == 'off' and self.menu.get('reflex') != 'off':
            self.app['low_latency'] = self.menu['reflex']
        if self.app.get('low_latency') == 'off' and self.menu.get('amd_antilag') == '1':
            self.app['low_latency'] = 'on'
        self._workshop_syncing = False

    def workshop_var(self, key):
        if key == 'show_fps':
            return self.var(key, 'ini')
        if key not in self.vars:
            value = self.menu.get(key, MENU_DEFAULTS[key])
            var = self.tk.BooleanVar(value=value == '1') if key in MENU_FLAGS else self.tk.StringVar(value=value)
            var.store = 'menu'
            self.vars[key] = var
        return self.vars[key]

    @staticmethod
    def show_workshop_row(widget, visible):
        for child in widget.workshop_widgets:
            child.grid() if visible else child.grid_remove()

    def workshop_track_setting(self, parent, key, widget):
        self.index_entry(widget, key.replace('_', ' ').title(), key=key)
        return widget

    def build_workshop_graphics(self, frame):
        self.section(frame, m._('Crowned Workshop'))
        self.graphics_dlss_row = self.row(frame, m._('DLSS render preset'), self.dlss_preset_choice(frame),
                 m._('Model hint; the driver can override it. Separate from render scale and FG.'))
        self.graphics_xess_row = self.row(frame, m._('XeSS quality'), self.choice(frame, 'xess_preset', 'menu', XESS_PRESETS),
                 m._('Seven XeSS ratios, saved separately from DLSS and FSR quality.'))
        self.note(frame, m._('Workshop FG supports HDR. Supermedo FG is SDR; native DLSS requires a restart.'))
        route = self.var('frame_generation', 'menu')
        native = self.var('frame_gen', 'ini')

        def sync_route(*_args):
            if self._workshop_syncing:
                return
            self._workshop_syncing = True
            try:
                native.set(ROUTE_TO_NATIVE.get(route.get(), 'off'))
            finally:
                self._workshop_syncing = False

        def sync_native(*_args):
            if self._workshop_syncing:
                return
            self._workshop_syncing = True
            try:
                route.set(NATIVE_TO_ROUTE.get(native.get(), 'off'))
            finally:
                self._workshop_syncing = False
        route.trace_add('write', sync_route)
        native.trace_add('write', sync_native)
        sync_route()
        def show_quality(*_args):
            upscaler = self.var('upscaler', 'ini').get()
            self.show_workshop_row(self.graphics_xess_row, upscaler == 'xess')
            self.show_workshop_row(self.graphics_dlss_row, upscaler == 'dlss')
            self.show_workshop_row(self.graphics_preset_row, upscaler != 'xess')
        self.var('upscaler', 'ini').trace_add('write', show_quality)
        show_quality()
        self.nvidia_multiplier_row = self.row(
            frame, m._('Workshop NVIDIA multiplier'), self.choice(frame, 'nvidia_generated_frames', 'menu', NVIDIA_MULTIPLIERS))
        self.nvidia_fg_preset_row = self.row(
            frame, m._('Workshop NVIDIA FG preset'), self.choice(frame, 'nvidia_fg_preset', 'menu', NVIDIA_FG_PRESETS),
            m._('A saved request is shown separately from driver evidence in the overlay.'))
        self.nvidia_fg_mod_row = self.check(
            frame, 'nvidia_fg_mod', 'menu', m._('RTX 20/30: enable external DLSSG mod'),
            m._('Opt in only. Requires your compatible Encore library; RTX 40/50 retain original NVIDIA files. Restart required.'))

        def show_nvidia(*_args):
            for row in (self.nvidia_multiplier_row, self.nvidia_fg_preset_row, self.nvidia_fg_mod_row):
                self.show_workshop_row(row, route.get() == 'nvidia')

        route.trace_add('write', show_nvidia)
        show_nvidia()
        self.check(frame, 'limit_generated_fps', 'menu', m._('Limit generated output'))
        self.row(frame, m._('Generated output FPS'), self.fps_cap_control(frame, 'generated_fps_limit', 'menu', 30, 1000, 'limit_generated_fps'))
        self.row(frame, m._('Background behavior'), self.choice(frame, 'background_mode', 'menu', BACKGROUND_MODES))
        self.row(frame, m._('Window mode'), self.choice(frame, 'window_mode', 'menu', [('launcher', ('Follow launcher',)), *WINDOW_MODES]))
        self.check(frame, 'borderless_vsync', 'menu', m._('VSync in borderless mode'))
        self.section(frame, m._('Workshop overlay'))
        for key, text in [('show_dlss_preset', 'DLSS render preset'), ('show_fg_preset', 'NVIDIA FG preset evidence'),
                          ('show_resolution', 'Internal and output resolution'), ('show_frame_generation', 'Real and generated frame rate'),
                          ('show_latency', 'Reflex PC latency'), ('show_frametime_graph', 'Real-frame frametime graph')]:
            self.check(frame, key, 'menu', m._(text))
    def build_workshop_cheats(self, frame):
        self.section(frame, m._('Runtime cheats', 'Читы в игре'))
        for key, label in [('cheat_damage', 'Damage dealt'), ('cheat_incoming', 'Damage received'), ('cheat_echoes', 'Blood Echoes'), ('cheat_movement', 'Movement speed')]:
            self.row(frame, m._(label), self.choice(frame, key, 'menu', MOVEMENT_MULTIPLIERS if key == 'cheat_movement' else CHEAT_MULTIPLIERS))
        for key, label in [('cheat_infinite_stamina', 'Infinite stamina'), ('cheat_no_consume', 'Do not consume items'), ('cheat_no_fall_damage', 'No fall damage')]:
            self.check(frame, key, 'menu', m._(label))

    def build_workshop_diagnostics(self, frame):
        self.section(frame, m._('Workshop diagnostics', 'Диагностика Workshop'))
        self.check(frame, 'developer_profile', 'app', m._('Record an opt-in diagnostic session'))
        self.workshop_button(frame, m._('Generate Support Report…', 'Создать отчёт…'),
                             self.generate_support_report, 'button:support_report')
        for attribute, mode, title in (
            ('nvidia_capture_button', 'inputs', m._('Capture NVIDIA FG inputs…', 'Записать входные данные NVIDIA FG…')),
            ('nvidia_compare_button', 'generated-only', m._('Compare generated frames…', 'Сравнить сгенерированные кадры…')),
            ('traversal_capture_button', 'traversal', m._('Capture a traversal hitch…', 'Записать рывок при перемещении…')),
        ):
            setattr(self, attribute, self.workshop_button(
                frame, title, lambda mode=mode: self.play(mode), 'button:' + mode))

    def workshop_button(self, frame, title, command, key):
        button = self.ttk.Button(frame, text=title, command=command)
        button.grid(row=self.next_row(frame), column=0, columnspan=2, sticky='w', pady=(5, 0))
        self.index_entry(button, title, key=key)
        return button

    def refresh_menu_settings(self):
        if not hasattr(self, 'menu'):
            return
        disk = load_menu()
        if disk.get('reflex') != self.menu_baseline.get('reflex') or disk.get('amd_antilag') != self.menu_baseline.get('amd_antilag'):
            var = self.vars.get('low_latency')
            if var is None or var.get() == self.app.get('low_latency'):
                latency = disk['reflex'] if disk['reflex'] != 'off' else 'on' if disk['amd_antilag'] == '1' else 'off'
                self.app['low_latency'] = latency
                if var is not None: var.set(latency)
        self._workshop_syncing = True
        try:
            for key, value in disk.items():
                var = self.vars.get(key)
                before = self.menu_baseline.get(key)
                if var is not None and var.store == 'menu':
                    current = var.get()
                    current = '1' if current is True else '0' if current is False else str(current)
                    if current == before:
                        var.set(value == '1' if key in MENU_FLAGS else value)
                    else:
                        continue
                self.menu[key] = value
            self.menu_baseline = disk
        finally:
            self._workshop_syncing = False

    def collect_workshop(self):
        if not hasattr(self, 'menu'):
            return  # fixtures constructing only an upstream page
        # Preserve changes made by the running overlay to controls untouched here.
        changes = {key: value for key, value in self.menu.items() if value != self.menu_baseline.get(key)}
        cap = str(self.app.get('frame_cap', ''))
        self.menu['real_fps_limit'] = cap or '-1'
        changes['real_fps_limit'] = self.menu['real_fps_limit']
        self.menu['show_fps'] = self.ini.get('show_fps', '1')
        changes['show_fps'] = self.menu['show_fps']
        # The native runtime and Workshop presenter share one route selection.
        self.ini['frame_gen'] = ROUTE_TO_NATIVE.get(self.menu['frame_generation'], 'off')
        self.ini['xess_preset'] = self.menu['xess_preset']
        self.menu['reflex'] = self.app.get('low_latency', 'off')
        changes['reflex'] = self.menu['reflex']
        if changes:
            save_menu(changes)
        self.menu = load_menu()
        self.menu_baseline = dict(self.menu)


NATIVE_TO_ROUTE = {'off': 'off', 'fsr3': 'native_fsr', 'dlss': 'native_dlss', 'fsr401': 'native_fsr401', 'fsr402': 'native_fsr402'}
ROUTE_TO_NATIVE = {route: native for native, route in NATIVE_TO_ROUTE.items()}
FRAME_GENERATORS += [('native_fsr401', ('AMD ML-FG 4.0.1 (SDR, RX 9000, experimental)',)),
                     ('native_fsr402', ('AMD ML-FG 4.0.2 (SDR, RX 9000, experimental)',))]
CHECKSUM_URLS = {}


def setting_keys(lines):
    return {line.split('=', 1)[0].strip() for line in lines if '=' in line and not line.lstrip().startswith('#')}


def migrate_saved_settings(saved):
    saved = dict(saved)
    if 'auto_backup' not in saved and 'save_auto_backup' in saved:
        saved['auto_backup'] = bool(saved['save_auto_backup'])
    saved.pop('save_auto_backup', None)
    return saved


def _menu_keys():
    try:
        return setting_keys(menu_path().read_text(encoding='utf-8').splitlines())
    except OSError:
        return set()


def environment(env, settings, graphics=None):
    env['BB_LAUNCHER_WINDOW_MODE'] = launcher_window_mode(settings)
    # The runtime takes one validated snapshot after acquiring its save lease.
    env['BB_SAVE_AUTO_BACKUP'] = '1' if settings.get('auto_backup', True) else '0'
    env['BB_SAVE_BACKUP_RETENTION'] = str(settings.get('save_backup_retention', 10))
    if settings.get('_geometry_diagnostic') in ('serial', 'capture'):
        env.update(BB_DRAW_PIPE='0', BB_PREP_WORKERS='0', BB_VK_RECORD_THREAD='0', BB_COPY_THREADS='0')
    if settings.get('_nvidia_diagnostic'):
        env['BB_FG_GENERATED_ONLY'] = '1' if settings['_nvidia_diagnostic'] == 'generated-only' else '0'
    return env


def checksum_url(url):
    found = CHECKSUM_URLS.get(url, url + '.sha256')
    if not isinstance(found, str) or not found.startswith('https://'):
        raise ValueError('Invalid update checksum URL.')
    return found


def read_game_output(process, settings, diagnostic, observe=None, before=()):
    """Drain a headless game even when the log file or output consumer fails."""
    directory = Path(settings.get('user_dir') or m.DATA_DIR / 'user')
    log = m.RunLog(directory / 'last_run.log', lambda text: None)
    for note in before:
        log.write(note + '\n')
    log.write(f'Bloodborne launcher {m.VERSION}\n')
    log.write('Launch settings: ' + json.dumps({key: settings.get(key) for key in
              ('fps', 'frame_cap', 'fullscreen', 'upscaler')}) + '\n')
    log.write('Requested graphics: ' + json.dumps({key: settings.get(key) for key in
              ('frame_generation', 'nvidia_generated_frames', 'generated_fps_limit')}) + '\n')
    try:
        for raw in iter(process.stdout.readline, b''):
            text = raw.decode('utf-8', errors='replace')
            diagnostic.record(text)
            log.write(text)
            if observe:
                try:
                    observe(text)
                except (OSError, ValueError):
                    pass
        code = process.wait()
        log.write(f'Process exited with code {code}\n')
    finally:
        log.close()
    diagnostic.finish(code)
    return code


def fetch_checksum(url):
    with m.bbport_tls.urlopen(checksum_url(url), timeout=30) as response:
        return response.read(4097).decode('utf-8')
