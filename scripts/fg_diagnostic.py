# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Package an explicitly requested NVIDIA FG capture after the game closes."""
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import zipfile

from support_report import (Redactor, build_identity_whitelist, detect_system,
                            json_bytes, settings_whitelist)

BUDGET = 256 * 1024 * 1024
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


def export_capture(directory, port, metadata):
    directory, port = Path(directory), Path(port)
    frames = directory / 'fg-inputs'
    archive = directory / 'NVIDIA-FG-diagnostic.zip'
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
    if not raw_files:
        return {'status': 'no_frames', 'complete_frames': 0, 'warnings': warnings}
    redactor = Redactor(paths=(directory, port, Path.home(), os.environ.get('APPDATA'),
                              os.environ.get('LOCALAPPDATA')),
                        identities=(os.environ.get('USERNAME'), os.environ.get('USER')))
    settings = {}
    for key in ('settings', 'ini', 'menu_at_start', 'menu_at_exit'):
        settings.update(settings_whitelist(metadata.get(key)))
    summary = {'schema': 1, 'revision': metadata.get('revision', 'unknown'),
               'mode': metadata.get('nvidia_diagnostic'), 'complete_frames': complete,
               'requested_frames': requested, 'status': 'captured' if complete == requested else 'incomplete',
               'raw_bytes': total, 'settings': settings, 'warnings': warnings,
               'limitations': ['Readback can affect timing.',
                   'real_color is the actual backbuffer before interpolation, not a generated frame.',
                   'The generated-only display comparison is temporary and is not a normal FPS benchmark.']}
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
        'Private NVIDIA FG diagnostic. Inspect before sharing; nothing was uploaded.\n'
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
                'requested_frames': requested, 'raw_bytes': total, 'warnings': warnings}
    except (OSError, zipfile.BadZipFile, RuntimeError):
        temporary.unlink(missing_ok=True)
        return {'status': 'archive_failed', 'complete_frames': complete, 'warnings': warnings}
