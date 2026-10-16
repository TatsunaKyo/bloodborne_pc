# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Package a requested traversal trace, with NVIDIA images when available."""
import hashlib
import json
import math
import os
import re
from pathlib import Path
import stat
import zipfile

from support_report import (Redactor, build_identity_whitelist, detect_system,
                            json_bytes, settings_whitelist)

BUDGET = 256 * 1024 * 1024
TIMELINE_BUDGET = 16 * 1024 * 1024
SCALARS = {'schema', 'capture_frame', 'requested_frames', 'submission_frame', 'generated_frames',
           'raw_bytes', 'render_width', 'render_height', 'output_width', 'output_height',
           'tagged_color_width', 'tagged_color_height', 'color_vulkan_format', 'reset',
           'near_plane', 'vertical_fov', 'far_plane', 'depth_inverted', 'camera_motion_included'}
ARRAYS = {'jitter': 2, 'motion_scale': 2, 'view': 12, 'inverse_view': 12, 'previous_view': 12,
          'previous_inverse_view': 12, 'projection': 4, 'previous_projection': 4,
          'view_to_clip': 16, 'clip_to_view': 16, 'clip_to_previous': 16, 'previous_to_clip': 16}


def regular(path, maximum):
    try:
        info = path.lstat()
        return stat.S_ISREG(info.st_mode) and info.st_size <= maximum
    except OSError:
        return False


def read_json(path):
    if not regular(path, 64 * 1024):
        return {}
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, UnicodeError, RecursionError):
        return {}


def frame_metadata(raw, index):
    if raw.get('schema') != 1 or raw.get('stage') != 'nvidia_tagged_inputs':
        return None
    safe = {key: value for key, value in raw.items() if key in SCALARS
            and type(value) in (int, float, bool) and math.isfinite(value)}
    for key, size in ARRAYS.items():
        values = raw.get(key)
        if not isinstance(values, list) or len(values) != size or any(
                type(v) not in (float, int) or not math.isfinite(v) for v in values):
            return None
        safe[key] = values
    if safe.get('capture_frame') != index or not 1 <= safe.get('requested_frames', 0) <= 4:
        return None
    for key in ('render_width', 'render_height', 'output_width', 'output_height'):
        if type(safe.get(key)) is not int or not 1 <= safe[key] <= 32768:
            return None
    if safe.get('color_vulkan_format') not in (37, 43, 44, 50, 58, 64):
        return None
    safe.update(stage='nvidia_tagged_inputs', depth_format='r32f', motion_format='rg16f',
                matrix_layout='row_major')
    return safe


def cpu_timeline(path, redactor, warnings):
    """Keep complete bounded records after interruption; never export arbitrary fields."""
    info = {'status': 'missing', 'windows': 0, 'events': 0}
    if not path.exists() and not path.is_symlink():
        return None, info
    if not regular(path, TIMELINE_BUDGET):
        warnings.append('CPU timeline linked or over budget; omitted.')
        return None, {**info, 'status': 'rejected'}
    records, partial, size = [], False, 0

    def integers(raw, names):
        if any(type(raw.get(k)) is not int or not 0 <= raw[k] < 2**64 for k in names):
            raise ValueError('Invalid timeline number')
        return {k: raw[k] for k in names}

    def address(raw, key):
        value = raw.get(key)
        if not isinstance(value, str) or not re.fullmatch(r'0x[0-9a-fA-F]{1,16}', value):
            raise ValueError('Invalid timeline address')
        return value

    def label(raw, key, maximum):
        value = raw.get(key)
        if not isinstance(value, str) or len(value) > maximum:
            raise ValueError('Invalid timeline label')
        return value

    try:
        with path.open('rb') as stream:
            for line in stream:
                if not line.strip():
                    continue
                try:
                    raw = json.loads(line)
                    if not isinstance(raw, dict):
                        raise ValueError('Invalid timeline record')
                    kind = raw.get('record')
                    count = 0
                    if kind == 'clock':
                        safe = {'record': kind, **integers(raw, ('schema', 'steady_ns', 'qpc', 'qpc_hz', 'pid', 'maximum_bytes')),
                                'module_base': address(raw, 'module_base'), 'window_limited': True}
                        if safe['schema'] != 1:
                            raise ValueError('Unknown timeline schema')
                    elif kind == 'window':
                        safe = {'record': kind, **integers(raw, ('begin_ns', 'end_ns', 'lost', 'dropped_windows', 'collisions')),
                                'phase': label(raw, 'phase', 80), 'truncated': raw.get('truncated') is True, 'events': []}
                        if safe['end_ns'] < safe['begin_ns'] or not isinstance(raw.get('events'), list):
                            raise ValueError('Invalid timeline window')
                        if len(raw['events']) > 16384:
                            safe['truncated'] = True
                        for event in raw['events'][:16384]:
                            try:
                                if not isinstance(event, dict):
                                    raise ValueError('Invalid event')
                                item = {**integers(event, ('thread', 'os_thread', 'start_ns', 'end_ns', 'bytes', 'id', 'depends_on')),
                                        'stage': label(event, 'stage', 200), 'role': label(event, 'role', 80),
                                        'address': address(event, 'address')}
                                if item['end_ns'] < item['start_ns']:
                                    raise ValueError('Invalid event span')
                                safe['events'].append(item)
                            except (ValueError, TypeError):
                                safe['truncated'] = True
                        count = len(safe['events'])
                        partial |= safe['truncated'] or any(safe[k] for k in ('lost', 'dropped_windows', 'collisions'))
                    elif kind == 'limit':
                        safe = {'record': 'limit', 'reason': '16 MiB limit'}
                        partial = True
                    else:
                        raise ValueError('Unknown timeline record')
                    encoded = (json.dumps(redactor.value(safe), ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')
                    if size + len(encoded) > TIMELINE_BUDGET:
                        partial = True
                        break
                    records.append(encoded); size += len(encoded)
                    info['windows'] += int(kind == 'window')
                    info['events'] += count
                except (ValueError, TypeError, UnicodeError, RecursionError):
                    partial = True
    except OSError:
        partial = True
    if partial:
        warnings.append('CPU timeline incomplete: interrupted, bounded or dropped records; valid records retained.')
    info['status'] = 'incomplete' if partial else 'captured' if info['windows'] else 'empty'
    return b''.join(records) or None, info


def export_capture(directory, port, metadata):
    directory, port = Path(directory), Path(port)
    frames = directory / 'fg-inputs'
    nvidia = bool(metadata.get('nvidia_diagnostic'))
    archive = directory / ('NVIDIA-FG-diagnostic.zip' if nvidia else 'Traversal-diagnostic.zip')
    temporary = archive.with_suffix('.tmp')
    records, raw_files, warnings = {}, {}, []
    complete, total, requested = 0, 0, 0
    for index in range(4):
        path = frames / f'fg{index}.json'
        if not path.exists():
            continue
        record = frame_metadata(read_json(path), index)
        if record is None:
            warnings.append(f'Frame {index}: invalid or incomplete metadata.')
            continue
        requested = max(requested, record['requested_frames'])
        valid = True
        for kind in ('depth', 'motion', 'real_color'):
            width, height = ((record['output_width'], record['output_height']) if kind == 'real_color'
                             else (record['render_width'], record['render_height']))
            size = width * height * 4
            file = frames / f'fg{index}_{kind}_{width}x{height}.raw'
            if not regular(file, min(size, BUDGET - total)) or file.stat().st_size != size:
                warnings.append(f'Frame {index}: {kind} missing, truncated, linked or over budget.')
                valid = False
                continue
            raw_files['fg-inputs/' + file.name] = (file, size)
            total += size
        complete += int(valid)
        records[f'fg-inputs/fg{index}.json'] = json_bytes(record)
    redactor = Redactor(paths=(directory, port, Path.home(), os.environ.get('APPDATA'),
                              os.environ.get('LOCALAPPDATA')),
                        identities=(os.environ.get('USERNAME'), os.environ.get('USER')))
    settings = {}
    for key in ('settings', 'ini', 'menu_at_start', 'menu_at_exit'):
        settings.update(settings_whitelist(metadata.get(key)))
    summary = {'schema': 1, 'revision': metadata.get('revision', 'unknown'),
               'mode': metadata.get('nvidia_diagnostic') or 'traversal', 'complete_frames': complete,
               'requested_frames': requested or (4 if nvidia else 0),
               'status': ('captured' if complete and complete == requested else
                          'incomplete' if raw_files else 'logs_only'),
               'image_capture_status': ('captured' if complete else
                                        'no_frames' if nvidia else 'not_requested'),
               'raw_bytes': total, 'settings': settings, 'warnings': warnings,
               'limitations': ['CPU traversal tracing works with frame generation on or off.',
                   'A logs_only archive contains no captured gameplay images.',
                   'Readback can affect timing.',
                   'real_color is the actual backbuffer before interpolation, not a generated frame.',
                   'The generated-only display comparison is temporary and is not a normal FPS benchmark.']}
    trace = metadata.get('cpu_hitch_trace', {})
    if isinstance(trace, dict):
        summary['cpu_hitch_trace'] = {key: trace[key] for key in (
            'enabled', 'ring_events', 'gpu_timestamp_profiler', 'normal_renderer_preserved',
            'causal_timeline', 'timeline_maximum_bytes')
            if type(trace.get(key)) in (bool, int)}
    timeline, summary['cpu_timeline'] = cpu_timeline(directory / 'cpu-timeline.jsonl', redactor, warnings)
    if timeline:
        records['cpu-timeline.jsonl'] = timeline
    records['session.json'] = json_bytes(redactor.value(summary))
    records['system.json'] = json_bytes(redactor.value(detect_system(False)))
    records['build-identity.json'] = json_bytes(redactor.value(
        build_identity_whitelist(read_json(port / 'BUILD-IDENTITY.json'))))
    log = directory / 'session.log'
    if regular(log, 128 * 1024 * 1024):
        with log.open('rb') as stream:
            stream.seek(max(0, log.stat().st_size - 4 * 1024 * 1024))
            records['session.log'] = redactor.text(stream.read().decode('utf-8', errors='replace')).encode()
    records['READ-ME.txt'] = (
        'Private renderer diagnostic. Inspect before sharing; nothing was uploaded.\n'
        'Traversal CPU logs are useful independently of FG and do not require F8.\n'
        'cpu-timeline.jsonl contains bounded CPU windows, native thread IDs, resource addresses and request links.\n'
        'Windows include a steady-clock/QPC anchor. Nested spans overlap; bytes are whole operations.\n'
        'This is not CPU sampling, a context-switch trace or displayed-frame timestamp measurement.\n'
        'No resource contents are stored in the CPU timeline. Interrupted captures retain complete records.\n'
        'If status is logs_only, no image readbacks were available.\n'
        'The binary images are explicitly requested gameplay readbacks, not game/save files.\n'
        'Camera constants and image dimensions belong to the same NVIDIA-tagged submission.\n'
        'Depth: one little-endian float32 per pixel. Motion: two little-endian float16s per pixel,\n'
        'in render pixels, previous minus current. Color uses color_vulkan_format in fgN.json.\n'
        'Logs/settings/system/build records use the existing support-report redaction.\n').encode()
    try:
        hashes = {}
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
            for name, data in sorted(records.items()):
                bundle.writestr(name, data)
                hashes[name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
            for name, (file, size) in sorted(raw_files.items()):
                digest = hashlib.sha256()
                written = 0
                with file.open('rb') as source, bundle.open(name, 'w', force_zip64=True) as target:
                    while chunk := source.read(1024 * 1024):
                        written += len(chunk)
                        if written > size:
                            raise OSError('Readback changed during export.')
                        digest.update(chunk)
                        target.write(chunk)
                if written != size:
                    raise OSError('Readback was interrupted during export.')
                hashes[name] = {'bytes': written, 'sha256': digest.hexdigest()}
            bundle.writestr('archive-integrity.json', json_bytes(hashes))
        with zipfile.ZipFile(temporary) as bundle:
            if bundle.testzip() is not None:
                raise OSError('Capture archive failed its CRC check.')
        temporary.replace(archive)
        return {'status': summary['status'], 'archive': archive.name, 'complete_frames': complete,
                'image_capture_status': summary['image_capture_status'],
                'requested_frames': summary['requested_frames'], 'raw_bytes': total, 'warnings': warnings}
    except (OSError, zipfile.BadZipFile, RuntimeError):
        temporary.unlink(missing_ok=True)
        return {'status': 'archive_failed', 'complete_frames': complete, 'warnings': warnings}
