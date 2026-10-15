# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Per-installation NVIDIA FG model preference, applied before the renderer starts.

NVAPI declarations are adapted from NVIDIA's MIT-licensed public SDK, commit
70d337db9186e968eab622f7e786de7e437faf3d. See third_party/nvapi/LICENSE.txt.
Only the two FG settings in a dedicated application profile are changed.
"""
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import tempfile

ENABLE = 0x10E41E03
PRESET = 0x10E41DF1
KEYS = (ENABLE, PRESET)
U32 = C.c_uint32
Unicode = C.c_uint16 * 2048


class Binary(C.Structure):
    _fields_ = [('length', U32), ('data', C.c_ubyte * 4096)]


class Value(C.Union):
    _pack_ = 4
    _fields_ = [('dword', U32), ('binary', Binary), ('text', Unicode), ('qword', C.c_uint64)]


class Setting(C.Structure):
    _pack_ = 4
    _fields_ = [('version', U32), ('name', Unicode), ('id', U32), ('type', U32),
                ('location', U32), ('predefined', U32), ('predefined_valid', U32),
                ('default', Value), ('current', Value)]


class Application(C.Structure):
    _fields_ = [('version', U32), ('predefined', U32), ('name', Unicode),
                ('friendly', Unicode), ('launcher', Unicode)]


class Profile(C.Structure):
    _fields_ = [('version', U32), ('name', Unicode), ('gpu_support', U32),
                ('predefined', U32), ('apps', U32), ('settings', U32)]


def wide(text):
    raw = str(text).encode('utf-16-le')
    if len(raw) >= C.sizeof(Unicode):
        raise ValueError('NVIDIA profile name is too long')
    result = Unicode()
    C.memmove(result, raw, len(raw))
    return result


def version(value):
    value.version = C.sizeof(value) | (1 << 16)
    return value


class ProfileError(RuntimeError):
    pass


class Driver:
    """cdecl NVAPI entry points; no DLL is loaded from the game directory."""
    def __init__(self):
        self.dll = C.WinDLL('nvapi64.dll', winmode=0x00000800)  # System32 only
        query = self.dll.nvapi_QueryInterface
        query.argtypes, query.restype = [U32], C.c_void_p
        def api(identifier, *types):
            address = query(identifier)
            if not address:
                raise ProfileError('The NVIDIA driver lacks the profile API')
            return C.CFUNCTYPE(C.c_int, *types)(address)
        ptr = C.c_void_p
        self.initialize = api(0x0150E828)
        self.unload = api(0xD22BDD7E)
        self.create_session = api(0x0694D52E, C.POINTER(ptr))
        self.destroy_session = api(0xDAD9CFF8, ptr)
        self.load = api(0x375DBD6B, ptr)
        self.save_api = api(0xFCBC7E14, ptr)
        self.find_app = api(0xEEE566B2, ptr, C.POINTER(C.c_uint16), C.POINTER(ptr), C.POINTER(Application))
        self.create_profile = api(0xCC176068, ptr, C.POINTER(Profile), C.POINTER(ptr))
        self.create_app = api(0x4347A9DE, ptr, ptr, C.POINTER(Application))
        self.get_api = api(0x73BF8338, ptr, ptr, U32, C.POINTER(Setting))
        self.set_api = api(0x577DD202, ptr, ptr, C.POINTER(Setting))
        self.delete_api = api(0xE4A26362, ptr, ptr, U32)
        self.profile_info = api(0x61CD6FD6, ptr, ptr, C.POINTER(Profile))
        self.session = ptr()
        self.profile = ptr()
        self.started = False

    @staticmethod
    def check(code):
        if code:
            raise ProfileError(f'NVIDIA profile operation failed ({code})')

    def open(self, executable, name, create):
        self.check(self.initialize())
        self.started = True
        self.check(self.create_session(C.byref(self.session)))
        self.check(self.load(self.session))
        app = version(Application())
        result = self.find_app(self.session, wide(executable), C.byref(self.profile), C.byref(app))
        if result == -166 and create:
            info = version(Profile())
            info.name = wide(name)
            self.check(self.create_profile(self.session, C.byref(info), C.byref(self.profile)))
            app.name, app.friendly = wide(executable), wide('Bloodborne: The Crowned Workshop')
            self.check(self.create_app(self.session, self.profile, C.byref(app)))
        elif result == -166:
            return False
        else:
            self.check(result)
            info = version(Profile())
            self.check(self.profile_info(self.session, self.profile, C.byref(info)))
            # Never edit a pre-existing generic/shared game profile or global profile.
            if bytes(info.name) != bytes(wide(name)) or info.predefined or info.apps != 1:
                raise ProfileError('This executable already belongs to another NVIDIA profile; manage its FG preset in NVIDIA App')
        return True

    def get(self, key):
        setting = version(Setting())
        result = self.get_api(self.session, self.profile, key, C.byref(setting))
        if result == -160:
            return None
        self.check(result)
        if setting.type != 0:
            raise ProfileError('Unexpected type for an NVIDIA FG setting')
        return int(setting.current.dword) if setting.location == 0 and not setting.predefined else None

    def set(self, key, value):
        if value is None:
            result = self.delete_api(self.session, self.profile, key)
            if result != -160:
                self.check(result)
        else:
            setting = version(Setting())
            setting.id, setting.current.dword = key, value
            self.check(self.set_api(self.session, self.profile, C.byref(setting)))

    def save(self):
        self.check(self.save_api(self.session))

    def close(self):
        if self.session:
            self.destroy_session(self.session)
            self.session = C.c_void_p()
        if self.started:
            self.unload()
            self.started = False


def write_journal(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent,
                                         prefix=path.name + '.', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def apply(preset, executable, store, driver_factory=Driver):
    """Return a startup log message. A DRS write is a preference, not active-model proof."""
    if preset not in ('default', 'a', 'b', 'c'):
        raise ValueError('Invalid NVIDIA FG preset')
    executable = str(Path(executable).resolve())
    identity = hashlib.sha256(executable.casefold().encode('utf-8')).hexdigest()[:24]
    name = 'The Crowned Workshop - ' + identity
    path = Path(store) / (identity + '.json')
    if preset == 'default' and not path.exists():
        return 'NVIDIA FG preset: follows NVIDIA settings (no profile changes).'
    journal = json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
    if journal is not None:
        if (journal.get('schema') != 1 or journal.get('profile') != name or
                journal.get('executable') != executable or
                not isinstance(journal.get('original'), dict)):
            raise ProfileError('The NVIDIA profile backup is invalid; no driver settings were changed')
        for field in ('original', 'applied', 'pending'):
            values = journal.get(field)
            if values is not None and (set(values) != {str(k) for k in KEYS} or
                    any(v is not None and (type(v) is not int or not 0 <= v <= 0xffffffff) for v in values.values())):
                raise ProfileError('The NVIDIA profile backup contains invalid settings')
    driver = driver_factory()
    try:
        if not driver.open(executable, name, create=preset != 'default'):
            if (preset == 'default' and journal is not None and journal.get('applied') is None
                    and all(value is None for value in journal['original'].values())):
                path.unlink()
                return 'NVIDIA FG preset: follows NVIDIA settings; the interrupted profile was never saved.'
            raise ProfileError('The original NVIDIA application profile is missing; its backup was kept')
        current = {str(k): driver.get(k) for k in KEYS}
        if journal is None:
            journal = {'schema': 1, 'profile': name, 'executable': executable,
                       'original': current, 'applied': None, 'pending': None}
        else:
            for key, value in current.items():
                owned = [v[key] for f in ('original', 'applied', 'pending') if (v := journal.get(f)) is not None]
                if value not in owned:
                    raise ProfileError('NVIDIA FG settings changed outside the launcher; no settings were overwritten and the backup was kept')
        target = journal['original'] if preset == 'default' else {str(ENABLE): 1, str(PRESET): ord(preset) - ord('a') + 1}
        if current != target:
            journal['pending'] = target
            # A recoverable backup must reach disk before SaveSettings can change DRS.
            write_journal(path, journal)
            for key in KEYS:
                if current[str(key)] != target[str(key)]:
                    driver.set(key, target[str(key)])
            driver.save()
            # Read a fresh DRS session, rather than treating the requested value as proof.
            driver.close()
            driver = driver_factory()
            if not driver.open(executable, name, create=False) or any(driver.get(k) != target[str(k)] for k in KEYS):
                raise ProfileError('The NVIDIA FG preference could not be verified; the recovery backup was kept')
        if preset == 'default':
            path.unlink(missing_ok=True)
            return 'NVIDIA FG preset: previous per-game NVIDIA settings restored.'
        journal['applied'], journal['pending'] = target, None
        write_journal(path, journal)
        return f'NVIDIA FG preset: {preset.upper()} saved to this installation\'s driver profile; waiting for runtime confirmation.'
    finally:
        driver.close()


def configure_launch(config, executable, environment):
    """Called by run.py, covering the launcher, shortcuts and in-game restart."""
    from pathlib import Path
    menu = {}
    try:
        for line in Path(config).with_suffix('.menu.ini').read_text(encoding='utf-8').splitlines():
            if '=' in line:
                key, value = line.split('=', 1)
                menu[key.strip()] = value.strip().lower()
    except FileNotFoundError:
        pass
    preset = menu.get('nvidia_fg_preset', 'default')
    # Preserve the user's choice when trying another FG provider; restore our override.
    if menu.get('frame_generation') != 'nvidia':
        preset = 'default'
    store = Path(environment.get('APPDATA', Path.home())) / 'bbport-launcher' / 'nvidia-profiles'
    try:
        return apply(preset, executable, store)
    except (OSError, ValueError, ProfileError, AttributeError) as error:
        # Do not include paths from OS/JSON exceptions in the session log.
        detail = str(error) if isinstance(error, ProfileError) else 'NVIDIA API or profile backup unavailable'
        return f'NVIDIA FG preset: not applied. {detail}.'
