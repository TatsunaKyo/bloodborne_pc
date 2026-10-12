# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Build an inspectable support archive from the port's existing diagnostics."""
from dataclasses import dataclass
from datetime import datetime, timezone
import ctypes
import hashlib
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import zipfile

SCHEMA_VERSION = 1
MAX_JSON = 512 * 1024
MAX_LOG = 384 * 1024
MAX_REPORT = 8 * 1024 * 1024
MAX_SESSIONS = 3
REPORT_FILES = re.compile(r'^(?:report\.json|report-summary\.md|performance\.json|'
                          r'hardware-submission\.json|build-identity\.json|manifest\.json|'
                          r'logs/last_run\.log|sessions/session-[1-3]/session\.(?:json|log))$')
REPOSITORY = 'https://github.com/TatsunaKyo/bloodborne_pc'

# Values are validated as well as keys: a modified setting must not smuggle a
# path, account or arbitrary environment variable into a nominally safe field.
ENUMS = {
    'upscaler': {'off', 'taa', 'dlss', 'xess', 'fsr3', 'fsr4', 'fsr411'},
    'window_mode': {'launcher', 'windowed', 'borderless', 'fullscreen'},
    'present_mode': {'Mailbox', 'Fifo', 'FifoRelaxed', 'Immediate'},
    'fps_mode': {'uncap', '30', '60', '75', '90'},
    'dlss_preset': {'default', 'e', 'f', 'j', 'k', 'm', 'l'},
    'frame_generation': {'off', 'fsr', 'nvidia'},
    'reflex': {'off', 'on', 'boost'}, 'background_mode': {'run', 'pause', '30', '60'},
    'live_resolution': {'auto', '0', '1'}, 'menu_language': {'en', 'ru'},
    'draw_pipe': {'', '0', '1'}, 'readbacks': {'', '0', '2'},
}
BOOL_KEYS = {'fullscreen', 'hdr', 'frame_stats', 'gpu_profile', 'vk_validation',
             'developer_profile', 'mods_enabled', 'sharpen', 'object_motion',
             'show_fps', 'borderless_vsync', 'show_dlss_preset', 'show_resolution',
             'show_frame_generation', 'show_latency', 'show_frametime_graph',
             'limit_generated_fps', 'amd_antilag', 'cheat_infinite_stamina',
             'cheat_no_consume', 'cheat_no_fall_damage', 'cheat_no_death',
             'cheat_stealth', 'cheat_silent', 'cheat_rally_no_decay', 'cheat_enemy_control',
             'effect_chromatic_aberration', 'effect_dof', 'effect_motion_blur',
             'effect_ssao', 'effect_game_aa', 'effect_dynamic_shadows', 'effect_ssr'}
NUMBERS = {'preset': (0, 4), 'xess_preset': (0, 6), 'real_fps_limit': (-1, 1000),
           'frame_cap': (0, 1000), 'generated_fps_limit': (30, 1000),
           'nvidia_generated_frames': (1, 5), 'frames_ahead': (0, 16),
           'sharpness': (0, 1), 'model_lod': (-2, 2),
           'cheat_damage': (1, 16), 'cheat_incoming': (1, 16),
           'cheat_echoes': (1, 16), 'cheat_movement': (1, 16)}
ENV_KEYS = {'BB_DRAW_PIPE', 'BB_PREP_WORKERS', 'BB_VK_RECORD_THREAD', 'BB_COPY_THREADS',
            'BB_FRAME_STATS', 'BB_GPU_PROFILE', 'BB_READBACKS', 'BB_OBJECT_MOTION',
            'BB_UPSCALER', 'BB_GPU_ID', 'BB_FPS_LIMIT', 'BB_FRAMES_AHEAD'}
PRIVATE_KEY = re.compile(r'(?i)(?:password|passwd|pwd|secret|token|authorization|'
                         r'api[ _-]?key|cookie|credential|npid|account|steam[ _-]?id|'
                         r'user[ _-]?(?:name|id)|player[ _-]?name|session[ _-]?id|sid)')


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def settings_whitelist(values):
    if not isinstance(values, dict):
        return {}
    result = {}
    for key, value in values.items():
        if not isinstance(value, (str, bool, int, float)):
            continue
        text = str(value)
        if key in ENUMS and text in ENUMS[key]:
            result[key] = value
        elif key in BOOL_KEYS and (type(value) is bool or text in ('0', '1')):
            result[key] = value
        elif key in NUMBERS:
            try:
                number = float(value)
            except (ValueError, OverflowError):
                continue
            low, high = NUMBERS[key]
            if math.isfinite(number) and low <= number <= high:
                result[key] = value
        elif key == 'output_res' and re.fullmatch(r'\d{3,5}x\d{3,5}', text):
            result[key] = value
    return result


class Redactor:
    def __init__(self, paths=(), identities=()):
        self.paths = sorted({str(p).rstrip('/\\') for p in paths if p}, key=len, reverse=True)
        self.identities = sorted({str(v) for v in identities if v and not str(v).isdecimal()},
                                 key=len, reverse=True)

    def text(self, text):
        text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', str(text))
        text = ''.join(c for c in text if c in '\n\r\t' or ord(c) >= 32)
        text = re.sub(r'-----BEGIN [^-]*(?:PRIVATE KEY|CERTIFICATE)-----.*?'
                      r'-----END [^-]+-----', '[private block removed]', text, flags=re.S)
        lines, private_continuation = [], False
        for line in text.splitlines():
            # Omit whole credential-bearing records, including continued JSON
            # or header values. Do not try to preserve part of an auth exchange.
            if PRIVATE_KEY.search(line):
                lines.append('[sensitive log record removed]')
                private_continuation = True
                continue
            if private_continuation:
                if not re.match(r'^(?:\[[\d.: T+\-]+s?\]|Runtime:|GPU[_ :]|VideoOut:|'
                                r'FrameStats:|Frames:|Process exited|Output |Patches:)', line):
                    lines.append('[sensitive continuation removed]')
                    continue
                private_continuation = False
            for path in self.paths:
                # Consume the remainder too: a folder/name beneath a known
                # root can still contain personal information.
                line = re.sub(re.escape(path) + r'(?:[\\/][^\r\n"\'<>|]*)?',
                              '[path]', line, flags=re.I)
            line = re.sub(r'(?i)(?:\\\\\?\\)?[a-z]:[\\/][^\r\n"\'<>|]*', '[path]', line)
            line = re.sub(r'\\\\[^\s\\/]+[\\/][^\r\n"\'<>|]*', '[network path]', line)
            line = re.sub(r'(?<!\w)/(?:home|Users|mnt|media|tmp|workspace|opt|var|srv|data)/'
                          r'[^\r\n"\'<>|]*', '[path]', line, flags=re.I)
            line = re.sub(r'(?i)\b(?:https?|ftp|file)://[^\s<>"\']+', '[URL]', line)
            line = re.sub(r'(?i)\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b', '[email]', line)
            line = re.sub(r'\bS-1-\d+(?:-\d+){2,}\b', '[account]', line)
            line = re.sub(r'\b7656119\d{10}\b', '[account]', line)
            line = re.sub(r'(?i)\b(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}\b', '[address]', line)
            line = re.sub(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', self._ip, line)
            for identity in self.identities:
                line = re.sub(r'(?<!\w)' + re.escape(identity) + r'(?!\w)', '[private]', line, flags=re.I)
            lines.append(line)
        return '\n'.join(lines) + ('\n' if text.endswith('\n') else '')

    @staticmethod
    def _ip(match):
        try:
            ipaddress.ip_address(match[0])
        except ValueError:
            return match[0]
        return '[address]'

    def value(self, value):
        if isinstance(value, str):
            if re.fullmatch(r'\d+(?:\.\d+)+', value):
                return value  # Driver/OS version, supplied only by whitelisted fields.
            return self.text(value)[:1024]
        if isinstance(value, dict):
            return {k: self.value(v) for k, v in value.items() if not PRIVATE_KEY.search(str(k))}
        if isinstance(value, list):
            return [self.value(v) for v in value[:100]]
        if value is None or type(value) in (bool, int):
            return value
        if type(value) is float and math.isfinite(value):
            return value
        return None


def _regular(path):
    try:
        info = path.lstat()
        return stat.S_ISREG(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400
    except OSError:
        return False


def _directory(path):
    try:
        info = path.lstat()
        return stat.S_ISDIR(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400
    except OSError:
        return False


def _read(path, maximum, tail=False):
    if not _regular(path):
        return None
    try:
        with path.open('rb') as file:
            size = os.fstat(file.fileno()).st_size
            if not tail and size > maximum:
                return None
            if tail and size > maximum:
                head_size = min(96 * 1024, maximum // 4)
                head = file.read(head_size)
                file.seek(max(size - maximum + head_size, 0))
                return head + b'\n[older log content omitted]\n' + file.read(maximum - head_size)
            return file.read(maximum)
    except OSError:
        return None


def _read_json(path):
    data = _read(path, MAX_JSON)
    if data is None:
        return None
    try:
        value = json.loads(data.decode('utf-8-sig'), parse_constant=lambda _x: None)
        return value if isinstance(value, dict) else None
    except (UnicodeError, ValueError, RecursionError):
        return None


def detect_system(include_profile=False):
    """Local fixed-field queries; no serials, accounts, registry IDs or network requests."""
    result = {'os': {'system': 'Windows' if os.name == 'nt' else os.name}, 'gpus': []}
    if hasattr(__import__('sys'), 'getwindowsversion'):
        version = __import__('sys').getwindowsversion()
        result['os'].update(version=f'{version.major}.{version.minor}', build=version.build)
    if os.name != 'nt':
        return result
    shell = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    script = "$ErrorActionPreference='Stop';[Console]::OutputEncoding=[Text.UTF8Encoding]::new();"
    script += "$o=Get-CimInstance Win32_OperatingSystem;"
    script += "$g=@(Get-CimInstance Win32_VideoController|ForEach-Object{"
    script += "@{model=$_.Name;driver_version=$_.DriverVersion}});"
    script += "$r=@{os=@{name=$o.Caption;version=$o.Version;build=$o.BuildNumber};gpus=$g};"
    if include_profile:
        script += "$c=Get-CimInstance Win32_Processor;$s=Get-CimInstance Win32_ComputerSystem;"
        script += "$r.hardware_profile=@{cpu_model=@($c|ForEach-Object{$_.Name});"
        script += "logical_processors=$s.NumberOfLogicalProcessors;ram_gib=[Math]::Round($s.TotalPhysicalMemory/1GB)};"
    script += '$r|ConvertTo-Json -Depth 4 -Compress'
    try:
        completed = subprocess.run([str(shell), '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', script],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                   timeout=12, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if completed.returncode == 0 and len(completed.stdout) <= MAX_JSON:
            raw = json.loads(completed.stdout.decode('utf-8-sig'))
            if isinstance(raw, dict):
                result = system_whitelist(raw, include_profile)
    except (OSError, subprocess.TimeoutExpired, ValueError, UnicodeError, RecursionError):
        result['query_status'] = 'unavailable'
    return result


def system_whitelist(raw, include_profile=False):
    if not isinstance(raw, dict):
        raw = {}
    os_data = raw.get('os') if isinstance(raw.get('os'), dict) else {}
    result = {'os': {k: v for k, v in os_data.items() if k in ('system', 'name', 'version', 'build')
                     and type(v) in (str, int)}, 'gpus': []}
    gpus = raw.get('gpus', [])
    if isinstance(gpus, list):
        for gpu in gpus[:8]:
            if isinstance(gpu, dict):
                result['gpus'].append({k: v for k, v in gpu.items() if k in ('model', 'driver_version')
                                       and isinstance(v, str)})
    if include_profile and isinstance(raw.get('hardware_profile'), dict):
        result['hardware_profile'] = {k: v for k, v in raw['hardware_profile'].items()
                                      if k in ('cpu_model', 'logical_processors', 'ram_gib')}
    return result


def _session_metadata(raw):
    result = {k: raw[k] for k in ('revision', 'started', 'status', 'exit_code', 'duration_seconds',
                                  'geometry_diagnostic') if k in raw and type(raw[k]) in (str, int, float)}
    for key in ('settings', 'ini', 'menu_at_start', 'menu_at_exit'):
        if key in raw:
            result[key] = settings_whitelist(raw[key])
    if isinstance(raw.get('renderer_environment'), dict):
        result['renderer_environment'] = {k: v for k, v in raw['renderer_environment'].items()
                                           if k in ENV_KEYS and isinstance(v, str)
                                           and (v in ENUMS['upscaler'] if k == 'BB_UPSCALER' else
                                                bool(re.fullmatch(r'-?\d{1,4}', v)) and -1 <= int(v) <= 1000)}
    return result


def build_identity_whitelist(raw):
    if not isinstance(raw, dict):
        return {}
    safe = {}
    for key in ('project', 'version', 'revision', 'launcher_version', 'source_commit', 'source_tree',
                'build_type', 'architecture', 'compiler', 'channel', 'upstream_version'):
        if key in raw and type(raw[key]) in (str, int):
            safe[key] = raw[key]
    # Hashes are useful, but never include the build's absolute input paths.
    for key in ('files', 'sha256', 'binaries', 'executables', 'runtime_files'):
        if isinstance(raw.get(key), dict):
            hashes = {}
            for name, value in raw[key].items():
                digest = value.get('sha256') if isinstance(value, dict) else value
                if isinstance(digest, str) and re.fullmatch('[a-fA-F0-9]{64}', digest):
                    basename = str(name).replace('\\', '/').rsplit('/', 1)[-1]
                    if basename in ('Bloodborne.exe', 'Play Bloodborne.exe', 'bb-probe.exe',
                                    'bb-play.exe', 'bb-gpu-capabilities.exe', 'nvngx_dlss.dll',
                                    'sl.interposer.dll', 'sl.dlss_g.dll', 'sl.reflex.dll', 'libxess.dll'):
                        hashes[basename] = digest.lower()
            if hashes:
                safe.setdefault('binary_sha256', {}).update(hashes)
    return safe


def hardware_submission(system, revision, settings):
    """A player's submission is unreviewed even if the player reports successful play."""
    return {'schema_version': 1, 'project': 'Bloodborne: The Crowned Workshop',
            'port_revision': revision, 'hardware': system, 'settings': settings,
            'status': 'unverified', 'reviewed': False,
            'evidence': {'kind': 'not-provided', 'gameplay_minutes': None, 'scene': '',
                         'result': 'not-provided', 'reference': ''}}


def validate_hardware_submission(raw):
    if not isinstance(raw, dict) or raw.get('schema_version') != 1:
        raise ValueError('Unsupported hardware submission format.')
    if raw.get('reviewed') is not False or raw.get('status') != 'unverified':
        raise ValueError('Player submissions must remain unreviewed and unverified.')
    evidence = raw.get('evidence')
    if not isinstance(evidence, dict) or evidence.get('kind') not in ('not-provided', 'gameplay-report'):
        raise ValueError('Hardware evidence must describe actual gameplay or remain absent.')
    return True


@dataclass(frozen=True)
class SupportReport:
    entries: dict
    warnings: tuple

    @property
    def summary(self):
        return self.entries['report-summary.md'].decode('utf-8')


def build_report(port_dir, user_dir, settings, ini, menu, revision, *, include_logs=True,
                 include_profile=False, system=None):
    port, user = Path(port_dir).resolve(), Path(user_dir).resolve()
    sensitive_values = [v for k, v in settings.items() if PRIVATE_KEY.search(str(k))]
    paths = [port, user, Path.home(), *[settings.get(k) for k in ('game_dir', 'mods_dir', 'patches_dir')],
             *[os.environ.get(k) for k in ('USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'TEMP')]]
    identities = sensitive_values + [os.environ.get('USERNAME'), os.environ.get('USER')]
    redactor = Redactor(paths, identities)
    entries, warnings, logs, sessions = {}, [], [], []
    current = {'launcher': settings_whitelist(settings), 'image': settings_whitelist(ini),
               'menu': settings_whitelist(menu)}
    diagnostic = user / 'diagnostics'
    if _directory(diagnostic):
        folders = []
        for folder in list(diagnostic.iterdir())[:1000]:
            try:
                st = folder.lstat()
                if stat.S_ISDIR(st.st_mode) and not getattr(st, 'st_file_attributes', 0) & 0x400:
                    folders.append((st.st_mtime_ns, folder))
            except OSError:
                pass
        for index, (_time, folder) in enumerate(sorted(folders, reverse=True)[:MAX_SESSIONS], 1):
            prefix = f'sessions/session-{index}'
            raw = _read_json(folder / 'session.json')
            if raw is not None:
                metadata = redactor.value(_session_metadata(raw))
                entries[prefix + '/session.json'] = json_bytes(metadata)
                sessions.append(metadata)
            elif (folder / 'session.json').exists():
                warnings.append(f'{prefix}: session metadata unavailable or malformed.')
            if include_logs:
                data = _read(folder / 'session.log', MAX_LOG, tail=True)
                if data is not None:
                    cleaned = redactor.text(data.decode('utf-8', errors='replace'))
                    entries[prefix + '/session.log'] = cleaned.encode('utf-8')
                    logs.append((prefix, cleaned))
    if include_logs:
        data = _read(user / 'last_run.log', MAX_LOG, tail=True)
        if data is not None:
            cleaned = redactor.text(data.decode('utf-8', errors='replace'))
            entries['logs/last_run.log'] = cleaned.encode('utf-8')
            logs.append(('last_run', cleaned))
        if not logs:
            warnings.append('No recent session logs were available. Profiling does not need to be enabled to export this report.')
    detected = system_whitelist(system if system is not None else detect_system(include_profile), include_profile)
    detected = redactor.value(detected)
    active = {'backend': 'Vulkan', 'source': 'port implementation', 'gpu': None, 'driver': None,
              'upscaler': None, 'frame_generation': None}
    # Startup GPU lines precede the later timings. Prefer the newest session's
    # actual selected Vulkan device over WMI's unordered list of adapters.
    for _source, log in logs:
        for key, pattern in [('gpu', r'GPU_Model:\s*([^\r\n]+)'),
                             ('driver', r'GPU_Vulkan_Driver:\s*([^\r\n]+)'),
                             ('upscaler', r'Upscaler:\s*([^\r\n]+)'),
                             ('frame_generation', r'(?:Frame generation|Frame Generation):\s*([^\r\n]+)')]:
            match = re.search(pattern, log)
            if active[key] is None and match:
                active[key] = match[1].strip()[:200]
        if active['gpu']:
            active['source'] = 'latest available session log'
            break
    observations = []
    for source, log in logs:
        for number, line in enumerate(log.splitlines(), 1):
            if re.search(r'(?i)framestats|frame stats|frames:|\bfps\b|frametime|latency|'
                         r'GPU profile|VideoOut:|GPU time|\bp99\b|queue.*(?:wait|ms)', line):
                observations.append({'source': source, 'line': number, 'text': line[:2048]})
    entries['performance.json'] = json_bytes({'schema_version': 1, 'observations': observations[-500:],
                                              'note': 'Existing diagnostic measurements; no new profiling run.'})
    identity = redactor.value(build_identity_whitelist(_read_json(port / 'BUILD-IDENTITY.json')))
    if identity:
        entries['build-identity.json'] = json_bytes(identity)
    else:
        warnings.append('Build identity unavailable; the launcher revision is included.')
    report = {'schema_version': 1, 'project': 'Bloodborne: The Crowned Workshop',
              'generated_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
              'port_revision': redactor.text(revision)[:80], 'system': detected,
              'renderer': active, 'selected_settings': current,
              'sessions': sessions, 'warnings': warnings,
              'privacy': {'logs_included': include_logs, 'optional_hardware_profile': include_profile,
                          'excluded': ['credentials', 'account identifiers', 'game files', 'saves',
                                       'raw memory dumps', 'frame captures', 'arbitrary environment variables'],
                          'sharing': 'local inspection and manual attachment only'}}
    entries['report.json'] = json_bytes(report)
    if include_profile:
        submission = hardware_submission(detected, report['port_revision'], current)
        validate_hardware_submission(submission)
        entries['hardware-submission.json'] = json_bytes(submission)
    gpu = active['gpu'] or ', '.join(g.get('model', 'Unknown') for g in detected['gpus']) or 'Unavailable'
    driver = active['driver'] or ', '.join(g.get('driver_version', 'Unknown') for g in detected['gpus']) or 'Unavailable'
    selected = {**current['launcher'], **current['image'], **current['menu']}
    fields = ('output_res', 'upscaler', 'preset', 'xess_preset', 'dlss_preset', 'frame_generation',
              'nvidia_generated_frames', 'real_fps_limit', 'limit_generated_fps', 'generated_fps_limit',
              'hdr', 'window_mode', 'present_mode', 'background_mode', 'reflex', 'amd_antilag')
    summary = f"# The Crowned Workshop support report\n\nRevision: {report['port_revision']}\nGPU: {gpu}\nDriver: {driver}\n"
    summary += 'Windows / OS: ' + json.dumps(detected['os'], ensure_ascii=False) + '\n\n'
    summary += '\n'.join(f'- {k}: {selected[k]}' for k in fields if k in selected)
    summary += '\n\nDescribe the scene, reproduction steps and expected/actual behavior in the issue.\n'
    summary += 'Review the sanitized files before attaching the ZIP. Hardware submissions await gameplay-evidence review.\n'
    entries['report-summary.md'] = summary.encode('utf-8')
    manifest = {'schema_version': 1, 'kind': 'crowned-workshop-support-report',
                'files': [{'path': name, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                          for name, data in sorted(entries.items())]}
    entries['manifest.json'] = json_bytes(manifest)
    return SupportReport(entries, tuple(warnings))


def verify_report(path):
    with zipfile.ZipFile(path) as archive:
        items = archive.infolist()
        names = [i.filename for i in items]
        if len(items) > 20 or len(set(names)) != len(names) or 'manifest.json' not in names:
            raise ValueError('Invalid support archive file list.')
        if any(not REPORT_FILES.fullmatch(i.filename) or i.file_size > MAX_REPORT or
               stat.S_ISLNK(i.external_attr >> 16) for i in items) or sum(i.file_size for i in items) > MAX_REPORT:
            raise ValueError('Unexpected or oversized support archive entry.')
        manifest = json.loads(archive.read('manifest.json'))
        if manifest.get('schema_version') != 1 or manifest.get('kind') != 'crowned-workshop-support-report':
            raise ValueError('Invalid support archive manifest.')
        records = manifest.get('files', [])
        if not isinstance(records, list) or {r['path'] for r in records} != set(names) - {'manifest.json'} or len(records) != len(names) - 1:
            raise ValueError('Incomplete support archive.')
        for record in records:
            data = archive.read(record['path'])
            if len(data) != record['size'] or hashlib.sha256(data).hexdigest() != record['sha256']:
                raise ValueError('Support archive checksum mismatch.')
    return True


def export_report(report, destination):
    """Verify a temporary ZIP before the atomic replacement; interruptions keep the old file."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.support-report-', suffix='.partial', dir=destination.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'w+b') as file:
            with zipfile.ZipFile(file, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                for path, data in report.entries.items():
                    if not REPORT_FILES.fullmatch(path):
                        raise ValueError('Unexpected support report entry.')
                    archive.writestr(path, data)
            file.flush()
            os.fsync(file.fileno())
        verify_report(temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination
