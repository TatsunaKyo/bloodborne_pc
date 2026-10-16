#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Bloodborne launcher for Windows (Tkinter; launcher/bbport_launcher.py is the Linux one).

Every setting of the port in one window: the game folder and saves, bbport.ini (upscaler,
preset, output, effects), start-up options passed to run.py as environment variables
(frame rate, presentation, HDR, ...), mods, third-party patches and the FSR 4 assets.
Launcher options live in %APPDATA%/bbport-launcher/settings.json.

Frozen with PyInstaller (packaging/windows/package.sh) the same Bloodborne.exe also runs the
game without the window (`--play`), run.py (`--run`) and the preparation scripts (`--script`),
so a packaged port needs no Python installation.
"""
import ctypes
import json
import os
from pathlib import Path
import queue
import re
import runpy
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import webbrowser
import zipfile

FROZEN = getattr(sys, 'frozen', False)
PORT_DIR = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PORT_DIR / 'scripts'))
sys.path.insert(0, str(PORT_DIR / 'tools'))
if FROZEN:
    # The packaged CPython 3.14 Pillow modules live beside the bundled runtime.
    sys.path.insert(0, str(PORT_DIR / '_internal'))
DATA_DIR = Path(os.environ.get('BB_DATA_DIR', PORT_DIR))
# Co-op test build: its own settings, and no updates (a public release would replace it).
COOP_TEST = False
CONFIG_DIR = Path(os.environ.get('APPDATA', Path.home())) / ('bbport-launcher-coop' if COOP_TEST else 'bbport-launcher')
CONFIG_FILE = CONFIG_DIR / 'settings.json'
PATCH_VERSION = '01.09'
MAX_LOG_LINES = 6000
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
# Fork releases use windows-v<upstream version>-tatsunakyo.<revision>.
VERSION = '1.6-tatsunakyo.52'
LAUNCHER_BUILD = 'TatsunaKyo revision'
# Co-op: the community server that answers the game's own server requests.
COMMUNITY_SERVER = 'https://thehuntersdream.com'
RELEASES_API = 'https://api.github.com/repos/TatsunaKyo/bloodborne_pc/releases/latest'
RELEASES_PAGE = 'https://github.com/TatsunaKyo/bloodborne_pc/releases/latest'
# Never copied over an installation by an update (the package does not hold them either).
USER_FILES = ('user', 'out', 'mods', 'bbport.ini', 'bbport.menu.ini', 'mods.json', 'patches.json', 'last_run.log')


# ---------------------------------------------------------------------------------------------
# Command line roles of the frozen executable.

def attach_stdio():
    """A windowed executable starts without sys.stdout; inherited pipes or a console still exist."""
    import msvcrt
    for name, std in (('stdout', -11), ('stderr', -12)):
        if getattr(sys, name) is not None:
            continue
        stream = None
        handle = ctypes.windll.kernel32.GetStdHandle(std)
        if handle and handle != ctypes.c_void_p(-1).value:
            try:
                stream = open(msvcrt.open_osfhandle(handle, os.O_WRONLY), 'w', encoding='utf-8',
                              errors='replace', buffering=1)
            except OSError:
                stream = None
        setattr(sys, name, stream or open(os.devnull, 'w'))


def run_role(argv):
    """--run [args]: run.py; --script <file> [args]: a preparation script. Returns an exit code."""
    attach_stdio()
    for stream in (sys.stdout, sys.stderr):  # keep messages in order with the game's output
        try:
            stream.reconfigure(line_buffering=True)
        except (AttributeError, ValueError):
            pass
    if argv[0] == '--script':
        path, sys.argv = argv[1], argv[1:]
    else:
        path = str(PORT_DIR / 'run.py')
        sys.argv = [path, *argv[1:]]
    try:
        runpy.run_path(path, run_name='__main__')
    except SystemExit as stop:
        return stop.code if isinstance(stop.code, int) else (0 if stop.code is None else 1)
    except Exception:
        # Command-line roles must return a failed exit code and readable stderr,
        # rather than waiting indefinitely on a windowed bootloader error dialog.
        import traceback
        traceback.print_exc()
        return 1
    return 0


def run_command():
    """The command that starts run.py: this executable when frozen, else Python."""
    return [sys.executable, '--run'] if FROZEN else [sys.executable, str(PORT_DIR / 'run.py')]


# ---------------------------------------------------------------------------------------------
# Languages: every text is written in English with the Russian next to it; the other
# languages are in bbport_lang.py, keyed by the English text.

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bbport_lang  # noqa: E402

LANG = 'en'


WARN = '  ⚠'  # marks a risky choice; the text before it is translated as usual


def _(en, ru=None):
    if en.endswith(WARN):
        return _(en[:-len(WARN)], ru and ru.removesuffix(WARN)) + WARN
    if LANG == 'ru':
        return ru or bbport_lang.table('ru').get(en) or en
    return bbport_lang.table(LANG).get(en) or en


def windows_language():
    try:
        primary = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3ff
    except (AttributeError, OSError):
        return 'en'
    return bbport_lang.WINDOWS_LANGUAGES.get(primary, 'en')


# ---------------------------------------------------------------------------------------------
# Settings. bbport.ini keys (the game reads them, the in-game menu edits them) and the
# launcher's own settings.json (passed to run.py as environment variables).

EFFECTS = [
    ('effect_chromatic_aberration', ('Chromatic aberration', 'Хроматическая аберрация'), True),
    ('effect_dof', ('Depth of field', 'Глубина резкости (DoF)'), True),
    ('effect_motion_blur', ('Motion blur', 'Размытие в движении'), True),
    ('effect_ssao', ('Ambient occlusion (SSAO)', 'Затенение SSAO'), True),
    ('effect_game_aa', ("The game's own anti-aliasing", 'Собственное сглаживание игры'), True),
    ('effect_dynamic_shadows', ('Shadows of dynamic lights', 'Тени от динамических источников'), True),
    ('effect_ssr', ('Screen-space reflections (not in the original)', 'Отражения SSR (не было в игре)'), False),
]
EXTRAS = [
    ('skip_intro', ('Skip the intro logos and movie', 'Пропуск заставок при запуске'), False),
    ('debug_camera', ('Free camera (hold Cross + L3; keyboard Space + Z)', 'Свободная камера (Cross + L3 / Space + Z)'), False),
    ('debug_menu', ('Game debug menu (left touchpad / Tab; needs the debug fonts)',
                    'Debug menu (левый touchpad / Tab; нужны шрифты)'), False),
]
# Cheats and gameplay tweaks: game patches for 1.09 (patches.py EFFECTS), off by default.
CHEATS = [
    ('cheat_no_death', ('Never die (health stops at 1 HP)', 'Бессмертие (здоровье не ниже 1 HP)'), False),
    ('cheat_stealth', ('Enemies do not see you (unless attacked)', 'Враги не видят вас (пока не атакованы)'), False),
    ('cheat_silent', ('Enemies do not hear you', 'Враги не слышат вас'), False),
    ('cheat_rally_no_decay', ('Rally never fades', 'Rally не угасает'), False),
    ('cheat_enemy_control', ('Control the targeted enemy (R3; L3 to go back; not with the free camera)',
                             'Управление выбранным врагом (R3; L3 — назад; не вместе со свободной камерой)'), False),
]
TWEAKS = [
    ('tweak_no_rally', ('No Rally (hits do not give health back)', 'Без Rally (удары не возвращают здоровье)'), False),
    ('tweak_camera_distance', ('Camera further from the character', 'Камера дальше от персонажа'), False),
    ('tweak_no_camera_rotation', ('No camera auto-rotation while moving', 'Без автоповорота камеры при движении'), False),
    ('tweak_easy_run', ('Run with less stick tilt (about 70%)', 'Бег при меньшем наклоне стика (около 70%)'), False),
    ('tweak_ragdoll', ('Dark Souls-style ragdoll physics (corpses fly further)',
                       'Физика тел как в Dark Souls (тела отлетают дальше)'), False),
]
INI_FLAGS = {'sharpen', 'object_motion', 'show_fps', *(k for k, _t, _o in EFFECTS + EXTRAS + CHEATS + TWEAKS)}
INI_DEFAULTS = {'upscaler': 'fsr4', 'preset': '1', 'sharpen': '1', 'sharpness': '0.50',
                'object_motion': '1', 'show_fps': '1', 'output_res': '1920x1080', 'model_lod': '0',
                'live_resolution': 'auto',
                **{key: '1' if on else '0' for key, _t, on in EFFECTS + EXTRAS + CHEATS + TWEAKS}}
APP_DEFAULTS = {'ui_language': '', 'game_dir': str(PORT_DIR.parent / 'CUSA03173'), 'user_dir': '',
                'mods_dir': '', 'mods_enabled': True, 'patches_dir': '', 'language': '1',
                'player_name': '', 'fullscreen': False, 'window_mode': '', 'hdr': False, 'present_mode': 'Mailbox',
                'fps_mode': 'uncap', 'frame_cap': '', 'real_fps_limit': '-1', 'draw_pipe': '', 'readbacks': '',
                'frames_ahead': '', 'frame_stats': False, 'gpu_profile': False,
                'vk_validation': False, 'developer_profile': False, 'extra_env': '', 'close_on_play': False,
                'check_updates': True, 'online': False, 'online_server': 'srv.shadps4.net:31313',
                'online_webapi': '', 'online_npid': '', 'online_password': '', 'online_upnp': True,
                'online_community': COMMUNITY_SERVER, 'save_auto_backup': True, 'save_backup_retention': 10}
MENU_DEFAULTS = {'menu_language': 'en', 'window_mode': 'launcher', 'borderless_vsync': '0',
                 'dlss_preset': 'default', 'xess_preset': '2', 'show_fps': '1', 'show_dlss_preset': '0',
                 'show_resolution': '0', 'show_fg_preset': '0', 'show_frame_generation': '0', 'show_latency': '0', 'show_frametime_graph': '0',
                 'background_mode': 'run', 'frame_generation': 'off', 'limit_generated_fps': '0', 'generated_fps_limit': '144', 'reflex': 'off', 'nvidia_generated_frames': '1', 'nvidia_fg_preset': 'default',
                 'amd_antilag': '0', 'real_fps_limit': '-1', 'nvidia_fg_mod': '0',
                 'cheat_damage': '1', 'cheat_incoming': '1', 'cheat_echoes': '1', 'cheat_movement': '1',
                 'cheat_infinite_stamina': '0', 'cheat_no_consume': '0', 'cheat_no_fall_damage': '0'}
MENU_FLAGS = {'borderless_vsync', 'show_fps', 'show_dlss_preset', 'show_resolution',
              'show_frame_generation', 'show_fg_preset', 'show_latency', 'show_frametime_graph', 'nvidia_fg_mod',
              'cheat_infinite_stamina', 'cheat_no_consume', 'cheat_no_fall_damage', 'limit_generated_fps', 'amd_antilag'}
CHEAT_MULTIPLIERS = [('1', ('Off', 'Выключено'))] + [(str(n), (f'x{n}', f'x{n}')) for n in (2, 4, 8, 16)]
MOVEMENT_MULTIPLIERS = [CHEAT_MULTIPLIERS[0], ('1.5', ('x1.5', 'x1.5'))] + CHEAT_MULTIPLIERS[1:]
FRAME_GENERATORS = [('off', ('Off', 'Выключено')), ('fsr', ('FSR Frame Generation (2x)', 'FSR Frame Generation (2x)')),
                    ('nvidia', ('NVIDIA DLSS Frame Generation / MFG', 'NVIDIA DLSS Frame Generation / MFG'))]
REFLEX_MODES = [('off', ('Off', 'Выключено')), ('on', ('On', 'Включено')), ('boost', ('On + Boost', 'Включено + Boost'))]
NVIDIA_MULTIPLIERS = [(str(n-1), (f'{n}x', f'{n}x')) for n in range(2, 7)]
NVIDIA_FG_PRESETS = [('default', ('Default (NVIDIA settings)', 'По настройкам NVIDIA')),
                     ('a', ('A', 'A')), ('b', ('B', 'B')),
                     ('c', ('C (Performance / beta)', 'C (производительность / бета)'))]
BACKGROUND_MODES = [('run', ('Keep running', 'Продолжать работу')),
                    ('pause', ('Pause game and rendering', 'Приостановить игру и рендер')),
                    ('30', ('Limit to 30 FPS', 'Лимит 30 FPS')),
                    ('60', ('Limit to 60 FPS', 'Лимит 60 FPS'))]
DLSS_PRESETS = [('default', ('Default (driver)', 'По умолчанию (драйвер)')),
                ('e', ('E (CNN / legacy)', 'E (CNN / устаревший)')),
                ('f', ('F (CNN / legacy)', 'F (CNN / устаревший)')),
                ('j', ('J (Transformer 1st gen)', 'J (Transformer 1-го пок.)')),
                ('k', ('K (Transformer 1st gen)', 'K (Transformer 1-го пок.)')),
                ('m', ('M (Transformer 2nd gen)', 'M (Transformer 2-го пок.)')),
                ('l', ('L (Transformer 2nd gen)', 'L (Transformer 2-го пок.)'))]
WINDOW_MODES = [('windowed', ('Windowed', 'Оконный')),
                ('borderless', ('Borderless fullscreen', 'Без рамки на весь экран')),
                ('fullscreen', ('Fullscreen (driver default)', 'Полный экран (настройка драйвера)'))]
MENU_LANGUAGES = [('en', ('English',)), ('ru', ('Русский',))]

UPSCALERS = [('dlss', ('DLSS (NVIDIA GeForce RTX)',)),
             ('xess', ('XeSS (Intel / compatible GPUs)', 'XeSS (Intel / совместимые GPU)')),
             ('fsr4', ('FSR 4 (best quality)', 'FSR 4 (лучшее качество)')),
             ('fsr411', ('FSR 4.1.1 (needs fsr4_411 assets)', 'FSR 4.1.1 (нужны ассеты fsr4_411)')),
             ('fsr3', ('FSR 3.1 (every GPU)', 'FSR 3.1 (любая видеокарта)')),
             ('taa', ('TAA (native resolution anti-aliasing)', 'TAA (нативное сглаживание)')),
             ('off', ('Off', 'Выключен'))]
PRESETS = [('0', ('Native AA (×1.0)',)), ('1', ('Quality (×1.5)',)), ('2', ('Balanced (×1.7)',)),
           ('3', ('Performance (×2)',)), ('4', ('Ultra Performance (×3)',))]
XESS_PRESETS = [('0', ('Native AA (×1.0)',)), ('1', ('Ultra Quality Plus (×1.3)',)),
                ('2', ('Ultra Quality (×1.5)',)), ('3', ('Quality (×1.7)',)),
                ('4', ('Balanced (×2)',)), ('5', ('Performance (×2.3)',)),
                ('6', ('Ultra Performance (×3)',))]
LEGACY_XESS_PRESETS = ('0', '2', '3', '4', '6')
OUTPUTS = [('1280x720', ('1280 × 720 (Steam Deck)',)), ('1920x1080', ('1920 × 1080',)),
           ('2560x1440', ('2560 × 1440',)), ('3840x2160', ('3840 × 2160 (4K)',))]
LIVE = [('auto', ('Auto (by graphics card)', 'Авто (по видеокарте)')), ('0', ('Off (faster)', 'Выключена (быстрее)')),
        ('1', ('On (change without restarting)', 'Включена (без перезапуска)'))]
LODS = [('0', ('As in the game', 'Как в игре')), ('-2', ('Highest (−2)', 'Максимальная (−2)')),
        ('1', ('Lower (1)', 'Ниже (1)')), ('2', ('Lowest (2)', 'Минимальная (2)'))]
FPS_MODES = [('uncap', ('Unlocked (frame-time patch)', 'Без ограничения (патч)')), ('60', ('60 FPS',)),
             ('75', ('75 FPS',)),
             ('90', ('90 FPS',)), ('30', ('30 FPS (as on PS4)', '30 FPS (как на PS4)'))]
PRESENT_MODES = [('Mailbox', ('Mailbox (low latency, no tearing)', 'Mailbox (без разрывов)')),
                 ('Fifo', ('FIFO (VSync)',)), ('FifoRelaxed', ('FIFO Relaxed',)),
                 ('Immediate', ('Immediate (tearing)', 'Immediate (с разрывами)'))]
LANGUAGES = [('1', ('English', 'Английский')), ('8', ('Russian', 'Русский')), ('0', ('Japanese', 'Японский')),
             ('2', ('French', 'Французский')), ('3', ('Spanish', 'Испанский')), ('4', ('German', 'Немецкий')),
             ('5', ('Italian', 'Итальянский'))]
DRAW_PIPE = [('', ('Auto (8+ threads)', 'Авто (8+ потоков)')), ('1', ('On', 'Включён')),
             ('0', ('Off (more stable)', 'Выключен (стабильнее)'))]
READBACKS = [('', ('Relaxed (default)', 'Relaxed (по умолчанию)')), ('0', ('Off', 'Выключены')),
             ('2', ('Precise',))]
# Frame cap of the unlocked mode (BB_FPS_LIMIT). '' leaves the port's own: the display refresh,
# at most 120, because the game's movement timing breaks above about 120 FPS.
FRAME_CAPS = [('-1', ('Auto: display refresh, max 120 (recommended)', 'Авто: частота монитора, макс. 120 (рекомендуется)')),
              ('30', ('30',)), ('60', ('60',)), ('75', ('75',)), ('90', ('90',)), ('120', ('120',)), ('144', ('144  ⚠',)), ('165', ('165  ⚠',)),
              ('240', ('240  ⚠',)), ('0', ('No limit  ⚠', 'Без ограничения  ⚠'))]
FRAMES_AHEAD = [('', ('1 (default)', '1 (по умолчанию)')), ('2', ('2',)), ('0', ('Unbounded', 'Без ограничения'))]
UI_LANGUAGES = bbport_lang.LANGUAGE_NAMES

FSR4_COMMIT = 'ae8d628fae208813172446d1e49ed94150b04658'
FSR4_BASE = f'https://raw.githubusercontent.com/FireBurn/Q2RTX/{FSR4_COMMIT}/baseq2/fsr4_shaders'


def fsr4_files():
    """The FSR 4 v07 asset set of tools/fetch_fsr4_assets.sh (1080 and 2160 tiers)."""
    files = ['LICENSE-FSR4-v07.txt', 'rcas.spv', 'spd_auto_exposure.spv']
    for model in ('native', 'quality', 'balanced', 'performance', 'ultraperf', 'drs'):
        files += [f'fsr4_model_v07_i8_{model}_initializers.bin', f'fsr4_model_v07_i8_{model}_pre_weights.bin',
                  f'fsr4_model_v07_i8_{model}_shader_manifest.json']
        for tier in ('1080', '2160'):
            files += [f'fsr4_model_v07_i8_{model}_{tier}_pre.spv', f'fsr4_model_v07_i8_{model}_{tier}_post.spv']
            files += [f'fsr4_model_v07_i8_{model}_{tier}_pass{n}.spv' for n in range(1, 13)]
    return files


def fsr4_missing():
    folder = PORT_DIR / 'fsr4_shaders'
    return [name for name in fsr4_files() if not (folder / name).is_file() or not (folder / name).stat().st_size]


def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def ini_path():
    return Path(os.environ.get('BB_CONFIG', DATA_DIR / 'bbport.ini'))


def menu_path():
    return ini_path().with_suffix('.menu.ini')


def load_menu():
    values = dict(MENU_DEFAULTS)
    # Preserve installations that kept their FPS counter preference in bbport.ini.
    ini, _lines = load_ini()
    values['show_fps'] = ini.get('show_fps', '1')
    try:
        legacy = max(0, min(4, int(ini.get('preset', '0'))))
    except ValueError:
        legacy = 0
    values['xess_preset'] = ini.get('xess_preset', LEGACY_XESS_PRESETS[legacy])
    if values['xess_preset'] not in dict(XESS_PRESETS):
        values['xess_preset'] = LEGACY_XESS_PRESETS[legacy]
    try:
        lines = menu_path().read_text(encoding='utf-8').splitlines()
    except OSError:
        lines = []
    if not any(line.strip().startswith('real_fps_limit=') for line in lines):
        previous = load_json(CONFIG_FILE, {})
        values['real_fps_limit'] = '75' if previous.get('fps_mode') == '75' else previous.get('frame_cap') or '-1'
    for line in lines:
        if '=' in line and not line.lstrip().startswith('#'):
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
    preset = dict(zip(('0', '5', '6', '10', '11', '12', '13'),
                      ('default', 'e', 'f', 'j', 'k', 'l', 'm'))).get(preset, preset)
    values['dlss_preset'] = preset if preset in dict(DLSS_PRESETS) else 'default'
    return values


def launcher_window_mode(settings):
    mode = settings.get('window_mode')
    return mode if mode in ('windowed', 'borderless', 'fullscreen') else \
        'fullscreen' if settings.get('fullscreen') else 'windowed'


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
    written, output = set(), []
    for line in lines:
        key = line.split('=', 1)[0].strip() if '=' in line and not line.lstrip().startswith('#') else None
        if key in changes:
            output.append(f'{key}={changes[key]}')
            written.add(key)
        else:
            output.append(line)
    output += [f'{key}={value}' for key, value in changes.items() if key not in written]
    temporary = menu_path().with_suffix('.menu.ini.launcher-tmp')
    temporary.write_text('\n'.join(output) + '\n', encoding='utf-8')
    os.replace(temporary, menu_path())


def load_ini():
    values, lines = dict(INI_DEFAULTS), []
    try:
        lines = ini_path().read_text(encoding='utf-8').splitlines()
    except OSError:
        pass
    for line in lines:
        if '=' in line and not line.lstrip().startswith('#'):
            key, value = line.split('=', 1)
            values[key.strip()] = value.strip()
    return values, lines


def save_ini(values, lines):
    """Rewrites the edited keys in place, appends missing ones, keeps comments and other keys."""
    written, out = set(), []
    for line in lines:
        if '=' in line and not line.lstrip().startswith('#'):
            key = line.split('=', 1)[0].strip()
            if key in values:
                out.append(f'{key}={values[key]}')
                written.add(key)
                continue
        out.append(line)
    if not lines:
        out.append('# bbport settings (in-game menu: Insert / L3+R3)')
    out += [f'{key}={value}' for key, value in values.items() if key not in written]
    ini_path().write_text('\n'.join(out) + '\n', encoding='utf-8')


def game_info(folder):
    """(title, app version) of a game folder, or None without eboot.bin."""
    folder = Path(folder or '.')
    if not (folder / 'eboot.bin').is_file():
        return None
    try:
        from prepare import sfo
        values = sfo((folder / 'sce_sys/param.sfo').read_bytes())
        return values.get('TITLE', 'Bloodborne').replace('™', '').strip(), values.get('APP_VER', '?')
    except (OSError, ValueError, ImportError):
        return 'Bloodborne', '?'


def webapi_address(server):
    """The shadNet WebAPI of a server address host:port (the server's default port 31315)."""
    host = server.rsplit(':', 1)[0] if server.count(':') == 1 else server
    return f'http://{host}:31315'


def community_address(value):
    """The game server (messages, bloodstains, ghosts) as https://host, The Hunter's Dream by default."""
    value = str(value).strip() or COMMUNITY_SERVER
    scheme, _sep, rest = value.rpartition('://')
    host = rest.split('/')[0].split(':')[0]  # the game picks the ports (20443, 18671)
    return f'{scheme or "https"}://{host}'


def webapi_setting(s):
    """The WebAPI field, unless it holds the game server's address (a common mix-up): then the
    co-op server's own WebAPI is used."""
    webapi = str(s['online_webapi']).strip()
    community_host = community_address(s['online_community']).split('://', 1)[1].split(':')[0]
    if webapi and community_host in webapi:
        webapi = ''
    return webapi or webapi_address(str(s['online_server']).strip() or APP_DEFAULTS['online_server'])


def server_check(server, webapi, community):
    """A line about each online address: reachable, or why not (runs off the Tk thread)."""
    import socket
    lines = []
    try:
        with urllib.request.urlopen(community + ':20443/bb-eu/ss.info', timeout=6) as reply:
            reply.read(64)
        lines.append(_('Game server {0}: reachable').format(community))
    except (OSError, ValueError) as error:
        lines.append(_('Game server {0}: not reachable ({1})').format(community, error))
    host, _sep, port = server.rpartition(':')
    try:
        socket.create_connection((host or server, int(port or 31313)), timeout=4).close()
        lines.append(_('Server {0}: reachable').format(server))
    except (OSError, ValueError) as error:
        lines.append(_('Server {0}: not reachable ({1})').format(server, error))
    try:
        with urllib.request.urlopen(webapi.rstrip('/') + '/status', timeout=4) as reply:
            ok = b'"ok":true' in reply.read(512).replace(b' ', b'')
        lines.append(_('WebAPI {0}: reachable').format(webapi) if ok else
                     _('WebAPI {0}: answered, but it is not a shadNet server').format(webapi))
    except (OSError, ValueError) as error:
        lines.append(_('WebAPI {0}: not reachable ({1})').format(webapi, error))
    return '\n'.join(lines)


def game_environment(s):
    env = dict(os.environ)
    env['BB_GAME_DIR'] = s['game_dir']
    if s['user_dir']:
        env['BB_USER_DIR'] = s['user_dir']
    env['BB_MODS_DIR'] = s['mods_dir'] or str(DATA_DIR / 'mods')
    env['BB_MODS_CONFIG'] = str(DATA_DIR / 'mods.json')
    env['BB_MODS_ENABLED'] = '1' if s['mods_enabled'] else '0'
    env['BB_PATCHES_DIR'] = s['patches_dir'] or str(DATA_DIR / 'patches')
    env['BB_PATCHES_CONFIG'] = str(DATA_DIR / 'patches.json')
    env['BB_LANGUAGE'] = s['language']
    if str(s['player_name']).strip():
        env['BB_USER_NAME'] = str(s['player_name']).strip()
    env['BB_FULLSCREEN'] = '1' if s['fullscreen'] else '0'
    env['BB_LAUNCHER_WINDOW_MODE'] = launcher_window_mode(s)
    env['BB_PRESENT_MODE'] = s['present_mode']
    env['BB_SAVE_AUTO_BACKUP'] = '1' if s.get('save_auto_backup', True) else '0'
    env['BB_SAVE_BACKUP_RETENTION'] = str(s.get('save_backup_retention', 10))
    if s['hdr']:
        env['BB_HDR'] = '1'
    # 75 uses the variable frame-time patch, not a fixed 60/90 timing patch.
    env['BB_FPS'] = 'uncap' if s['fps_mode'] == '75' else s['fps_mode']
    real_cap = str(s.get('real_fps_limit', '-1'))
    if real_cap.isdecimal() and (real_cap == '0' or 30 <= int(real_cap) <= 1000):
        env['BB_FPS_LIMIT'] = real_cap
    elif s['fps_mode'] == '75':
        env['BB_FPS_LIMIT'] = '75'
    elif s.get('frame_cap', ''):
        env['BB_FPS_LIMIT'] = s['frame_cap']
    for key, name in (('draw_pipe', 'BB_DRAW_PIPE'), ('readbacks', 'BB_READBACKS'), ('frames_ahead', 'BB_FRAMES_AHEAD')):
        if s[key]:
            env[name] = s[key]
    for key, name in (('frame_stats', 'BB_FRAME_STATS'), ('gpu_profile', 'BB_GPU_PROFILE'),
                      ('vk_validation', 'BB_VK_VALIDATION')):
        if s[key]:
            env[name] = '1'
    for item in str(s['extra_env']).split():
        if '=' in item:
            key, value = item.split('=', 1)
            env[key] = value
    if s.get('online'):
        server = str(s['online_server']).strip() or APP_DEFAULTS['online_server']
        env['BB_ONLINE'] = '1'
        env['BB_SHADNET_SERVER'] = server
        env['BB_SHADNET_WEBAPI'] = webapi_setting(s)
        env['BB_SHADNET_NPID'] = str(s['online_npid']).strip()
        env['BB_SHADNET_PASSWORD'] = str(s['online_password'])
        env['BB_UPNP'] = '1' if s['online_upnp'] else '0'
        env['BB_COMMUNITY_SERVER'] = community_address(s['online_community'])
    env['PYTHONUNBUFFERED'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    if s.get('_geometry_diagnostic') in ('serial', 'capture'):
        # One comparison run, after saved/extra environment settings. Do not persist
        # these overrides: the normal launch must retain the user's renderer choices.
        env.update(BB_DRAW_PIPE='0', BB_PREP_WORKERS='0', BB_VK_RECORD_THREAD='0', BB_COPY_THREADS='0')
    if s.get('_nvidia_diagnostic'):
        env['BB_FG_GENERATED_ONLY'] = '1' if s['_nvidia_diagnostic'] == 'generated-only' else '0'
    return env


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
        root = Path(settings.get('user_dir') or DATA_DIR / 'user') / 'diagnostics'
        root.mkdir(parents=True, exist_ok=True)
        self.directory = Path(tempfile.mkdtemp(prefix=time.strftime('%Y%m%d-%H%M%S-'), dir=root))
        # Deliberately omit identity, credentials, arbitrary environment values and paths.
        keys = ('window_mode', 'fullscreen', 'hdr', 'present_mode', 'fps_mode', 'frame_cap',
                'frames_ahead', 'draw_pipe', 'readbacks', 'vk_validation')
        system = {'system': sys.platform, 'architecture_bits': ctypes.sizeof(ctypes.c_void_p)*8}
        if hasattr(sys, 'getwindowsversion'):
            system['windows_version'] = list(sys.getwindowsversion()[:3])
        self.metadata = {'revision': VERSION, 'platform': system,
                         'started': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                         'settings': {key: settings.get(key) for key in keys},
                         'ini': load_ini()[0], 'menu_at_start': menu_values(settings),
                         'status': 'running'}
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
            env.update(BB_FRAME_STATS='1', BB_GPU_PROFILE='1',
                       BB_DIAGNOSTICS_DIR=str(self.directory.resolve()))
            if self.metadata.get('nvidia_diagnostic') or self.metadata.get('traversal_diagnostic'):
                # Observe short CPU operations and their actual execution thread.
                # The old GPU profiler ends render passes and can wait for queries:
                # keep that separate from this reproduction of traversal pacing.
                env['BB_HITCH_TRACE'] = '1'
                env['BB_HITCH_TRACE_PATH'] = str((self.directory / 'cpu-timeline.jsonl').resolve())
                env.pop('BB_GPU_PROFILE', None)
                self.metadata['cpu_hitch_trace'] = {
                    'enabled': True, 'ring_events': 65536,
                    'gpu_timestamp_profiler': False,
                    'normal_renderer_preserved': True,
                    'causal_timeline': True, 'timeline_maximum_bytes': 16 * 1024 * 1024,
                    'interpretation': 'CPU spans are inclusive and may overlap; they are not GPU durations.'}
                self.record('Traversal CPU trace and bounded dependency timeline active with your current FG setting. '
                    'Reproduce the hitch and close the game. No key press is required for the log archive.\n')
            if self.metadata.get('nvidia_diagnostic'):
                captures = self.directory / 'fg-inputs'
                captures.mkdir()
                env.update(BB_FG_CAPTURE_TRIGGER=str((self.directory / 'fg-capture.trigger').resolve()),
                           BB_FG_CAPTURE_DIR=str(captures.resolve()))
                self.metadata['frame_capture'] = {'key': 'F8', 'requested_frames': 4,
                    'position': 'nvidia_tagged_inputs', 'maximum_raw_bytes': 256 * 1024 * 1024,
                    'normal_renderer_preserved': True}
                self.record('NVIDIA FG diagnostic: ' + self.metadata['nvidia_diagnostic'] + '\n'
                    'Keep NVIDIA FG enabled. Press F8 while the assets flash, then close the game. '
                    'The capture includes tagged depth/motion/constants and the real backbuffer; '
                    'it does not capture NVIDIA\'s internal generated image. Readbacks can affect timing. '
                    'CPU flight recording is active; reproduce the traversal hitch before pressing F8.\n')
            if self.metadata.get('geometry_diagnostic') == 'capture':
                captures = self.directory / 'frames'
                captures.mkdir()
                env.update(BB_GEOMETRY_CAPTURE='1', BB_DUMP_FRAMES='8', BB_DUMP_POLL_FRAMES='1',
                           BB_DUMP_TRIGGER=str((self.directory / 'capture.trigger').resolve()),
                           BB_DUMP_DIR=str(captures.resolve()),
                           BB_CAPTURE_TRIGGER=str((self.directory / 'passes.trigger').resolve()),
                           BB_CAPTURE_DIR=str((self.directory / 'passes').resolve()))
                (self.directory / 'passes').mkdir()
                self.record('Frame capture ready: press F8 when assets flash, then close the game. '
                            'This records eight scene-input/output frames before Frame Generation.\n')
                self.metadata['frame_capture'] = {'key': 'F8', 'requested_frames': 8,
                                                  'position': 'before_frame_generation'}
            keys = ('BB_DRAW_PIPE', 'BB_PREP_WORKERS', 'BB_VK_RECORD_THREAD', 'BB_COPY_THREADS',
                    'BB_FRAME_STATS', 'BB_GPU_PROFILE', 'BB_PIPE_VERIFY', 'BB_GEOMETRY_CAPTURE',
                    'BB_DUMP_FRAMES', 'BB_DUMP_POLL_FRAMES', 'BB_PIPELINE_CACHE',
                    'BB_OBJECT_MOTION', 'BB_UPSCALER', 'BB_READBACKS', 'BB_FG_GENERATED_ONLY', 'BB_HITCH_TRACE')
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
            self.log.write(f'[{time.monotonic()-self.started:10.3f}s] {text}')

    def finish(self, code):
        if self.directory:
            self.metadata.update(status='exited', exit_code=code,
                                 duration_seconds=round(time.monotonic()-self.started, 3),
                                 menu_at_exit=load_menu())
            self.record(f'Process exited with code {code}\n')
            self.write_metadata()
            self.log.close()
            if self.metadata.get('geometry_diagnostic') == 'capture':
                self.archive_capture()
            if self.metadata.get('nvidia_diagnostic') or self.metadata.get('traversal_diagnostic'):
                self.archive_fg_capture()

    def archive_fg_capture(self):
        from fg_diagnostic import export_capture
        result = export_capture(self.directory, PORT_DIR, self.metadata)
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
            self.metadata['frame_capture'].update(
                status='captured' if pairs == 8 else 'incomplete',
                raw_files=len(frames), paired_frames=pairs)
            self.write_metadata()
            with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as bundle:
                for path in (self.directory / 'session.log', self.directory / 'session.json', *frames,
                             *sorted((self.directory / 'passes').glob('*'))):
                    if path.is_file():
                        bundle.write(path, path.relative_to(self.directory))
            temporary.replace(archive)
            print(f'Flashing diagnostic saved: {archive}', flush=True)
        except (OSError, zipfile.BadZipFile) as error:
            temporary.unlink(missing_ok=True)
            self.metadata['frame_capture'].update(status='archive_failed', error_type=type(error).__name__)
            self.write_metadata()
            print(f'Cannot package the capture ({error}); the individual files are in {self.directory}.', flush=True)


def read_game_output(process, settings, diagnostic, emit):
    """Shared reader for the windowed launcher and --play; no UI-thread work."""
    log = None
    try:
        log_dir = Path(settings.get('user_dir') or DATA_DIR / 'user')
        log_dir.mkdir(parents=True, exist_ok=True)
        log = open(log_dir / 'last_run.log', 'w', encoding='utf-8', buffering=1)
        # Keep current-run identity/settings in the ordinary log as well. An
        # older opt-in diagnostics folder must not be mistaken for this run.
        log.write(f'Bloodborne launcher {VERSION} | {time.strftime("%Y-%m-%dT%H:%M:%S%z")}\n')
        keys = ('window_mode', 'hdr', 'present_mode', 'fps_mode', 'frame_cap',
                'frames_ahead', 'draw_pipe', 'readbacks')
        log.write('Launch settings: ' + json.dumps({k: settings.get(k) for k in keys}) + '\n')
        log.write('Requested graphics: ' + json.dumps(menu_values(settings), ensure_ascii=False) + '\n')
    except OSError:
        pass
    try:
        for raw in iter(process.stdout.readline, b''):
            text = raw.decode('utf-8', errors='replace').replace('\r\n', '\n')
            emit(text)
            if log:
                log.write(text)
            diagnostic.record(text)
        code = process.wait()
        if log:
            log.write(f'\nProcess exited with code {code}\n')
        diagnostic.finish(code)
        return code
    finally:
        if log:
            log.close()


# ---------------------------------------------------------------------------------------------
# The window.

BG, PANEL, CARD, LINE = '#0c0f12', '#14181c', '#1d2227', '#414039'
TEXT, MUTED, GOLD, BLOOD, BLOOD_HI = '#efe6d8', '#afa69a', '#d6c1a1', '#51332e', '#71483e'


class Launcher:
    def __init__(self, root, tk, ttk, filedialog, messagebox):
        self.tk, self.ttk, self.filedialog, self.messagebox = tk, ttk, filedialog, messagebox
        self.root = root
        self.ui_closed = False
        def closing(event):
            if event.widget is root:
                self.ui_closed = True
        root.bind('<Destroy>', closing, add='+')
        self.app = {**APP_DEFAULTS, **load_json(CONFIG_FILE, {})}
        self.ini, self.ini_lines = load_ini()
        self.menu = menu_values(self.app)
        self.menu_baseline = dict(self.menu)
        self.vars = {}
        self.process = self.job = None
        self.downloading = False
        self.output = queue.Queue()
        self.gpu_text = _('• Checking the graphics card…', '• Проверка видеокарты…')
        self.banner_source = self.banner_image = None
        self.ui_calls = queue.Queue()  # work for the Tk thread from helper threads
        self.mod_order, self.mod_vars, self.patch_vars = [], {}, {}
        root.title('Bloodborne: The Crowned Workshop — TatsunaKyo')
        root.configure(bg=BG)
        self.dpi = root.winfo_fpixels('1i') / 96.0
        root.geometry(f'{self.px(1120)}x{self.px(740)}')
        root.minsize(self.px(980), self.px(660))
        self.set_icon()
        self.style()
        self.build()
        self.show('play')
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(100, self.drain_output)
        threading.Thread(target=self.detect_gpu, daemon=True).start()
        if self.app.get('check_updates', True) and not COOP_TEST:
            threading.Thread(target=self.check_update, daemon=True).start()

    def px(self, size):
        return int(size * self.dpi)

    def set_icon(self):
        for icon in (PORT_DIR / 'docs/assets/crowned-workshop.ico', PORT_DIR / 'launcher/bloodborne.ico'):
            try:
                self.root.iconbitmap(default=str(icon))
                return
            except self.tk.TclError:
                pass
        for icon in (PORT_DIR / 'docs/assets/crowned-workshop-icon-64.png',
                     PORT_DIR / 'launcher/bloodborne.png', Path(self.app['game_dir']) / 'sce_sys' / 'icon0.png'):
            try:
                self.icon = self.tk.PhotoImage(file=str(icon))
                if self.icon.width() > 128:
                    self.icon = self.icon.subsample(self.icon.width() // 64)
                self.root.iconphoto(True, self.icon)
                return
            except (self.tk.TclError, OSError):
                continue

    # ---- look --------------------------------------------------------------------------------
    def check_images(self):
        """16 px (DPI-scaled) check box images: the clam theme draws a cross."""
        tk = self.tk
        n = max(14, int(16 * self.dpi))
        images = []
        for checked in (False, True):
            image = tk.PhotoImage(width=n + self.px(8), height=n)  # unset pixels stay transparent
            fill = BLOOD if checked else CARD
            image.put(GOLD if checked else '#5a4c40', to=(0, 0, n, n))
            image.put(fill, to=(1, 1, n - 1, n - 1))
            if checked:
                # Tick: down from (0.22n, 0.52n) to (0.42n, 0.72n), up to (0.78n, 0.30n).
                pts = []
                x0, y0, x1, y1, x2, y2 = .22 * n, .52 * n, .42 * n, .72 * n, .78 * n, .28 * n
                for t in range(40):
                    f = t / 39
                    pts.append((x0 + (x1 - x0) * f, y0 + (y1 - y0) * f))
                    pts.append((x1 + (x2 - x1) * f, y1 + (y2 - y1) * f))
                width = max(1, round(n / 9))
                for x, y in pts:
                    image.put('#f4ece0', to=(int(x), int(y), int(x) + width, int(y) + width))
            images.append(image)
        self.check_off, self.check_on = images

    def style(self):
        ttk = self.ttk
        s = ttk.Style(self.root)
        s.theme_use('clam')
        self.check_images()
        s.element_create('Bb.indicator', 'image', self.check_off, ('selected', self.check_on), sticky='')
        s.layout('TCheckbutton', [('Checkbutton.padding', {'sticky': 'nswe', 'children': [
            ('Bb.indicator', {'side': 'left', 'sticky': ''}),
            ('Checkbutton.focus', {'side': 'left', 'sticky': 'w', 'children': [
                ('Checkbutton.label', {'sticky': 'nswe'})]})]})])
        base = ('Segoe UI', 10)
        self.root.option_add('*TCombobox*Listbox.background', CARD)
        self.root.option_add('*TCombobox*Listbox.foreground', TEXT)
        self.root.option_add('*TCombobox*Listbox.selectBackground', BLOOD)
        self.root.option_add('*TCombobox*Listbox.font', base)
        s.configure('.', background=PANEL, foreground=TEXT, fieldbackground=CARD, bordercolor=LINE,
                    lightcolor=LINE, darkcolor=LINE, troughcolor=CARD, focuscolor=GOLD, font=base)
        s.configure('TFrame', background=PANEL)
        s.configure('Workshop.TFrame', background=CARD, borderwidth=1, relief='solid')
        s.configure('Workshop.TLabel', background=CARD, foreground=TEXT)
        s.configure('Settings.TLabelframe', background=PANEL, bordercolor=LINE, relief='solid', borderwidth=1)
        s.configure('Settings.TLabelframe.Label', background=PANEL, foreground=GOLD, font=('Georgia', 12))
        s.configure('WorkshopSection.TLabel', background=CARD, foreground=GOLD, font=('Georgia', 13))
        s.configure('TLabel', background=PANEL, foreground=TEXT)
        s.configure('Muted.TLabel', background=PANEL, foreground=MUTED, font=('Segoe UI', 9))
        s.configure('Section.TLabel', background=PANEL, foreground=GOLD, font=('Georgia', 13))
        s.configure('TCheckbutton', background=PANEL, foreground=TEXT, padding=(0, 3))
        s.map('TCheckbutton', background=[('active', PANEL)], foreground=[('disabled', MUTED)])
        s.configure('Warning.TLabel', background='#2a1d12', foreground='#e3b25a', padding=(10, 6))
        s.configure('TCombobox', arrowcolor=GOLD, foreground=TEXT, padding=4)
        s.map('TCombobox', fieldbackground=[('readonly', CARD)], foreground=[('readonly', TEXT)],
              selectbackground=[('readonly', CARD)], selectforeground=[('readonly', TEXT)])
        s.configure('TEntry', foreground=TEXT, insertcolor=TEXT, padding=4)
        s.configure('TSpinbox', foreground=TEXT, arrowcolor=GOLD, insertcolor=TEXT, padding=4)
        s.configure('TButton', background=CARD, foreground=TEXT, padding=(12, 6), borderwidth=1)
        s.map('TButton', background=[('active', LINE), ('disabled', PANEL)], foreground=[('disabled', MUTED)])
        s.configure('Play.TButton', background=GOLD, foreground=BG, font=('Georgia', 15, 'bold'),
                    padding=(36, 10), borderwidth=1)
        s.map('Play.TButton', background=[('active', '#e6d6bc'), ('disabled', CARD)],
              foreground=[('disabled', MUTED)])
        s.configure('Horizontal.TProgressbar', background=GOLD, troughcolor=CARD, bordercolor=LINE)
        s.configure('Vertical.TScrollbar', background=CARD, arrowcolor=GOLD, troughcolor=PANEL, bordercolor=PANEL)
        s.configure('Workshop.Treeview', background=CARD, fieldbackground=CARD, foreground=TEXT,
                    rowheight=self.px(24), bordercolor=LINE)
        # Override clam's light row-state map as well as its normal background.
        s.map('Workshop.Treeview', background=[('selected', BLOOD), ('!selected', CARD)],
              foreground=[('selected', TEXT), ('!selected', TEXT)])
        s.configure('Workshop.Treeview.Heading', background=PANEL, foreground=GOLD,
                    font=('Segoe UI', 10, 'bold'))

    # ---- widget helpers ----------------------------------------------------------------------
    def var(self, key, store):
        """The Tk variable of a setting (one per setting, shared by every widget that shows it)."""
        tk = self.tk
        if key not in self.vars:
            if store == 'ini':
                value = self.ini.get(key, INI_DEFAULTS[key])
                if key in INI_FLAGS:
                    v = tk.BooleanVar(value=value == '1')
                elif key == 'sharpness':
                    v = tk.DoubleVar(value=float(value or 0.5))
                else:
                    v = tk.StringVar(value=value)
            elif store == 'menu':
                value = self.menu.get(key, MENU_DEFAULTS[key])
                v = tk.BooleanVar(value=value == '1') if key in MENU_FLAGS else tk.StringVar(value=value)
            else:
                value = self.app.get(key, APP_DEFAULTS[key])
                if isinstance(APP_DEFAULTS[key], bool):
                    v = tk.BooleanVar(value=bool(value))
                else:
                    v = tk.StringVar(value=str(value))
            v.store = store
            self.vars[key] = v
        return self.vars[key]

    def track_setting(self, parent, key, widget):
        category = getattr(parent, 'settings_category', None)
        if category is not None:
            if not hasattr(self, 'setting_locations'):
                self.setting_locations = {}
            self.setting_locations.setdefault(key, []).append((category, widget))
        return widget

    def settings_section(self, parent, title):
        box = self.ttk.LabelFrame(parent, text=title, style='Settings.TLabelframe',
                                  padding=(self.px(16), self.px(12)))
        box.grid(row=self.next_row(parent), column=0, columnspan=2, sticky='ew', pady=(0, self.px(16)))
        box.columnconfigure(0, minsize=self.px(200))
        box.columnconfigure(1, weight=1)
        box.settings_category = parent.settings_category
        return box

    def choice(self, parent, key, store, options, width=38):
        """A combobox over (value, (english, russian)) pairs, kept in sync with its variable."""
        var = self.var(key, store)
        values = [v for v, _t in options]
        box = self.ttk.Combobox(parent, values=[_(*text) for _v, text in options], state='readonly', width=width)
        if var.get() not in values:
            var.set(values[0])

        def show(*_args):
            current = var.get()
            box.current(values.index(current) if current in values else 0)
        show()
        box.bind('<<ComboboxSelected>>', lambda _e: var.set(values[box.current()]))
        var.trace_add('write', show)
        return self.track_setting(parent, key, box)

    def next_row(self, parent):
        return parent.grid_size()[1]

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
        choices = [(key, ('NVIDIA DLSS FG / MFG', 'NVIDIA DLSS FG / MFG') if key == 'nvidia' else labels)
                   for key, labels in FRAME_GENERATORS] if width < 30 else FRAME_GENERATORS
        box = self.choice(parent, 'frame_generation', 'menu', choices, width=width)
        upscaler = self.var('upscaler', 'ini')
        def availability(*_args):
            box.configure(state='readonly' if upscaler.get() != 'off' else 'disabled')
        upscaler.trace_add('write', availability)
        availability()
        return box

    def fps_cap_control(self, parent, key, store, minimum, maximum, enabled_key=None,
                        options=None):
        """Exact entry and relative dragging: moving one pixel changes one FPS."""
        tk, ttk = self.tk, self.ttk
        holder = ttk.Frame(parent)
        value = self.var(key, store)
        draft = tk.StringVar()
        position = tk.DoubleVar()
        labels = {v: _(*text) for v, text in options or []}
        if options:
            labels['-1'] = _('Auto', 'Авто')
            labels['0'] = _('No cap', 'Без ограничения')
        if options:
            entry = ttk.Combobox(holder, textvariable=draft, width=19,
                                 values=list(labels.values()), state='normal')
        else:
            entry = ttk.Spinbox(holder, textvariable=draft, from_=minimum, to=maximum,
                               increment=1, width=7)
        entry.pack(side='right', padx=(10, 0))
        slider = ttk.Scale(holder, from_=minimum, to=maximum, variable=position,
                           length=self.px(160))
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
                    # Preserve the unlocked-mode Auto/No limit choices and the
                    # existing explicit caps above 120; their warning stays visible.
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
        return self.track_setting(parent, key, holder)

    def row(self, parent, title, widget, hint=None):
        ttk = self.ttk
        r = self.next_row(parent)
        label = ttk.Label(parent, text=title, wraplength=self.px(180), justify='left')
        label.grid(row=r, column=0, sticky='nw', padx=(0, 18), pady=(8, 0))
        widget.grid(row=r, column=1, sticky='w', pady=(5, 0))
        widget.row_label = label
        if hint:
            widget.row_hint = ttk.Label(parent, text=hint, style='Muted.TLabel', wraplength=self.px(410), justify='left')
            widget.row_hint.grid(row=r + 1, column=1, sticky='w', pady=(2, 2))
        return widget

    def show_row(self, widget, visible):
        for part in (widget.row_label, widget, getattr(widget, 'row_hint', None)):
            if part is not None:
                part.grid() if visible else part.grid_remove()

    def check(self, parent, key, store, title, hint=None):
        ttk = self.ttk
        r = self.next_row(parent)
        widget = ttk.Checkbutton(parent, text=title, variable=self.var(key, store))
        widget.grid(row=r, column=0, columnspan=2, sticky='w', pady=(4, 0))
        if hint:
            ttk.Label(parent, text=hint, style='Muted.TLabel', wraplength=self.px(590), justify='left').grid(
                row=r + 1, column=0, columnspan=2, sticky='w', padx=(26, 0))
        return self.track_setting(parent, key, widget)

    def note(self, parent, text, top=12):
        self.ttk.Label(parent, text=text, style='Muted.TLabel', wraplength=self.px(680), justify='left').grid(
            row=self.next_row(parent), column=0, columnspan=2, sticky='w', pady=(top, 0))

    def section(self, parent, title, top=18):
        self.ttk.Label(parent, text=title, style='Section.TLabel').grid(
            row=self.next_row(parent), column=0, columnspan=2, sticky='w', pady=(top, 2))

    def folder(self, parent, key, title, prompt, hint=None, on_change=None):
        ttk = self.ttk
        var = self.var(key, 'app')
        holder = ttk.Frame(parent)
        ttk.Entry(holder, textvariable=var, width=54).pack(side='left')

        def browse():
            chosen = self.filedialog.askdirectory(title=prompt, initialdir=var.get() or str(PORT_DIR))
            if chosen:
                var.set(str(Path(chosen)))
        ttk.Button(holder, text=_('Browse…', 'Обзор…'), command=browse).pack(side='left', padx=(6, 0))
        ttk.Button(holder, text=_('Open', 'Открыть'), command=lambda: self.open_path(var.get(), key)).pack(
            side='left', padx=(6, 0))
        if on_change:
            var.trace_add('write', lambda *_a: on_change())
        return self.row(parent, title, holder, hint)

    def scrolled_page(self, name, title, subtitle):
        """A settings page: a heading and content that scrolls vertically."""
        tk, ttk = self.tk, self.ttk
        outer = ttk.Frame(self.content)
        head = ttk.Frame(outer, padding=(28, 22, 28, 6))
        head.pack(fill='x')
        ttk.Label(head, text=title, background=PANEL, foreground=TEXT, font=('Georgia', 20)).pack(anchor='w')
        subtitle_label = ttk.Label(head, text=subtitle, style='Muted.TLabel', justify='left')
        subtitle_label.pack(anchor='w')
        head.bind('<Configure>', lambda e: subtitle_label.configure(wraplength=max(self.px(100), e.width-self.px(56))))
        tk.Frame(outer, bg=LINE, height=1).pack(fill='x', padx=self.px(28), pady=(self.px(10), self.px(10)))
        canvas = tk.Canvas(outer, bg=PANEL, highlightthickness=0, bd=0)
        bar = ttk.Scrollbar(outer, orient='vertical', command=canvas.yview)
        inner = ttk.Frame(canvas, padding=(28, 0, 28, 24))
        inner.settings_category = name
        outer.viewport, outer.settings_body = canvas, inner
        inner.columnconfigure(1, weight=1)
        window = canvas.create_window(0, 0, window=inner, anchor='nw')
        inner.bind('<Configure>', lambda _e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(window, width=e.width))
        canvas.configure(yscrollcommand=bar.set)
        bar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        outer.scroll = lambda units: canvas.yview_scroll(units, 'units') if inner.winfo_height() > canvas.winfo_height() else None
        outer.scroll_to_top = lambda: canvas.yview_moveto(0)
        self.pages[name] = outer
        return inner

    # ---- layout ------------------------------------------------------------------------------
    def build(self):
        tk, ttk = self.tk, self.ttk
        side = tk.Frame(self.root, bg=BG, width=self.px(220))
        side.pack(side='left', fill='y')
        side.pack_propagate(False)
        self.side = side
        brand_width = self.px(184)
        self.brand_title = tk.Label(side, text='BLOODBORNE:\nTHE CROWNED\nWORKSHOP',
                                   bg=BG, fg=GOLD, font=('Georgia', 13),
                                   anchor='w', justify='left', wraplength=brand_width, bd=0, padx=0)
        self.brand_title.pack(fill='x', padx=self.px(18), pady=(self.px(12), self.px(4)))
        self.brand_author = tk.Label(side, text='by TatsunaKyo', bg=BG, fg=TEXT,
                                    font=('Segoe UI', 10), anchor='w', bd=0, padx=0)
        self.brand_author.pack(fill='x', padx=self.px(18))
        self.brand_origin = tk.Label(side, text='Native Windows port based on\nSuper Medo\'s bloodbornepc',
                                    bg=BG, fg=MUTED, font=('Segoe UI', 8),
                                    anchor='w', justify='left', wraplength=brand_width, bd=0, padx=0)
        self.brand_origin.pack(fill='x', padx=self.px(18), pady=(self.px(5), 0))
        self.brand_version = tk.Label(side, text=f'v{VERSION}' + ('\n' + _('co-op test build') if COOP_TEST else ''),
                                     bg=BG, fg=GOLD, font=('Segoe UI', 9),
                                     anchor='w', justify='left', wraplength=brand_width, bd=0, padx=0)
        self.brand_version.pack(fill='x', padx=self.px(18), pady=(self.px(3), self.px(8)))
        self.brand_mark = self.tk.Canvas(side, width=self.px(44), height=self.px(44), bg=BG, bd=0, highlightthickness=0)
        self.brand_mark.pack(anchor='w', padx=self.px(18), pady=(0, self.px(6)))
        self.draw_emblem(self.brand_mark, self.px(22), self.px(22), self.px(36))
        tk.Frame(side, bg=LINE, height=1).pack(fill='x', padx=self.px(18), pady=(0, self.px(6)))
        self.nav, self.current_page = {}, None
        navigation = (
            ('play', _('Play', 'Играть'), None),
            ('image', _('Image', 'Изображение'), _('SETTINGS', 'НАСТРОЙКИ')),
            ('frames', _('Frames', 'Кадры'), None),
            ('window', _('Window', 'Окно'), None),
            ('overlay', _('Overlay', 'Статистика'), None),
            ('cheats', _('Cheats', 'Читы'), None),
            ('effects', _('Effects', 'Эффекты'), None),
            ('advanced', _('Advanced', 'Дополнительно'), None),
            ('game', _('Game & files', 'Игра и файлы'), _('LAUNCHER', 'ЛАУНЧЕР')),
            ('online', _('Online co-op', 'Онлайн-кооператив'), None),
            ('mods', _('Mods & patches', 'Моды и патчи'), None),
            ('log', _('Log', 'Журнал'), None))
        for name, title, group in navigation:
            if group:
                tk.Label(side, text=group, bg=BG, fg=GOLD, anchor='w',
                         font=('Segoe UI', 8), padx=self.px(18)).pack(fill='x', pady=(self.px(7), self.px(2)))
            item = tk.Label(side, text='  ' + title, bg=BG, fg=MUTED, anchor='w', font=('Segoe UI', 10),
                            padx=self.px(12), pady=self.px(3), cursor='hand2', takefocus=True)
            item.pack(fill='x')
            item.bind('<Button-1>', lambda _e, n=name: self.show(n))
            item.bind('<Return>', lambda _e, n=name: self.show(n))
            item.bind('<space>', lambda _e, n=name: self.show(n))
            item.bind('<Enter>', lambda _e, n=name: n != self.current_page and self.nav[n].configure(bg=CARD, fg=TEXT))
            item.bind('<Leave>', lambda _e, n=name: n != self.current_page and self.nav[n].configure(bg=BG, fg=MUTED))
            self.nav[name] = item
        tk.Frame(side, bg=BG).pack(fill='both', expand=True)
        self.update_box = None
        self.side_note = tk.Label(side, text=_('In the game: Insert or L3+R3\nopens the port\'s menu.',
                                               'В игре: Insert или L3+R3\nоткрывает меню порта.'),
                                  bg=BG, fg=MUTED, font=('Segoe UI', 9), justify='left', wraplength=brand_width)
        self.side_note.pack(anchor='w', padx=self.px(18), pady=(0, self.px(14)))

        right = tk.Frame(self.root, bg=PANEL)
        right.pack(side='left', fill='both', expand=True)
        bar = tk.Frame(right, bg=BG, height=self.px(72), highlightthickness=1, highlightbackground=LINE)
        bar.pack(fill='x', side='bottom')
        bar.pack_propagate(False)
        self.status = tk.Label(bar, text='', bg=BG, fg=MUTED, font=('Segoe UI', 10), anchor='w', justify='left')
        self.status.pack(side='left', padx=self.px(20))
        bar.bind('<Configure>', lambda e: self.status.configure(wraplength=max(self.px(120), e.width-self.px(360))))
        self.play_button = ttk.Button(bar, text=_('PLAY', 'ИГРАТЬ'), style='Play.TButton', command=self.play)
        self.play_button.pack(side='right', padx=(10, 24), pady=11)
        self.stop_button = ttk.Button(bar, text=_('Stop', 'Остановить'), command=self.stop, state='disabled')
        self.stop_button.pack(side='right', pady=11)
        self.content = tk.Frame(right, bg=PANEL)
        self.content.pack(fill='both', expand=True)

        self.pages = {}
        self.build_play()
        self.build_image()
        self.build_frames()
        self.build_window()
        self.build_overlay()
        self.build_effects()
        self.build_game()
        self.build_cheats()
        self.build_online()
        self.build_mods()
        self.build_advanced()
        self.build_log()
        self.root.bind_all('<MouseWheel>', self.wheel)
        self.refresh_status()

    def wheel(self, event):
        page = self.pages.get(self.current_page)
        if hasattr(page, 'scroll') and not isinstance(event.widget, (self.tk.Text, self.ttk.Combobox)) \
                and 'popdown' not in str(event.widget):
            page.scroll(int(-event.delta / 120))

    def show(self, name):
        for page in self.pages.values():
            page.pack_forget()
        self.pages[name].pack(fill='both', expand=True)
        self.current_page = name
        for n, item in self.nav.items():
            item.configure(bg=CARD if n == name else BG, fg=GOLD if n == name else MUTED,
                           text=('│ ' if n == name else '  ') + item.cget('text')[2:])
        if name == 'mods':
            self.refresh_lists()
        elif name == 'image':
            self.refresh_fsr4()
        elif name == 'play':
            self.refresh_status()

    def show_overlay_settings(self, _event=None):
        self.show('overlay')
        self.pages['overlay'].scroll_to_top()
        return 'break'

    def build_play(self):
        tk, ttk = self.tk, self.ttk
        page = tk.Frame(self.content, bg=PANEL)
        self.pages['play'] = page
        self.banner = tk.Canvas(page, height=self.px(290), bg=BG, highlightthickness=0, bd=0)
        self.banner.pack(fill='x')
        self.banner.bind('<Configure>', lambda _e: self.draw_banner())
        body = ttk.Frame(page, padding=(self.px(20), self.px(12), self.px(20), self.px(8)))
        body.pack(fill='both', expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=0)
        info = ttk.Frame(body, style='Workshop.TFrame', padding=self.px(12))
        info.grid(row=0, column=0, sticky='new', padx=(0, self.px(12)))
        ttk.Label(info, text=_('Your workshop', 'Ваша мастерская'), style='WorkshopSection.TLabel').pack(anchor='w', pady=(0, 6))
        self.checks = {}
        for key in ('game', 'saves', 'gpu', 'fsr4'):
            self.checks[key] = ttk.Label(info, text='', style='Workshop.TLabel', justify='left', wraplength=self.px(440))
            self.checks[key].pack(anchor='w', pady=3)
        quick_card = ttk.Frame(body, style='Workshop.TFrame', padding=self.px(12))
        quick_card.grid(row=0, column=1, sticky='new')
        quick = ttk.Frame(quick_card)
        quick.pack(fill='x')
        ttk.Label(quick, text=_('Quick settings', 'Основное'), style='Section.TLabel').grid(
            row=0, column=0, columnspan=2, sticky='w', pady=(0, 2))
        self.section(quick, _('Image', 'Изображение'), top=4)
        self.row(quick, _('Upscaler', 'Апскейлер'), self.choice(quick, 'upscaler', 'ini', UPSCALERS, 26))
        self.quick_preset_row = self.row(quick, _('Preset', 'Пресет'),
                                         self.choice(quick, 'preset', 'ini', PRESETS, 26))
        self.quick_xess_row = self.row(quick, _('XeSS quality', 'Качество XeSS'),
                                       self.choice(quick, 'xess_preset', 'menu', XESS_PRESETS, 26))
        self.quick_dlss_row = self.dlss_preset_choice(quick, 26)
        self.row(quick, _('DLSS preset', 'Пресет DLSS'), self.quick_dlss_row)
        def show_upscaler_rows(*_args):
            provider = self.var('upscaler', 'ini').get()
            self.show_row(self.quick_preset_row, provider != 'xess')
            self.show_row(self.quick_xess_row, provider == 'xess')
            self.show_row(self.quick_dlss_row, provider == 'dlss')
        self.row(quick, _('Output', 'Разрешение'), self.choice(quick, 'output_res', 'ini', OUTPUTS, 26))
        self.section(quick, _('Frames', 'Кадры'), top=8)
        self.row(quick, _('Frame rate', 'Частота кадров'), self.choice(quick, 'fps_mode', 'app', FPS_MODES, 26))
        self.row(quick, _('Frame Generation', 'Генерация кадров'),
                 self.frame_generation_choice(quick, 26))
        quick_multiplier = self.choice(quick, 'nvidia_generated_frames', 'menu', NVIDIA_MULTIPLIERS, 26)
        self.quick_fg_multiplier_row = quick_multiplier
        self.row(quick, _('NVIDIA FG multiplier', 'Множитель NVIDIA FG'), quick_multiplier)
        def show_fg_multiplier(*_args):
            visible = self.var('frame_generation', 'menu').get() == 'nvidia'
            quick_multiplier.configure(state='readonly' if visible else 'disabled')
            for widget in (quick_multiplier.row_label, quick_multiplier):
                if visible:
                    widget.grid()
                else:
                    widget.grid_remove()
        self.section(quick, _('Window & overlay', 'Окно и статистика'), top=8)
        self.row(quick, _('Window mode', 'Режим окна'), self.choice(quick, 'window_mode', 'menu', WINDOW_MODES, 26))
        ttk.Checkbutton(quick, text=_('Show performance overlay', 'Показывать статистику'),
                        variable=self.var('show_fps', 'menu')).grid(
            row=self.next_row(quick), column=1, sticky='w', pady=(4, 0))
        self.overlay_link = ttk.Label(quick, text=_('Customize overlay…', 'Настроить статистику…'),
                                      foreground=GOLD, font=('Segoe UI', 10, 'underline'),
                                      cursor='hand2', takefocus=True)
        self.overlay_link.grid(
            row=self.next_row(quick), column=1, sticky='w', pady=(4, 0))
        for event in ('<Button-1>', '<Return>', '<space>'):
            self.overlay_link.bind(event, self.show_overlay_settings)
        # Reserve every grid row before hiding optional controls. Hidden rows have
        # zero height, but must never be reused by Output or another setting.
        self.var('upscaler', 'ini').trace_add('write', show_upscaler_rows)
        self.var('frame_generation', 'menu').trace_add('write', show_fg_multiplier)
        show_upscaler_rows()
        show_fg_multiplier()
        def fit_play(_event=None):
            # Leave space for the quick settings at narrow widths and high DPI.
            width = max(self.px(140), min(self.px(440),
                        body.winfo_width() - quick_card.winfo_reqwidth() - self.px(44)))
            for label in self.checks.values():
                if int(label.cget('wraplength')) != width:
                    label.configure(wraplength=width)
            required = max(quick_card.winfo_reqheight(), info.winfo_reqheight()) + self.px(22)
            height = max(self.px(90), min(self.px(290), page.winfo_height() - required))
            if int(self.banner.cget('height')) != height:
                self.banner.configure(height=height)
        for widget in (page, body, quick_card, quick, info):
            widget.bind('<Configure>', fit_play)
        for key in ('fps_mode', 'upscaler', 'output_res'):
            self.vars[key].trace_add('write', lambda *_a: self.refresh_status())

    def draw_emblem(self, canvas, x, y, size):
        """The editable crowned TK mark, drawn as vectors at the current DPI."""
        scale = size / 256
        def line(points, **kw):
            canvas.create_line(*[value for a,b in points for value in (x+(a-128)*scale,y+(b-128)*scale)],
                               fill=GOLD, width=max(1, self.px(1.3)), **kw)
        for points in (((54,74),(47,34),(90,54),(128,18),(166,54),(209,34),(202,74)),
                       ((58,87),(198,87)), ((47,218),(47,153),(76,119),(128,101),(180,119),(209,153),(209,218)),
                       ((75,137),(137,137)), ((106,137),(106,216)),
                       ((151,137),(151,216)), ((186,137),(151,174),(189,216)),
                       ((40,237),(216,237))):
            line(points)

    def draw_banner(self):
        """Workshop artwork and live typography, independent of the game dump's cover."""
        c = self.banner
        c.delete('all')
        w, h = max(c.winfo_width(), self.px(400)), int(c['height'])
        art = PORT_DIR / 'docs/assets/crowned-workshop-art-moon.png'
        key = (str(art), w, h)
        if self.banner_source != key:
            self.banner_source, self.banner_image = key, None
            try:
                from PIL import Image, ImageTk, ImageOps
                with Image.open(art) as painting:
                    # Keep the hunter/window on the right and a quiet field for lettering.
                    image = ImageOps.fit(painting.convert('RGB'), (w, h),
                                        method=Image.Resampling.LANCZOS, centering=(.75, .42))
                    self.banner_image = ImageTk.PhotoImage(image)
            except (ImportError, OSError, self.tk.TclError):
                pass
        if self.banner_image:
            c.create_image(0, 0, image=self.banner_image, anchor='nw', tags='workshop-art')
        compact = h < self.px(205)
        x = self.px(26)
        if not compact:
            self.draw_emblem(c, x+self.px(18), self.px(33), self.px(38))
            c.create_text(x+self.px(51), self.px(33), text='TatsunaKyo', anchor='w',
                          fill=GOLD, font=('Georgia', 11, 'italic'), tags='workshop-type')
        title_y = self.px(8) if compact else self.px(75)
        c.create_text(x, title_y, text='BLOODBORNE', anchor='nw', fill=TEXT,
                      font=('Georgia', 17 if compact else 26), tags='workshop-type')
        c.create_text(x, title_y+self.px(31 if compact else 43), text='The Crowned Workshop',
                      anchor='nw', fill=GOLD, font=('Georgia', 12 if compact else 18), tags='workshop-type')
        c.create_line(x, h-self.px(29), w-self.px(26), h-self.px(29), fill=LINE)
        info = game_info(self.var('game_dir', 'app').get())
        sub = (_('Game version {} · ready', 'Версия игры {} · готова').format(info[1]) if info
               else _('Choose your game folder in Game & files', 'Выберите папку игры в «Игра и файлы»'))
        c.create_text(x, h-self.px(15), text=sub, anchor='w', fill=TEXT,
                      font=('Segoe UI', 9), tags='workshop-type')

    def build_image(self):
        ttk = self.ttk
        f = self.scrolled_page('image', _('Image', 'Изображение'),
                               _('Upscaling, resolution and image tuning. Same category in the in-game menu.', 'Апскейлинг, разрешение и настройка изображения. Та же вкладка в меню игры.'))
        page = f
        f = self.settings_section(page, _('Upscaling & resolution', 'Апскейлинг и разрешение'))
        self.row(f, _('Upscaler', 'Апскейлер'), self.choice(f, 'upscaler', 'ini', UPSCALERS),
                 _("Temporal upscaling with the game's own motion vectors. FSR 4 needs its assets (below) and "
                   'a GPU with INT8 dot products; otherwise the game falls back to FSR 3.1 by itself.',
                   'Временной апскейлинг с векторами движения игры. FSR 4 нужны ассеты (ниже) и GPU с INT8; '
                   'иначе игра сама переключится на FSR 3.1.'))
        self.graphics_preset_row = self.row(f, _('Quality preset', 'Пресет'), self.choice(f, 'preset', 'ini', PRESETS),
                 _('Render scale per axis: Quality renders at 1/1.5 of the output size.',
                   'Масштаб рендера по каждой оси: Quality рисует в 1/1.5 размера вывода.'))
        self.graphics_xess_row = self.row(f, _('XeSS quality', 'Качество XeSS'),
                 self.choice(f, 'xess_preset', 'menu', XESS_PRESETS),
                 _('XeSS has its own ratios: Ultra Quality Plus ×1.3, Ultra Quality ×1.5, Quality ×1.7, Balanced ×2 and Performance ×2.3. Your DLSS/FSR quality is saved separately.',
                   'XeSS использует свои масштабы: Ultra Quality Plus ×1.3, Ultra Quality ×1.5, Quality ×1.7, Balanced ×2 и Performance ×2.3. Качество DLSS/FSR сохраняется отдельно.'))
        self.image_dlss_row = self.row(f, _('DLSS render preset', 'Пресет модели DLSS'), self.dlss_preset_choice(f),
                 _('Model hint, separate from render scale. '
                   'In-game changes apply on the next frame. '
                   'E/F are legacy; driver/profile overrides may supersede this choice.',
                   'Модель отдельно от масштаба. '
                   'Изменения в игре применяются на следующем кадре. '
                   'E/F устарели; драйвер или профиль может переопределить выбор.'))
        self.row(f, _('Output resolution', 'Разрешение вывода'), self.choice(f, 'output_res', 'ini', OUTPUTS),
                 _('What the upscaler produces; the HUD is drawn at this size too.',
                   'Что выдаёт апскейлер; интерфейс рисуется в этом же размере.'))
        self.row(f, _('Live resolution changes', 'Смена разрешения на лету'), self.choice(f, 'live_resolution', 'ini', LIVE),
                 _('Off: outputs other than 1080p are set by a patch at start (fastest; changing them in the '
                   'game restarts it). On: change output and preset in the game without a restart, at a cost.',
                   'Выкл.: разрешения кроме 1080p задаются патчем при запуске (быстрее). Вкл.: менять в игре '
                   'без перезапуска, но медленнее.'))
        f = self.settings_section(page, _('Image tuning', 'Настройка изображения'))
        self.check(f, 'sharpen', 'ini', _('Sharpening (RCAS)', 'Резкость (RCAS)'))
        holder = ttk.Frame(f)
        ttk.Scale(holder, from_=0.0, to=2.0, variable=self.var('sharpness', 'ini'), length=self.px(200)).pack(side='left')
        value = ttk.Label(holder, width=5)
        value.pack(side='left', padx=10)
        show = lambda *_a: value.configure(text=f'{self.vars["sharpness"].get():.2f}')
        self.vars['sharpness'].trace_add('write', show)
        show()
        self.track_setting(f, 'sharpness', holder)
        self.row(f, _('Sharpness', 'Сила резкости'), holder)
        self.check(f, 'object_motion', 'ini', _('Object motion vectors', 'Векторы движения объектов'),
                   _('Improves motion history for characters, cloth and weapons. Restart the game after changing it.',
                     'Улучшает историю движения персонажей, одежды и оружия. После изменения нужен перезапуск.'))
        f = self.settings_section(page, _('FSR 4 assets', 'Ассеты FSR 4'))
        self.fsr4_label = ttk.Label(f, text='', wraplength=self.px(590), justify='left')
        self.fsr4_label.grid(row=self.next_row(f), column=0, columnspan=2, sticky='w')
        holder = ttk.Frame(f)
        holder.grid(row=self.next_row(f), column=0, columnspan=2, sticky='w', pady=(8, 0))
        self.fsr4_button = ttk.Button(holder, text=_('Download FSR 4 assets', 'Скачать ассеты FSR 4'),
                                      command=self.download_fsr4)
        self.fsr4_button.pack(side='left')
        self.fsr4_progress = ttk.Progressbar(holder, length=280, maximum=len(fsr4_files()))
        self.fsr4_progress.pack(side='left', padx=12)
        self.note(f, _("From FireBurn/Q2RTX on GitHub (built from AMD's MIT-licensed FidelityFX source), "
                       'about 30 MB, into the fsr4_shaders folder of the port.',
                       'С GitHub FireBurn/Q2RTX (собраны из MIT-исходников AMD FidelityFX), около 30 МБ, '
                       'в папку fsr4_shaders порта.'), top=6)
        def show_quality_rows(*_args):
            provider = self.var('upscaler', 'ini').get()
            xess = provider == 'xess'
            self.show_row(self.graphics_preset_row, not xess)
            self.show_row(self.graphics_xess_row, xess)
            self.show_row(self.image_dlss_row, provider == 'dlss')
        # Assign all grid rows before hiding either quality control or its help text.
        self.var('upscaler', 'ini').trace_add('write', show_quality_rows)
        show_quality_rows()

    def build_frames(self):
        ttk = self.ttk
        f = self.scrolled_page('frames', _('Frames', 'Кадры'),
                               _('Real-frame limits, generated output and latency controls.', 'Лимиты реальных кадров, генерация и задержка.'))
        page = f
        f = self.settings_section(page, _('Real game frames', 'Реальные кадры игры'))
        self.row(f, _('Frame rate', 'Режим'), self.choice(f, 'fps_mode', 'app', FPS_MODES),
                 _("Community patches for game version 1.09. Unlocked makes the game use the real frame time. "
                   'Other game versions always run at 30 FPS (the patches would corrupt them).',
                   'Патчи сообщества для версии 1.09. «Без ограничения» — игра использует реальное время кадра. '
                   'Другие версии всегда работают в 30 FPS.'))
        self.row(f, _('Frame cap (unlocked mode)', 'Ограничение FPS (режим без ограничения)'),
                 self.fps_cap_control(f, 'real_fps_limit', 'menu', 30, 120, options=FRAME_CAPS),
                 _("Auto follows the startup/display policy. No cap removes the real ceiling. Above about 120 FPS the game's movement timing breaks (running and rolling get slower, "
                   'physics and animations can glitch): higher caps are at your own risk.',
                   'Выше ~120 FPS ломается тайминг движения игры (бег и перекаты замедляются, возможны '
                   'сбои физики и анимаций): более высокие значения — на ваш риск.'))
        self.row(f, _('Frames ahead of the GPU', 'Кадров впереди GPU'), self.choice(f, 'frames_ahead', 'app', FRAMES_AHEAD),
                 _('A shorter queue can reduce latency; more frames ahead can improve throughput on some configurations.',
                   'Короткая очередь может снизить задержку; больше кадров впереди иногда повышает производительность.'))
        f = self.settings_section(page, _('Frame Generation & output cap', 'Генерация кадров и лимит вывода'))
        self.row(f, _('Frame Generation', 'Генерация кадров'),
                 self.frame_generation_choice(f),
                 _('FSR FG adds one interpolated frame between real frames. Supports SDR and HDR10 with a temporal upscaler. The normal FPS limit counts real frames: 75 can produce 150 with FG 2x.',
                   'FSR FG добавляет один промежуточный кадр. Поддерживает SDR и HDR10 с временным апскейлером. Обычный лимит относится к реальным кадрам: 75 даёт до 150 с FG 2x.'))
        multiplier_choice = self.choice(f, 'nvidia_generated_frames', 'menu', NVIDIA_MULTIPLIERS)
        def multiplier_state(*_args):
            multiplier_choice.configure(state='readonly' if self.var('frame_generation', 'menu').get() == 'nvidia' else 'disabled')
        self.var('frame_generation', 'menu').trace_add('write', multiplier_state)
        multiplier_state()
        self.row(f, _('NVIDIA FG multiplier', 'Множитель NVIDIA FG'),
                 multiplier_choice,
                 _('NVIDIA FG requires a compatible GPU, driver and Hardware-accelerated GPU scheduling. Only multipliers supported by your GPU will run. SDR and HDR10 use the same FG path.',
                   'Нужны совместимые GPU, драйвер и планирование GPU с аппаратным ускорением. Работают только поддерживаемые GPU множители. Поддерживаются SDR и HDR10.'))
        self.nvidia_fg_preset_row = self.row(f, _('NVIDIA FG preset', 'Пресет NVIDIA FG'),
                 self.choice(f, 'nvidia_fg_preset', 'menu', NVIDIA_FG_PRESETS),
                 _('Applied before the next launch using the included NVIDIA runtime. Selecting a model disables driver DLL replacement for this installation; Default restores the previous settings. C/Lite needs DLSS-G 310.9.16, included here. The driver must accept the model for this process; see the detected model and exact errors under Frames in-game.',
                   'Применяется перед следующим запуском с включённой средой NVIDIA. Выбор модели отключает замену DLL драйвером для этой установки; Default возвращает прежние настройки. Данные драйвера и ошибки доступны в Frames в игре.'))
        self.check(f, 'nvidia_fg_mod', 'menu',
                   _('DLSSG mod for RTX 20/30 (experimental)', 'Мод DLSSG для RTX 20/30 (экспериментальный)'),
                   _('Requires restart and NVIDIA FG. Downloads the pinned RTX Encore provider once, only for the selected RTX 20/30. Vulkan support is experimental. RTX 40/50 always keep the original NVIDIA path. A supplied bin/mods/dlssg/dlssg_sm86.dll takes precedence.',
                     'Нужны перезапуск и NVIDIA FG. Проверенный файл RTX Encore загружается один раз только для выбранной RTX 20/30. Vulkan экспериментален. RTX 40/50 используют исходный путь NVIDIA. Пользовательская bin/mods/dlssg/dlssg_sm86.dll имеет приоритет.'))
        def fg_preset_visibility(*_args):
            self.show_row(self.nvidia_fg_preset_row, self.var('frame_generation', 'menu').get() == 'nvidia')
        self.var('frame_generation', 'menu').trace_add('write', fg_preset_visibility)
        self.check(f, 'limit_generated_fps', 'menu',
                   _('Limit total FPS with Frame Generation', 'Лимит общих FPS с генерацией кадров'))
        holder = self.fps_cap_control(f, 'generated_fps_limit', 'menu', 30, 1000,
                                      enabled_key='limit_generated_fps')
        self.row(f, _('Total FPS cap', 'Общий лимит FPS'), holder,
                 _('Optional. Includes generated frames and can reduce the real frame rate. Generated frames do not advance game logic or physics.',
                   'Необязательный лимит включает промежуточные кадры и может снизить реальные FPS. Генерация не меняет физику и логику игры.'))
        f = self.settings_section(page, _('Latency', 'Задержка'))
        self.row(f, _('NVIDIA Reflex', 'NVIDIA Reflex'),
                 self.choice(f, 'reflex', 'menu', REFLEX_MODES),
                 _('Available independently of DLSS FG on supported NVIDIA GPUs. NVIDIA FG enables Reflex automatically; Boost is optional.',
                   'Работает независимо от DLSS FG на совместимых GPU NVIDIA. NVIDIA FG включает Reflex автоматически; Boost необязателен.'))
        self.amd_antilag_check = self.check(f, 'amd_antilag', 'menu', 'AMD Anti-Lag 2',
                   _('Reduces input latency on supported Radeon GPUs through VK_AMD_anti_lag. Independent of the upscaler and FSR FG; unavailable drivers keep the normal path.',
                     'Снижает задержку ввода на совместимых Radeon через VK_AMD_anti_lag. Независимо от апскейлера и FSR FG; без поддержки используется обычный режим.'))
        # Hide only after every row in the section has a permanent grid index.
        fg_preset_visibility()

    def build_window(self):
        ttk = self.ttk
        f = self.scrolled_page('window', _('Window', 'Окно'),
                               _('Window mode, HDR presentation and behavior when unfocused.', 'Режим окна, HDR и работа в фоне.'))
        page = f
        f = self.settings_section(page, _('Window & presentation', 'Окно и показ кадров'))
        self.row(f, _('Window mode', 'Режим окна'), self.choice(f, 'window_mode', 'menu', WINDOW_MODES),
                 _('Borderless uses the desktop resolution and refresh rate, with fast Alt-Tab.',
                   'Режим без рамки использует разрешение и частоту рабочего стола, с быстрым Alt-Tab.'))
        self.borderless_vsync_check = ttk.Checkbutton(f,
            text=_('V-sync in borderless', 'V-sync без рамки'), variable=self.var('borderless_vsync', 'menu'))
        self.track_setting(f, 'borderless_vsync', self.borderless_vsync_check)
        self.borderless_vsync_check.grid(row=self.next_row(f), column=0, columnspan=2, sticky='w', pady=(4, 0))
        self.note(f, _('Off: lowest presentation queueing (Immediate; tearing is possible). '
                       'On: Mailbox without tearing, or FIFO if unavailable.',
                       'Выкл.: минимальная очередь (Immediate; возможны разрывы). '
                       'Вкл.: Mailbox без разрывов, либо FIFO.'), top=4)
        self.presentation_choice = self.choice(f, 'present_mode', 'app', PRESENT_MODES)
        self.row(f, _('Presentation', 'Режим показа кадров'), self.presentation_choice,
                 _('Used in windowed/fullscreen modes. Borderless uses the V-sync option above.',
                   'Для оконного и полноэкранного режимов. Без рамки используется V-sync выше.'))
        self.vars['window_mode'].trace_add('write', lambda *_a: self.update_window_controls())
        self.update_window_controls()
        self.check(f, 'hdr', 'app', _('Allow HDR output', 'Разрешить HDR'),
                   _('When HDR is on in Windows and the display supports it.',
                     'Если HDR включён в Windows и монитор его поддерживает.'))
        f = self.settings_section(page, _('Background behavior', 'Работа в фоне'))
        self.row(f, _('When in background', 'В фоне'),
                 self.choice(f, 'background_mode', 'menu', BACKGROUND_MODES),
                 _('Pause the entire game on Windows or cap background rendering when the window loses focus. '
                   'The foreground frame cap is kept.',
                   'При потере фокуса: приостановить всю игру в Windows или ограничить FPS в фоне. '
                   'Основной лимит FPS сохраняется.'))

    def build_overlay(self):
        ttk = self.ttk
        f = self.scrolled_page('overlay', _('Overlay', 'Статистика'),
                               _('Choose the performance information you want to see while playing.', 'Выберите статистику для показа во время игры.'))
        page = f
        f = self.settings_section(page, _('Performance overlay', 'Статистика производительности'))
        self.check(f, 'show_fps', 'menu', _('Show performance overlay', 'Показывать статистику'),
                   _('FPS, frame time and upscaler in the top-right corner.',
                     'FPS, время кадра и апскейлер в правом верхнем углу.'))
        f = self.settings_section(page, _('Optional fields', 'Дополнительные поля'))
        self.check(f, 'show_dlss_preset', 'menu',
                   _('Show DLSS preset in overlay', 'Показывать пресет DLSS в статистике'),
                   _('Add the preset letter on the same line. K>M means K is active and M is pending. '
                     'Turn this off to keep the original overlay.',
                     'Буква пресета в той же строке. K>M: K активен, M ожидает применения. '
                     'Выключите для исходной статистики.'))
        self.check(f, 'show_resolution', 'menu',
                   _('Show input/output resolution in overlay', 'Показывать разрешение входа/выхода'),
                   _('Current render and output sizes on the same OSD line.',
                     'Текущее разрешение рендера и вывода в той же строке статистики.'))
        self.check(f, 'show_frame_generation', 'menu',
                   _('Show Frame Generation in overlay', 'Показывать генерацию кадров в статистике'),
                   _('Show whether FG is active and its current multiplier on the same line.',
                     'Состояние генерации кадров и текущий множитель в той же строке.'))
        self.check(f, 'show_fg_preset', 'menu',
                   _('Show NVIDIA FG preset in overlay', 'Показывать пресет NVIDIA FG в статистике'),
                   _('FG model:C means NVIDIA confirms C. C? is a driver profile preference awaiting confirmation; C! means an override error. Independent of the DLSS upscaling preset.',
                     'FG model:C: NVIDIA подтверждает C. C?: значение профиля без подтверждения. C!: ошибка. Отдельно от пресета апскейлера DLSS.'))
        self.check(f, 'show_latency', 'menu',
                   _('Show PC latency in overlay', 'Показывать задержку ПК в статистике'),
                   _('Measured by NVIDIA Reflex, from simulation start to GPU completion. N/A means the driver has no valid sample. This excludes monitor and input-device latency.',
                     'Измеряется NVIDIA Reflex: от начала симуляции до завершения GPU. N/A означает отсутствие данных. Задержка монитора и устройства ввода не учитывается.'))
        f = self.settings_section(page, _('Frametime graph', 'График времени кадров'))
        self.frametime_graph_check = self.check(f, 'show_frametime_graph', 'menu',
                   _('Show frametime graph in overlay', 'Показывать график времени кадров'),
                   _('A compact trace of the last 240 real-frame presentation intervals, with the latest and peak time. Generated frames are not included; this is not GPU render time or monitor latency.',
                     'Компактный график последних 240 интервалов показа реальных кадров, с текущим и пиковым временем. Сгенерированные кадры не включены; это не время рендера GPU и не задержка монитора.'))

    def build_effects(self):
        ttk = self.ttk
        f = self.scrolled_page('effects', _('Effects', 'Эффекты'),
                               _('Game effects, detail, camera and gameplay patches for version 1.09. Restart required.', 'Эффекты, детализация, камера и патчи игры 1.09. Нужен перезапуск.'))
        page = f
        self.version_warning(f)
        f = self.settings_section(page, _('Detail & visual effects', 'Детализация и эффекты'))
        self.row(f, _('Model detail (LOD)', 'Детализация моделей'), self.choice(f, 'model_lod', 'ini', LODS),
                 _('A game patch (game version 1.09).', 'Патч игры (версия 1.09).'))
        for key, title, _on in EFFECTS:
            self.check(f, key, 'ini', _(*title))
        self.note(f, _('The game\'s AA preference is used with the upscaler off. Temporal upscalers use their own AA. Switching between Off and a temporal upscaler requires a restart to apply this game patch.',
                       'Собственное сглаживание игры используется без апскейлера. Временные апскейлеры используют своё сглаживание. Для переключения между Off и временным апскейлером нужен перезапуск.'))
        f = self.settings_section(page, _('Camera & gameplay extras', 'Камера и игровой процесс'))
        for key, title, _on in EXTRAS:
            self.check(f, key, 'ini', _(*title))
        self.note(f, _('Effects and extras are game patches for version 1.09, applied at start.',
                       'Эффекты и дополнения — патчи игры для версии 1.09, применяются при запуске.'))
        for key, title, _on in TWEAKS:
            self.check(f, key, 'ini', _(*title))



    def update_window_controls(self):
        borderless = self.var('window_mode', 'menu').get() == 'borderless'
        self.borderless_vsync_check.configure(state='normal' if borderless else 'disabled')
        self.presentation_choice.configure(state='disabled' if borderless else 'readonly')

    def refresh_menu_settings(self):
        latest = menu_values(self.app)
        for key, value in latest.items():
            var = self.vars.get(key)
            current = ('1' if var.get() else '0') if var is not None and key in MENU_FLAGS else \
                str(var.get()) if var is not None else self.menu_baseline[key]
            if current == self.menu_baseline[key]:
                self.menu[key] = self.menu_baseline[key] = value
                if var is not None:
                    var.set(value == '1' if key in MENU_FLAGS else value)

    def build_game(self):
        f = self.scrolled_page('game', _('Game & files', 'Игра и файлы'),
                               _('Your game dump, saves, player name and game language.', 'Дамп игры, сохранения, имя игрока и язык игры.'))
        self.section(f, _('Game', 'Игра'), top=4)
        self.folder(f, 'game_dir', _('Game folder', 'Папка игры'),
                    _('Choose the folder with eboot.bin', 'Выберите папку с eboot.bin'),
                    _('Your own dump of CUSA03173 (eboot.bin, sce_module, sce_sys, dvdroot_ps4); version 1.09 '
                      'for the community patches.', 'Ваш дамп CUSA03173 (eboot.bin, sce_module, sce_sys, '
                      'dvdroot_ps4); версия 1.09 для патчей сообщества.'), on_change=self.game_changed)
        self.folder(f, 'user_dir', _('Saves folder', 'Папка сохранений'),
                    _('Choose the saves folder', 'Выберите папку сохранений'),
                    _('Empty: {} (shader caches are kept there too).',
                      'Пусто: {} (там же кэш шейдеров).').format(DATA_DIR / 'user'), on_change=self.refresh_status)
        self.ttk.Button(f, text=_('Open Save Manager…', 'Открыть менеджер сохранений…'),
                        command=self.open_save_manager).grid(row=self.next_row(f), column=0, columnspan=2,
                                                              sticky='w', pady=(8, 4))
        self.ttk.Label(f, text=_('Automatic pre-launch backups, named snapshots and verified restore with rollback. Save operations require a closed game.',
                                'Резервные копии перед запуском, именованные снимки и проверенное восстановление. Операции требуют закрытой игры.'),
                       style='Muted.TLabel', wraplength=self.px(590)).grid(row=self.next_row(f), column=0, columnspan=2, sticky='we', pady=(0, 12))
        self.row(f, _('Game language', 'Язык игры'), self.choice(f, 'language', 'app', LANGUAGES))
        self.row(f, _('Player name', 'Имя игрока'), self.ttk.Entry(f, textvariable=self.var('player_name', 'app'), width=30),
                 _('Where the game shows the PSN name; empty: the default.', 'Где игра показывает имя PSN; пусто — по умолчанию.'))

    def build_cheats(self):
        f = self.scrolled_page('cheats', _('Cheats', 'Читы'),
                               _('Player cheats for version 1.09. Choices marked below require a restart. Leave them off for a normal '
                                 'play-through.', 'Читы для версии 1.09. Отмеченные настройки требуют перезапуска. Для обычного '
                                 'прохождения оставьте их выключенными.'))
        self.version_warning(f)
        page = f
        f = self.settings_section(page, _('Runtime cheats', 'Читы во время игры'))
        self.row(f, _('Player damage', 'Урон игрока'),
                 self.choice(f, 'cheat_damage', 'menu', CHEAT_MULTIPLIERS))
        self.row(f, _('Reduce enemy damage', 'Снизить урон врагов'),
                 self.choice(f, 'cheat_incoming', 'menu', CHEAT_MULTIPLIERS),
                 _('x2 halves damage received from enemies; x16 divides it by 16. Defense stats stay the same.',
                   'x2 делит урон врагов на 2; x16 — на 16. Характеристики защиты не меняются.'))
        self.row(f, _('Blood Echoes gained', 'Полученные эхо крови'),
                 self.choice(f, 'cheat_echoes', 'menu', CHEAT_MULTIPLIERS))
        self.row(f, _('Movement speed', 'Скорость движения'),
                 self.choice(f, 'cheat_movement', 'menu', MOVEMENT_MULTIPLIERS))
        self.check(f, 'cheat_infinite_stamina', 'menu', _('Infinite stamina', 'Бесконечная выносливость'))
        self.check(f, 'cheat_no_fall_damage', 'menu', _('No fall damage', 'Без урона от падения'),
                   _('Prevents normal fall damage for your character. Scripted deaths and death volumes still apply.',
                     'Отменяет обычный урон от падения для игрока. Скриптовые смерти и зоны смерти остаются.'))
        self.check(f, 'cheat_no_consume', 'menu',
                   _('Consumables are not reduced on use', 'Расходники не тратятся при использовании'),
                   _('Includes ammunition. You still need to own the item; selling, dropping and buying behave normally.',
                     'Включая боеприпасы. Нужен предмет в инвентаре; продажа, выбрасывание и покупка работают как обычно.'))
        self.note(f, _('These choices can also be changed from the in-game menu. They are enabled only when the version 1.09 hooks pass verification.',
                      'Эти настройки можно менять в меню игры. Они доступны только после проверки кода версии 1.09.'))
        f = self.settings_section(page, _('Startup cheats (restart required)', 'Читы при запуске (нужен перезапуск)'))
        for key, title, _on in CHEATS:
            self.check(f, key, 'ini', _(*title) + _(' (restart required)', ' (после перезапуска)'))
        # Enemy control and the free camera share their buttons: one at a time.
        control, camera = self.var('cheat_enemy_control', 'ini'), self.var('debug_camera', 'ini')
        control.trace_add('write', lambda *_a: control.get() and camera.set(False))
        camera.trace_add('write', lambda *_a: camera.get() and control.set(False))

    def build_online(self):
        ttk = self.ttk
        f = self.scrolled_page('online', _('Online co-op'),
                               _("Messages, bloodstains and ghosts come from The Hunter's Dream; bells and summons "
                                 'go through a shadNet server.'))
        self.check(f, 'online', 'app', _('Play online'),
                   _('Off: the game stays offline, as before.'))
        self.var('online', 'app').trace_add('write', lambda *_a: self.refresh_status())
        self.section(f, _('Game server (messages, bloodstains, ghosts)'))
        community = self.var('online_community', 'app')
        self.row(f, _('Game server'), ttk.Entry(f, textvariable=community, width=40),
                 _('The Hunter\'s Dream by default. Only the name is needed; the game picks the ports.'))
        self.section(f, _('Co-op server (bells and summons)'))
        server = self.var('online_server', 'app')
        self.row(f, _('Server address'), ttk.Entry(f, textvariable=server, width=40),
                 _('srv.shadps4.net:31313 is the public shadPS4 server. For a private server, enter '
                   'host:port from the person who runs it.'))
        self.row(f, _('WebAPI address'), ttk.Entry(f, textvariable=self.var('online_webapi', 'app'), width=40),
                 _('Of the shadNet server, not the game server. Leave empty: the server address with '
                   'port 31315 is used.'))
        self.section(f, _('Account'))
        self.row(f, _('Online ID (NPID)'), ttk.Entry(f, textvariable=self.var('online_npid', 'app'), width=40),
                 _('Your shadNet account name, not your email. Register one at shadnet.shadps4.net, or ask the '
                   'owner of a private server.'))
        self.row(f, _('Password'), ttk.Entry(f, textvariable=self.var('online_password', 'app'), width=40, show='•'),
                 _('Saved on this PC with the other launcher settings.'))
        self.section(f, _('Connection'))
        self.check(f, 'online_upnp', 'app', _('UPnP (open a port on the router automatically)'),
                   _('Turn it off on Tailscale or another VPN.'))
        result = ttk.Label(f, text='', style='Muted.TLabel', justify='left')

        def check():
            values = {key: self.var(key, 'app').get()
                      for key in ('online_server', 'online_webapi', 'online_community')}
            address = values['online_server'].strip() or APP_DEFAULTS['online_server']
            webapi, game = webapi_setting(values), community_address(values['online_community'])
            online_on = self.var('online', 'app').get()
            result.configure(text=_('Checking…'))

            def work():
                text = server_check(address, webapi, game)
                if values['online_webapi'].strip() and values['online_webapi'].strip() != webapi:
                    text += '\n' + _('The WebAPI box holds the game server address; it is ignored.')
                if not online_on:
                    text += '\n' + _('"Play online" is off: the game starts offline.')
                self.ui_calls.put(lambda: result.configure(text=text))
            threading.Thread(target=work, daemon=True).start()
        self.row(f, '', ttk.Button(f, text=_('Test connection'), command=check))
        result.grid(row=self.next_row(f), column=1, sticky='w', pady=(6, 0))
        self.note(f, _('Everyone in a session needs the same game version (1.09) and the same server. '
                       'Cheats change the game for the other players too: turn them off when you play together.'))

    def build_mods(self):
        f = self.scrolled_page('mods', _('Mods & patches', 'Моды и патчи'),
                               _('The game files are never changed: mods are layered over them at start.',
                                 'Файлы игры не меняются: моды накладываются при запуске.'))
        self.section(f, _('Mods', 'Моды'), top=4)
        self.check(f, 'mods_enabled', 'app', _('Load mods', 'Загружать моды'),
                   _('Loose-file mods, each in its own folder (with dvdroot_ps4, or chr\\, parts\\ … directly).',
                     'Моды из файлов, каждый в своей папке (с dvdroot_ps4 или chr\\, parts\\ … напрямую).'))
        self.folder(f, 'mods_dir', _('Mods folder', 'Папка модов'), _('Choose the mods folder', 'Выберите папку модов'),
                    _('Empty: {}', 'Пусто: {}').format(DATA_DIR / 'mods'), on_change=self.refresh_lists)
        self.mods_frame = self.ttk.Frame(f)
        self.mods_frame.grid(row=self.next_row(f), column=0, columnspan=2, sticky='we', pady=(8, 0))
        self.section(f, _('Third-party patches', 'Сторонние патчи'))
        self.folder(f, 'patches_dir', _('Patches folder', 'Папка патчей'), _('Choose the patches folder', 'Выберите папку патчей'),
                    _('shadPS4/GoldHEN XML patch files for version 1.09. Empty: {}',
                      'XML-патчи shadPS4/GoldHEN для версии 1.09. Пусто: {}').format(DATA_DIR / 'patches'),
                    on_change=self.refresh_lists)
        self.patches_frame = self.ttk.Frame(f)
        self.patches_frame.grid(row=self.next_row(f), column=0, columnspan=2, sticky='we', pady=(8, 0))
        self.ttk.Button(f, text=_('Refresh', 'Обновить'), command=self.refresh_lists).grid(
            row=self.next_row(f), column=0, sticky='w', pady=(14, 0))

    def build_advanced(self):
        ttk = self.ttk
        f = self.scrolled_page('advanced', _('Advanced', 'Дополнительно'),
                               _('Launcher options, performance switches and diagnostics.',
                                 'Настройки лаунчера, производительность и диагностика.'))
        page = f
        f = self.settings_section(page, _('Language & launcher', 'Язык и лаунчер'))
        self.row(f, _('In-game menu language', 'Язык внутриигрового меню'),
                 self.choice(f, 'menu_language', 'menu', MENU_LANGUAGES),
                 _('Language of the R3+L3 / Insert settings menu.', 'Язык меню настроек R3+L3 / Insert.'))
        self.row(f, _('Launcher language', 'Язык лаунчера'), self.choice(f, 'ui_language', 'app', UI_LANGUAGES),
                 _('Applies when the launcher opens again.', 'Применится при следующем открытии лаунчера.'))
        self.check(f, 'close_on_play', 'app', _('Close the launcher when the game starts', 'Закрывать лаунчер при запуске игры'))
        self.check(f, 'check_updates', 'app', _('Check for updates when the launcher opens',
                                                'Проверять обновления при открытии лаунчера'))
        holder = ttk.Frame(f)
        holder.grid(row=self.next_row(f), column=0, columnspan=2, sticky='w', pady=(10, 0))
        ttk.Button(holder, text=_('Desktop shortcut', 'Ярлык на рабочем столе'), command=self.shortcut).pack(side='left')
        ttk.Button(holder, text=_('Add to Steam'), command=self.add_to_steam).pack(side='left', padx=(6, 0))
        ttk.Button(holder, text=_('Port folder', 'Папка порта'), command=lambda: self.open_path(DATA_DIR)).pack(side='left', padx=6)
        ttk.Button(holder, text='bbport.ini', command=lambda: self.open_path(ini_path())).pack(side='left')
        holder = ttk.Frame(f)
        holder.grid(row=self.next_row(f), column=0, columnspan=2, sticky='w', pady=(10, 0))
        ttk.Button(holder, text=_('Check for updates', 'Проверить обновления'),
                   command=lambda: threading.Thread(target=self.check_update, args=(True,), daemon=True).start()
                   ).pack(side='left')
        ttk.Label(holder, text=f'v{VERSION}', style='Muted.TLabel').pack(side='left', padx=10)
        holder = ttk.Frame(f)
        holder.grid(row=self.next_row(f), column=0, columnspan=2, sticky='w', pady=(10, 0))
        ttk.Button(holder, text=_('Clear shader cache', 'Очистить кэш шейдеров'), command=self.clear_cache).pack(side='left')
        ttk.Label(holder, text=_('If the game only shows a black screen, this usually helps.',
                                 'Если игра показывает только чёрный экран, обычно это помогает.'),
                  style='Muted.TLabel').pack(side='left', padx=10)
        f = self.settings_section(page, _('Renderer', 'Рендер'))
        self.row(f, _('Two-stage GPU pipeline', 'Двухстадийный конвейер GPU'), self.choice(f, 'draw_pipe', 'app', DRAW_PIPE),
                 _('Overlaps command preparation and GPU work. Switch it off when comparing an instability.', 'Совмещает подготовку команд с работой GPU. Выключите для сравнения при нестабильности.'))
        self.row(f, _('GPU readbacks', 'Чтение данных GPU'), self.choice(f, 'readbacks', 'app', READBACKS),
                 _('How exactly data the GPU writes is copied back for the game.',
                   'Насколько точно данные, записанные GPU, возвращаются игре.'))
        f = self.settings_section(page, _('Diagnostics', 'Диагностика'))
        self.check(f, 'developer_profile', 'app', _('Developer profiling and crash diagnostics', 'Профилирование и диагностика сбоев'))
        ttk.Label(f, text=_('Off by default. Keeps one folder per run in the saves folder / diagnostics, with timings, settings, the exit code and a crash dump when available. Profiling can affect performance.',
                           'По умолчанию выключено. Сохраняет журнал, тайминги, настройки, код завершения и дамп сбоя в папке сохранений / diagnostics. Профилирование может снизить скорость.'),
                  style='Muted.TLabel', wraplength=int(590*self.dpi)).grid(row=self.next_row(f), column=0, columnspan=2, sticky='w', pady=(0,8))
        self.check(f, 'frame_stats', 'app', _('Frame statistics in the log (every 5 s)', 'Статистика кадров в журнале (раз в 5 с)'))
        self.check(f, 'gpu_profile', 'app', _('GPU time per pass in the log', 'Профиль GPU в журнале'))
        comparisons = ttk.Frame(f)
        comparisons.grid(row=self.next_row(f), column=0, columnspan=2, sticky='w', pady=(8, 4))
        self.nvidia_capture_button = ttk.Button(comparisons,
            text=_('Capture NVIDIA FG inputs', 'Записать входные данные NVIDIA FG'),
            command=lambda: self.play('inputs'))
        self.nvidia_capture_button.pack(side='left')
        self.nvidia_compare_button = ttk.Button(comparisons,
            text=_('Show generated frames only', 'Только сгенерированные кадры'),
            command=lambda: self.play('generated-only'))
        self.nvidia_compare_button.pack(side='left', padx=(8, 0))
        ttk.Label(f, text=_('One diagnostic run. Keep NVIDIA FG enabled; press F8 when assets flash, then close the game. Renderer settings stay in use. Capture can affect timing.',
                            'Один диагностический запуск. Оставьте NVIDIA FG включённой; нажмите F8 при мерцании объектов и закройте игру. Настройки рендера сохраняются. Запись может влиять на время кадров.'),
                  style='Muted.TLabel', wraplength=int(590*self.dpi)).grid(
                      row=self.next_row(f), column=0, columnspan=2, sticky='w', pady=(0, 4))
        self.check(f, 'vk_validation', 'app', _('Vulkan validation layers (needs the Vulkan SDK; much slower)',
                                                'Слои валидации Vulkan (нужен Vulkan SDK; сильно замедляет)'))
        self.ttk.Button(f, text=_('Generate Support Report…', 'Создать отчёт для поддержки…'),
                        command=self.generate_support_report).grid(row=self.next_row(f), column=0, columnspan=2,
                                                                   sticky='w', pady=(12, 4))
        self.ttk.Label(f, text=_('Inspect sanitized diagnostics and an optional anonymous hardware profile before exporting a ZIP. Nothing is uploaded.',
                                'Просмотрите очищенную диагностику и необязательный анонимный профиль перед экспортом ZIP. Ничего не загружается.'),
                       style='Muted.TLabel', wraplength=self.px(590)).grid(row=self.next_row(f), column=0, columnspan=2, sticky='we')
        self.row(f, _('Extra variables', 'Доп. переменные'), ttk.Entry(f, textvariable=self.var('extra_env', 'app'), width=58),
                 _('NAME=value pairs separated by spaces (README lists them).', 'Пары ИМЯ=значение через пробел (список в README).'))

    def build_log(self):
        tk, ttk = self.tk, self.ttk
        page = ttk.Frame(self.content, padding=(20, 14, 20, 8))
        self.pages['log'] = page
        top = ttk.Frame(page)
        top.pack(fill='x', pady=(0, 8))
        ttk.Label(top, text=_('Log', 'Журнал'), font=('Georgia', 20)).pack(side='left')
        ttk.Button(top, text=_('Copy', 'Копировать'), command=self.copy_log).pack(side='right')
        ttk.Button(top, text=_('Clear', 'Очистить'), command=lambda: self.set_log('')).pack(side='right', padx=6)
        ttk.Button(top, text=_('Generate Support Report…', 'Создать отчёт для поддержки…'),
                   command=self.generate_support_report).pack(side='right', padx=6)
        self.log = tk.Text(page, wrap='none', bg='#0a0908', fg='#cfc6b8', insertbackground=TEXT, relief='flat',
                           font=('Consolas', 9), padx=8, pady=6, state='disabled', highlightthickness=0)
        bar = ttk.Scrollbar(page, command=self.log.yview)
        self.log.configure(yscrollcommand=bar.set)
        bar.pack(side='right', fill='y')
        self.log.pack(fill='both', expand=True)

    def support_report_context(self):
        """Read current UI/preferences without changing game, mod or launcher files."""
        app, ini, menu = dict(self.app), dict(self.ini), dict(self.menu)
        stores = {'app': app, 'ini': ini, 'menu': menu}
        for key, var in self.vars.items():
            try:
                value = var.get()
            except self.tk.TclError:
                continue
            stores[var.store][key] = value
        return {'port_dir': PORT_DIR, 'user_dir': Path(app.get('user_dir') or DATA_DIR / 'user'),
                'settings': app, 'ini': ini, 'menu': menu, 'revision': VERSION}

    def generate_support_report(self):
        from support_report_ui import open_support_report
        return open_support_report(self)

    def open_save_manager(self):
        from save_manager_ui import open_save_manager
        return open_save_manager(self)

    def version_warning(self, parent):
        """A banner shown while the selected game is not version 1.09 (refresh_status)."""
        label = self.ttk.Label(parent, style='Warning.TLabel', wraplength=self.px(590), justify='left', text=_(
            'Your game is version {}: these options are patches for 1.09 and are not applied; the game runs '
            'at 30 FPS. Update the dump to 1.09 to use them.',
            'Ваша игра версии {}: эти настройки — патчи для 1.09 и не применяются; игра работает в 30 FPS. '
            'Обновите дамп до 1.09, чтобы их использовать.'))
        label.grid(row=self.next_row(parent), column=0, columnspan=2, sticky='we', pady=(6, 4))
        label.template = label.cget('text')
        self.warnings = getattr(self, 'warnings', []) + [label]

    # ---- state -------------------------------------------------------------------------------
    def game_changed(self):
        self.banner_source = None
        self.draw_banner()
        self.set_icon()
        self.refresh_status()

    def refresh_status(self):
        info = game_info(self.var('game_dir', 'app').get())
        if not info:
            game = _('✗ No eboot.bin in the game folder (Game & files)', '✗ В папке игры нет eboot.bin («Игра и файлы»)')
        elif info[1] == PATCH_VERSION:
            game = _('✓ Game version {}: every patch available', '✓ Версия игры {}: доступны все патчи').format(info[1])
        else:
            game = _('⚠ Game version {}: runs at 30 FPS without the community patches (they are for 1.09)',
                     '⚠ Версия игры {}: 30 FPS без патчей сообщества (они для 1.09)').format(info[1])
        user = Path(self.var('user_dir', 'app').get() or DATA_DIR / 'user')
        saves = list((user / 'savedata').glob('*/*/SPRJ*')) if (user / 'savedata').is_dir() else []
        save = (_('✓ Saves found in {}', '✓ Найдены сохранения в {}').format(user) if saves
                else _('• No saves yet: the game creates them in {}', '• Сохранений пока нет: игра создаст их в {}').format(user))
        missing = fsr4_missing()
        fsr4 = (_('✓ FSR 4 assets installed', '✓ Ассеты FSR 4 установлены') if not missing else
                _('• FSR 4 assets missing (Image); FSR 3.1 is used meanwhile',
                  '• Нет ассетов FSR 4 («Изображение»); пока используется FSR 3.1'))
        for key, text in (('game', game), ('saves', save), ('gpu', self.gpu_text), ('fsr4', fsr4)):
            self.checks[key].configure(text=text, foreground=MUTED if text.startswith('•') else
                                       '#d9a441' if text.startswith('⚠') else '#d36b5c' if text.startswith('✗') else TEXT)
        for label in getattr(self, 'warnings', []):
            if info and info[1] != PATCH_VERSION:
                label.configure(text=label.template.format(info[1]))
                label.grid()
            else:
                label.grid_remove()
        if not self.process:
            self.play_button.configure(state='normal' if info and not getattr(self, 'save_busy', False) else 'disabled')
            self.status.configure(text=self.summary() if info else _('Choose the game folder first.',
                                                                     'Сначала выберите папку игры.'), fg=MUTED)

    def summary(self):
        fps = dict(FPS_MODES).get(self.var('fps_mode', 'app').get(), ('?',))
        info = game_info(self.var('game_dir', 'app').get())
        if info and info[1] != PATCH_VERSION:
            fps = ('30 FPS',)
        upscaler = dict(UPSCALERS).get(self.var('upscaler', 'ini').get(), ('?',))[0].split(' (')[0]
        output = self.var('output_res', 'ini').get().replace('x', ' × ')
        online = _('Online') if self.var('online', 'app').get() else _('Offline')
        return f'{_(*fps)}   ·   {upscaler}   ·   {output}   ·   {online}'

    def detect_gpu(self):
        exe = PORT_DIR / 'bin' / 'bb-gpu-capabilities.exe'
        if not exe.is_file():
            exe = PORT_DIR / 'out' / 'bb-gpu-capabilities.exe'
        env = dict(os.environ)
        if not (exe.parent / 'SDL3.dll').is_file():
            clang64 = Path(os.environ.get('MSYS2_ROOT', r'C:\msys64')) / 'clang64' / 'bin'
            env['PATH'] = f'{clang64}{os.pathsep}{env.get("PATH", "")}'
        text = _('• Graphics card: not checked', '• Видеокарта: не проверена')
        try:
            result = subprocess.run([str(exe), '--live-resolution'], capture_output=True, text=True, timeout=30,
                                    env=env, creationflags=NO_WINDOW)
            names = [line[5:].split(':')[0] for line in result.stderr.splitlines() if line.startswith('GPU: ')]
            if names:
                text = _('✓ Graphics card: {}', '✓ Видеокарта: {}').format(names[0])
            elif result.returncode:
                text = _('✗ No Vulkan 1.3 graphics card found (update the driver)',
                         '✗ Не найдена видеокарта с Vulkan 1.3 (обновите драйвер)')
            capability = subprocess.run([str(exe), '--amd-antilag'], capture_output=True, text=True,
                                        timeout=30, env=env, creationflags=NO_WINDOW)
            if capability.returncode == 0 and capability.stdout.strip() in ('0', '1'):
                available = capability.stdout.strip() == '1'
                self.ui_calls.put(lambda: self.amd_antilag_check.configure(state='normal' if available else 'disabled'))
        except (OSError, subprocess.TimeoutExpired):
            pass
        self.gpu_text = text
        self.ui_calls.put(self.refresh_status)

    def refresh_fsr4(self):
        total, missing = len(fsr4_files()), len(fsr4_missing())
        self.fsr4_progress.configure(value=total - missing)
        self.fsr4_label.configure(
            text=_('Installed: {} files in {}.', 'Установлены: {} файлов в {}.').format(total, PORT_DIR / 'fsr4_shaders')
            if not missing else _('{} of {} files missing in {}.', 'Нет {} из {} файлов в {}.').format(
                missing, total, PORT_DIR / 'fsr4_shaders'))
        self.fsr4_button.configure(state='normal' if missing and not self.downloading else 'disabled')

    def download_fsr4(self):
        self.downloading = True
        self.fsr4_button.configure(state='disabled')
        folder = PORT_DIR / 'fsr4_shaders'

        def work():
            error = None
            try:
                folder.mkdir(parents=True, exist_ok=True)
                for name in fsr4_missing():
                    part = folder / (name + '.part')
                    with urllib.request.urlopen(f'{FSR4_BASE}/{name}', timeout=60) as response:
                        part.write_bytes(response.read())
                    part.replace(folder / name)
                    self.ui_calls.put(self.refresh_fsr4)
            except OSError as failure:
                error = failure

            def done():
                self.downloading = False
                self.refresh_fsr4()
                self.refresh_status()
                if error:
                    self.messagebox.showerror('FSR 4', _('Download failed: {}', 'Не удалось скачать: {}').format(error))
            self.ui_calls.put(done)
        threading.Thread(target=work, daemon=True).start()

    def refresh_lists(self):
        if not hasattr(self, 'patches_frame'):
            return
        tk, ttk = self.tk, self.ttk
        from mods import discover
        from patches import external_patches
        for holder in (self.mods_frame, self.patches_frame):
            for widget in holder.winfo_children():
                widget.destroy()
        root = Path(self.var('mods_dir', 'app').get() or DATA_DIR / 'mods')
        profile = load_json(DATA_DIR / 'mods.json', {})
        available = discover(root)
        if set(self.mod_order) != set(available):
            known = [n for n in profile.get('order', []) if n in available]
            self.mod_order = known + [n for n in available if n not in known]
        old = {n: v.get() for n, v in self.mod_vars.items()}
        self.mod_vars = {}
        if not available:
            ttk.Label(self.mods_frame, text=_('No mods in {} yet.', 'В {} пока нет модов.').format(root),
                      style='Muted.TLabel').pack(anchor='w')
        for index, name in enumerate(self.mod_order):
            line = ttk.Frame(self.mods_frame)
            line.pack(fill='x', pady=1)
            var = tk.BooleanVar(value=old.get(name, name not in profile.get('disabled', [])))
            self.mod_vars[name] = var
            ttk.Button(line, text='▲', width=3, command=lambda i=index: self.move_mod(i, -1)).pack(side='left')
            ttk.Button(line, text='▼', width=3, command=lambda i=index: self.move_mod(i, 1)).pack(side='left', padx=(2, 10))
            ttk.Checkbutton(line, text=f'{index + 1}.  {name}', variable=var).pack(side='left')
        if len(self.mod_order) > 1:
            ttk.Label(self.mods_frame, text=_('Lower in the list loads later and wins conflicts.',
                                              'Ниже в списке — загружается позже и перекрывает.'),
                      style='Muted.TLabel').pack(anchor='w', pady=(4, 0))
        chosen = load_json(DATA_DIR / 'patches.json', {})
        found = external_patches(Path(self.var('patches_dir', 'app').get() or DATA_DIR / 'patches'), PATCH_VERSION)
        old = {n: v.get() for n, v in self.patch_vars.items()}
        self.patch_vars = {}
        if not found:
            ttk.Label(self.patches_frame, text=_('No patch files for version 1.09 yet.', 'Пока нет патчей для версии 1.09.'),
                      style='Muted.TLabel').pack(anchor='w')
        for key, _path, meta in found:
            on = key in chosen.get('enabled', []) or (key not in chosen.get('disabled', []) and
                                                      meta.get('isEnabled', 'false').lower() == 'true')
            var = tk.BooleanVar(value=old.get(key, on))
            self.patch_vars[key] = var
            author = meta.get('Author')
            ttk.Checkbutton(self.patches_frame, text=key + (f'  —  {author}' if author else ''), variable=var).pack(anchor='w')

    def move_mod(self, index, step):
        other = index + step
        if 0 <= other < len(self.mod_order):
            self.mod_order[index], self.mod_order[other] = self.mod_order[other], self.mod_order[index]
            self.refresh_lists()

    def collect(self):
        """Writes launcher, renderer, overlay, mod and patch settings."""
        for commit in getattr(self, 'fps_cap_committers', []):
            commit()
        self.refresh_menu_settings()
        menu_changes = {}
        for key, var in self.vars.items():
            try:
                value = var.get()
            except self.tk.TclError:  # an unfinished number in a spinbox
                value = (MENU_DEFAULTS[key] == '1' if key in MENU_FLAGS else MENU_DEFAULTS[key]) \
                    if var.store == 'menu' else APP_DEFAULTS.get(key, INI_DEFAULTS.get(key))
            if var.store == 'ini':
                self.ini[key] = ('1' if value else '0') if key in INI_FLAGS else \
                    f'{float(value):.2f}' if key == 'sharpness' else str(value)
            elif var.store == 'menu':
                value = ('1' if value else '0') if key in MENU_FLAGS else str(value)
                if value != self.menu_baseline[key]:
                    menu_changes[key] = value
                self.menu[key] = value
            else:
                self.app[key] = value
        # Migrate the old launcher-only cap into the shared live setting, including
        # an unchanged migrated value. A running game's edits were merged above.
        menu_changes['real_fps_limit'] = self.menu['real_fps_limit']
        self.app['frame_cap'] = ''
        self.app['real_fps_limit'] = self.menu['real_fps_limit']
        save_menu(menu_changes)
        self.menu_baseline = dict(self.menu)
        self.app['window_mode'] = self.menu['window_mode']
        self.app['fullscreen'] = self.menu['window_mode'] != 'windowed'
        self.ini['show_fps'] = self.menu['show_fps']
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(self.app, indent=2, ensure_ascii=False), encoding='utf-8')
        save_ini({key: self.ini[key] for key in INI_DEFAULTS}, self.ini_lines)
        self.ini, self.ini_lines = load_ini()
        if self.mod_order:
            (DATA_DIR / 'mods.json').write_text(json.dumps(
                {'order': self.mod_order, 'disabled': [n for n, v in self.mod_vars.items() if not v.get()]},
                indent=2), encoding='utf-8')
        if self.patch_vars:
            chosen = load_json(DATA_DIR / 'patches.json', {})
            shown = set(self.patch_vars)
            enabled = {k for k in chosen.get('enabled', []) if k not in shown} | {k for k, v in self.patch_vars.items() if v.get()}
            disabled = {k for k in chosen.get('disabled', []) if k not in shown} | {k for k, v in self.patch_vars.items() if not v.get()}
            (DATA_DIR / 'patches.json').write_text(json.dumps(
                {'enabled': sorted(enabled), 'disabled': sorted(disabled)}, indent=2), encoding='utf-8')

    # ---- game process ------------------------------------------------------------------------
    def play(self, nvidia_diagnostic=None):
        if self.process or getattr(self, 'save_busy', False):
            return
        online, npid = self.var('online', 'app'), self.var('online_npid', 'app')
        if not online.get() and npid.get().strip():
            choice = self.messagebox.askyesnocancel(
                'Bloodborne', _('An online account is filled in, but "Play online" is off.\n\n'
                                'Yes: play online.   No: play offline.'))
            if choice is None:
                return
            online.set(bool(choice))
        if online.get() and '@' in npid.get():
            self.messagebox.showwarning(
                'Bloodborne', _('The Online ID is the account name (NPID) you registered on the server, '
                                'not your email address.'))
            self.show('online')
            return
        self.collect()
        if not game_info(self.app['game_dir']):
            self.messagebox.showerror('Bloodborne', _('Choose the game folder with eboot.bin (CUSA03173).',
                                                      'Выберите папку игры с eboot.bin (CUSA03173).'))
            self.show('game')
            return
        self.set_log('')
        settings = dict(self.app)
        if nvidia_diagnostic in ('inputs', 'generated-only'):
            settings = nvidia_diagnostic_settings(settings, ['--nvidia-diagnostic=' + nvidia_diagnostic])
        diagnostic = None
        try:
            diagnostic = DiagnosticSession(settings)
            self.process = subprocess.Popen(run_command(), cwd=PORT_DIR, env=diagnostic.environment(game_environment(settings)),
                                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
        except OSError as error:
            if diagnostic:
                diagnostic.record(f'Could not start: {error}\n')
                diagnostic.finish(-1)
            self.append(_('Could not start: {}', 'Не удалось запустить: {}').format(error) + '\n')
            self.process = None
            return
        self.job = GameJob(self.process)
        # Continue draining the pipe when Close launcher hides the UI. Losing
        # the reader would truncate profiling and can break the child's stdout.
        threading.Thread(target=self.read_output, args=(self.process, settings, diagnostic), daemon=False).start()
        self.play_button.configure(state='disabled')
        self.stop_button.configure(state='normal')
        self.status.configure(text=_('Preparing the game; it opens in its own window…',
                                     'Подготовка игры; она откроется в своём окне…'), fg=GOLD)
        if self.app.get('close_on_play'):
            self.root.after(5000, self.root.destroy)  # the game keeps running

    def read_output(self, process, settings, diagnostic):
        """Helper thread: the game's output to the Log page and to <saves folder>/last_run.log."""
        def emit(text):
            if not self.ui_closed:
                self.output.put(text)
        code=read_game_output(process, settings, diagnostic, emit)
        if not self.ui_closed:
            self.output.put((code,))

    def drain_output(self):
        while not self.ui_calls.empty():
            self.ui_calls.get_nowait()()
        try:
            for _i in range(500):
                item = self.output.get_nowait()
                if isinstance(item, tuple):
                    self.append(_('\n— the game exited (code {}) —\n', '\n— игра завершилась (код {}) —\n').format(item[0]))
                    self.process = None
                    if self.job:
                        self.job.close()
                    self.stop_button.configure(state='disabled')
                    self.refresh_menu_settings()
                    self.refresh_status()
                else:
                    if 'Entering original x86-64 code' in item:
                        self.status.configure(text=_('The game is running.', 'Игра запущена.'), fg=GOLD)
                    elif 'restarting through run.py' in item:
                        self.status.configure(text=_('Restarting with the new settings…', 'Перезапуск с новыми настройками…'), fg=GOLD)
                    self.append(item)
        except queue.Empty:
            pass
        self.root.after(100, self.drain_output)

    def stop(self):
        if self.job:
            self.job.terminate()

    def append(self, text):
        self.log.configure(state='normal')
        self.log.insert('end', text)
        lines = int(self.log.index('end-1c').split('.')[0])
        if lines > MAX_LOG_LINES:
            self.log.delete('1.0', f'{lines - MAX_LOG_LINES}.0')
        self.log.see('end')
        self.log.configure(state='disabled')

    def set_log(self, text):
        self.log.configure(state='normal')
        self.log.delete('1.0', 'end')
        self.log.insert('end', text)
        self.log.configure(state='disabled')

    def copy_log(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.log.get('1.0', 'end'))

    def open_path(self, path, key=None):
        if key == 'user_dir' and not path:
            path = DATA_DIR / 'user'
        elif key == 'mods_dir' and not path:
            path = DATA_DIR / 'mods'
        elif key == 'patches_dir' and not path:
            path = DATA_DIR / 'patches'
        path = Path(path or DATA_DIR)
        if path.suffix == '.ini':
            self.collect()
        elif not path.exists():
            path.mkdir(parents=True, exist_ok=True)
        os.startfile(str(path))

    # ---- updates -------------------------------------------------------------------------------
    def check_update(self, manual=False):
        """Helper thread: asks GitHub for the newest release and offers it when it is newer."""
        try:
            version, url, page = latest_release()
        except (OSError, ValueError, KeyError) as failure:
            if manual:
                self.ui_calls.put(lambda error=failure: self.messagebox.showerror(
                    'Bloodborne', _('Could not check for updates: {}', 'Не удалось проверить обновления: {}').format(error)))
            return

        def show():
            if version_tuple(version) > version_tuple(VERSION):
                self.offer_update(version, url, page)
            elif manual:
                self.messagebox.showinfo('Bloodborne', _('You have the latest version ({}).',
                                                         'У вас последняя версия ({}).').format(VERSION))
        self.ui_calls.put(show)

    def offer_update(self, version, url, page):
        if self.update_box:
            return
        tk, ttk = self.tk, self.ttk
        text = _('Version {} is available.', 'Доступна версия {}.').format(version)
        box = tk.Frame(self.side, bg=CARD, highlightthickness=1, highlightbackground=GOLD)
        self.update_label = tk.Label(box, text=text, bg=CARD, fg=GOLD, font=('Segoe UI', 10, 'bold'),
                                     wraplength=self.px(160), justify='left')
        self.update_label.pack(anchor='w', padx=10, pady=(8, 6))
        buttons = tk.Frame(box, bg=CARD)
        buttons.pack(fill='x', padx=10, pady=(0, 10))
        self.update_button = ttk.Button(buttons, text=_('Update', 'Обновить'),
                                        command=lambda: self.install_update(version, url, page))
        self.update_button.pack(fill='x')
        ttk.Button(buttons, text=_("What's new", 'Что нового'), command=lambda: webbrowser.open(page)).pack(
            fill='x', pady=(4, 0))
        box.pack(fill='x', padx=(22, 18), pady=(0, 14), before=self.side_note)
        self.update_box = box
        if not self.process:
            self.status.configure(text=text, fg=GOLD)

    def install_update(self, version, url, page):
        if self.process:
            self.messagebox.showinfo('Bloodborne', _('Close the game before updating.', 'Закройте игру перед обновлением.'))
            return
        if not FROZEN or not url:  # a source tree updates with git
            webbrowser.open(page)
            return
        if not self.messagebox.askyesno('Bloodborne', _(
                'Install version {} now? The launcher closes, installs it and opens again. Saves and settings are kept.',
                'Установить версию {} сейчас? Лаунчер закроется, установит её и откроется снова. Сохранения и '
                'настройки останутся.').format(version)):
            return
        self.update_button.configure(state='disabled')

        def progress(percent):
            self.update_label.configure(text=_('Downloading version {}… {}%', 'Загрузка версии {}… {}%').format(
                version, percent))

        def work():
            try:
                # Each launcher owns its staging folder; a second launcher must
                # not erase another update in progress.
                update_dir = Path(tempfile.mkdtemp(prefix='crowned-workshop-update-'))
                archive = update_dir / update_package_name(version)
                request = urllib.request.Request(url, headers={'User-Agent': 'bbport-launcher'})
                with urllib.request.urlopen(request, timeout=60) as response, open(archive, 'wb') as out:
                    total, done, shown = int(response.headers.get('Content-Length') or 0), 0, -1
                    while chunk := response.read(1 << 20):
                        out.write(chunk)
                        done += len(chunk)
                        percent = done * 100 // total if total else 0
                        if percent != shown:
                            shown = percent
                            self.ui_calls.put(lambda p=percent: progress(p))
                checksum_request = urllib.request.Request(url + '.sha256', headers={'User-Agent': 'bbport-launcher'})
                with urllib.request.urlopen(checksum_request, timeout=30) as response:
                    sidecar = response.read(4097).decode('utf-8')
                self.ui_calls.put(lambda: self.update_label.configure(text=_('Verifying update…', 'Проверка обновления…')))
                root = verify_update_archive(archive, version, sidecar)
                with zipfile.ZipFile(archive) as package:
                    package.extractall(update_dir / 'new')
                archive.unlink()
                new = update_dir / 'new' / root
                # The new launcher copies itself over this installation once this one has closed.
                subprocess.Popen([str(new / 'Bloodborne.exe'), '--install-update', str(PORT_DIR), str(os.getpid())],
                                 cwd=str(new), stdin=subprocess.DEVNULL, creationflags=NO_WINDOW)
                self.ui_calls.put(self.root.destroy)
            except (OSError, ValueError, zipfile.BadZipFile) as failure:
                if 'update_dir' in locals():
                    shutil.rmtree(update_dir, ignore_errors=True)
                def failed(error=failure):
                    self.update_button.configure(state='normal')
                    self.update_label.configure(text=_('Version {} is available.', 'Доступна версия {}.').format(version))
                    self.messagebox.showerror('Bloodborne', _('Update failed: {}', 'Не удалось обновить: {}').format(error))
                self.ui_calls.put(failed)
        threading.Thread(target=work, daemon=True).start()

    def clear_cache(self):
        """Shader and pipeline caches; they are rebuilt while playing."""
        if self.process:
            return
        import shutil
        cache = Path(self.app['user_dir'] or DATA_DIR / 'user') / 'cache'
        shutil.rmtree(cache, ignore_errors=True)
        self.messagebox.showinfo('Bloodborne', _('Shader cache cleared. The next start stutters for a few minutes while '
                                                 'it is rebuilt.', 'Кэш шейдеров очищен. Следующий запуск несколько '
                                                 'минут будет подтормаживать, пока кэш собирается заново.'))

    def shortcut(self):
        """Bloodborne.lnk on the desktop."""
        if FROZEN:
            target, arguments, icon = sys.executable, '', f'{sys.executable},0'
        else:  # a source tree: the launcher script with the windowless Python
            pythonw = Path(sys.executable).with_name('pythonw.exe')
            target = str(pythonw if pythonw.exists() else sys.executable)
            arguments, icon = Path(__file__).resolve(), PORT_DIR / 'launcher' / 'bloodborne.ico'
        script = ('$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath("Desktop")'
                  '+"\\Bloodborne.lnk");'
                  f'$s.TargetPath="{target}";$s.WorkingDirectory="{PORT_DIR}";$s.IconLocation="{icon}";'
                  + (f"$s.Arguments='\"{arguments}\"';" if arguments else '') + '$s.Save()')
        result = subprocess.run(['powershell', '-NoProfile', '-Command', script], capture_output=True,
                                creationflags=NO_WINDOW)
        if result.returncode == 0:
            self.messagebox.showinfo('Bloodborne', _('Shortcut created on the desktop.', 'Ярлык создан на рабочем столе.'))
        else:
            self.messagebox.showerror('Bloodborne', result.stderr.decode(errors='replace')[:400])

    def add_to_steam(self):
        """Bloodborne in the Steam library (a non-Steam game that starts Play Bloodborne.exe)."""
        import bbport_steam
        steam = bbport_steam.steam_folder()
        configs = bbport_steam.user_configs(steam) if steam else []
        if not configs:
            self.messagebox.showerror('Bloodborne', _('Steam was not found on this PC (or nobody has signed in to it yet).'))
            return
        if FROZEN:
            exe, options = PORT_DIR / 'Play Bloodborne.exe', ''
        else:
            pythonw = Path(sys.executable).with_name('pythonw.exe')
            exe, options = (pythonw if pythonw.exists() else Path(sys.executable)), f'"{Path(__file__).resolve()}" --play'
        self.collect()  # Play Bloodborne.exe starts the game with the saved settings
        restart = False
        if bbport_steam.steam_running():
            if not self.messagebox.askyesno('Bloodborne', _('Steam has to close while the game is added; it starts '
                                                            'again afterwards. Close Steam now?')):
                return
            subprocess.Popen([str(steam / 'steam.exe'), '-shutdown'], creationflags=NO_WINDOW)
            for _i in range(60):
                time.sleep(0.5)
                if not bbport_steam.steam_running():
                    break
            else:
                self.messagebox.showerror('Bloodborne', _('Steam did not close. Close it yourself and try again.'))
                return
            time.sleep(1)  # Steam writes its files as it exits
            restart = True
        try:
            for config in configs:
                bbport_steam.add_shortcut(config / 'shortcuts.vdf', 'Bloodborne', str(exe), str(PORT_DIR),
                                          str(exe), options)
        except (OSError, ValueError) as error:
            self.messagebox.showerror('Bloodborne', _('Could not add the game to Steam: {}').format(error))
            return
        if restart:
            os.startfile('steam://open/games')
        self.messagebox.showinfo('Bloodborne', _('Bloodborne is in your Steam library. It starts with the settings '
                                                 'saved in this launcher.'))

    def close(self):
        try:
            self.collect()
        except Exception:  # never keep the window open over a settings problem
            pass
        self.root.destroy()


class GameJob:
    """A Windows job holding run.py and everything it starts: bb-probe.exe and the launches made
    by the in-game restart (no longer descendants of the first process)."""

    def __init__(self, process):
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateJobObjectW.restype = ctypes.c_void_p
        self.handle = kernel32.CreateJobObjectW(None, None)
        if self.handle:
            kernel32.AssignProcessToJobObject(ctypes.c_void_p(self.handle), ctypes.c_void_p(int(process._handle)))

    def terminate(self):
        if self.handle:
            ctypes.windll.kernel32.TerminateJobObject(ctypes.c_void_p(self.handle), 1)

    def close(self):
        if self.handle:
            ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(self.handle))
            self.handle = None


def play_without_window(settings):
    """--play: the game with the saved settings (shortcuts, Steam). Output goes to the console
    when there is one and to <saves folder>/last_run.log."""
    attach_stdio()
    diagnostic = DiagnosticSession(settings)
    try:
        process = subprocess.Popen(run_command(), cwd=PORT_DIR, env=diagnostic.environment(game_environment(settings)),
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
    except OSError as error:
        diagnostic.record(f'Could not start: {error}\n')
        diagnostic.finish(-1)
        raise
    def emit(text):
        try:
            sys.stdout.write(text)
        except (OSError, ValueError):
            pass
    return read_game_output(process, settings, diagnostic, emit)


def version_tuple(text):
    return tuple(int(number) for number in re.findall(r'\d+', text or ''))


def update_package_name(version):
    from release_integrity import package_name
    return package_name(version)


def verify_update_archive(archive, version, sidecar):
    """Check the downloaded checksum and release identity before running its code."""
    from release_integrity import checksum, validate
    archive = Path(archive)
    if not isinstance(sidecar, str) or len(sidecar) > 4096:
        raise ValueError('Invalid update checksum file.')
    match = re.fullmatch(r'([0-9a-fA-F]{64})[ \t]+\*?([^\r\n]+)\s*', sidecar.strip())
    if not match or match[2] != archive.name or match[1].lower() != checksum(archive):
        raise ValueError('The downloaded update does not match its SHA-256 checksum.')
    try:
        return validate(archive, expected_version=version)['root']
    except (TypeError, KeyError, SyntaxError) as failure:
        raise ValueError('The update contains malformed release metadata.') from failure


def latest_release():
    """(version, Windows package URL, page URL) of this fork's latest revision."""
    request = urllib.request.Request(RELEASES_API, headers={'Accept': 'application/vnd.github+json',
                                                            'User-Agent': 'bbport-launcher'})
    with urllib.request.urlopen(request, timeout=15) as response:
        release = json.load(response)
    if not isinstance(release, dict) or release.get('draft') or release.get('prerelease'):
        raise ValueError('The stable updater does not install drafts or prereleases.')
    # Revisions 19 and 21 were published as stable releases with a legacy
    # -preview tag. GitHub's release flag determines their channel.
    tag_name = release.get('tag_name')
    tag = re.fullmatch(r'windows-v(\d+(?:\.\d+)*)-tatsunakyo\.(\d+)(?:-preview)?',
                       tag_name) if isinstance(tag_name, str) else None
    if not tag:
        raise ValueError('The latest release is not a TatsunaKyo Windows revision.')
    version = f'{tag[1]}-tatsunakyo.{tag[2]}'
    package_name = f'Bloodborne-Windows-v{tag[1]}-TatsunaKyo-Revision-{tag[2]}.zip'
    assets = release.get('assets', [])
    if not isinstance(assets, list):
        raise ValueError('Invalid release asset list.')
    packages = [asset for asset in assets if isinstance(asset, dict)
                and asset.get('name') == package_name
                and asset.get('state', 'uploaded') == 'uploaded']
    url = packages[0].get('browser_download_url') if len(packages) == 1 else None
    if url and (not isinstance(url, str) or not url.startswith('https://')):
        raise ValueError('Invalid Windows package URL.')
    return version, url, release.get('html_url') or RELEASES_PAGE


def wait_for_previous_launcher(wait_pid):
    kernel = ctypes.windll.kernel32
    kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel.WaitForSingleObject.restype = ctypes.c_uint32
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel.CloseHandle.restype = ctypes.c_int
    handle = kernel.OpenProcess(0x00100000, False, int(wait_pid))
    if not handle:
        # An exited PID is no longer a process. Access denied or another lookup
        # failure is not evidence that the old launcher has closed.
        return kernel.GetLastError() == 87  # ERROR_INVALID_PARAMETER
    try:
        return kernel.WaitForSingleObject(handle, 60000) == 0  # WAIT_OBJECT_0
    finally:
        kernel.CloseHandle(handle)


def install_update(target, wait_pid):
    """--install-update TARGET PID, run by the downloaded version from its temporary folder:
    waits for the old launcher to close, copies this version over TARGET (never the saves,
    settings or mods) and starts it."""
    target = Path(target)
    if not wait_for_previous_launcher(wait_pid):
        ctypes.windll.user32.MessageBoxW(None, _(
            'The previous launcher did not close. No update files were copied. Close it and retry the update.',
            'Предыдущий лаунчер не закрылся. Файлы не копировались. Закройте его и повторите обновление.'), 'Bloodborne', 0x10)
        return 1
    ignore = shutil.ignore_patterns(*USER_FILES)
    for attempt in range(30):
        try:
            shutil.copytree(PORT_DIR, target, dirs_exist_ok=True, ignore=ignore)
            break
        except OSError:  # a file still in use: the old launcher is closing
            time.sleep(1)
    else:
        ctypes.windll.user32.MessageBoxW(None, _(
            'Could not install the update. Download it from the releases page.',
            'Не удалось установить обновление. Скачайте его со страницы релизов.'), 'Bloodborne', 0x10)
        webbrowser.open(RELEASES_PAGE)
        return 1
    subprocess.Popen([str(target / 'Bloodborne.exe')], cwd=str(target))
    return 0


def main():
    global LANG
    args = sys.argv[1:]
    if args and args[0] in ('--run', '--script'):
        sys.exit(run_role(args))
    settings = {**APP_DEFAULTS, **load_json(CONFIG_FILE, {})}
    normal_settings = settings
    settings = geometry_diagnostic_settings(settings, args)
    settings = nvidia_diagnostic_settings(settings, args)
    settings = traversal_diagnostic_settings(settings, args)
    LANG = settings.get('ui_language') or windows_language()
    if args[:1] == ['--install-update'] and len(args) == 3:
        sys.exit(install_update(args[1], args[2]))
    # Without a usable game folder there is nothing to play yet: open the launcher instead.
    if '--play' in args and (Path(settings['game_dir'] or '.') / 'eboot.bin').is_file():
        sys.exit(play_without_window(settings))
    # Comparison switches apply to that launch; never serialize them through the UI.
    settings = {key: value for key, value in normal_settings.items()
                if key not in ('_geometry_diagnostic', '_nvidia_diagnostic', '_traversal_diagnostic')}
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # sharp text on scaled displays
    except (AttributeError, OSError):
        pass
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    root = tk.Tk()
    Launcher(root, tk, ttk, filedialog, messagebox)
    root.mainloop()


if __name__ == '__main__':
    main()
