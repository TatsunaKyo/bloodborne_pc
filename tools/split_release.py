# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Separate developer records from a complete package without removing runtime dependencies."""
import argparse
import json
from pathlib import Path, PurePosixPath
import zipfile

from release_integrity import checksum, package_name, safe_member, validate, validate_developer, require

LAUNCHER_SOURCE = 'source/modified-files/launcher/bbport_launcher_win.py'
SOURCE_PATCH = 'source/tatsunakyo-revision.patch'
DIAGNOSTICS = {'Start-Verified-Launcher.cmd', 'Diagnose-Geometry-Normal.cmd',
               'Diagnose-Geometry-Serial.cmd', 'Capture-Flashing-Assets.cmd'}


def developer_file(name):
    return ((name.startswith('source/') and name not in (LAUNCHER_SOURCE, SOURCE_PATCH))
            or name.startswith('.github/') or name in DIAGNOSTICS
            or (name.startswith('bin/') and name.endswith('-test.exe')))


def write_zip(path, root, entries):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, data in sorted(entries.items()):
            safe_member(name)
            entry = zipfile.ZipInfo(str(PurePosixPath(root) / name))
            entry.create_system = 0; entry.external_attr = 0x20
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, data)
    with zipfile.ZipFile(path) as archive:
        require(archive.testzip() is None, 'Exported ZIP failed its CRC check')
    path.with_suffix('.zip.sha256').write_text(checksum(path) + '  ' + path.name + '\n')


def diagnostic_wrapper(name, original, version, runtime_root):
    prefix = ('@echo off\nsetlocal\nset "WORKSHOP_PORT=%~1"\n'
              f'if not defined WORKSHOP_PORT set "WORKSHOP_PORT=%~dp0..\\..\\{runtime_root}"\n'
              'if not exist "%WORKSHOP_PORT%\\Bloodborne.exe" (\n'
              '  echo Pass your game installation folder as the first argument.\n'
              f'  echo Example: {name} "D:\\The Crowned Workshop"\n'
              '  pause\n  exit /b 1\n)\ncd /d "%WORKSHOP_PORT%"\n')
    body = original.decode('utf-8').replace('\r\n', '\n')
    body = body.replace('@echo off\n', '').replace('setlocal\n', '')
    body = body.replace('cd /d "%~dp0"\n', '')
    body = body.replace('"%~dp0Bloodborne.exe"', '"%WORKSHOP_PORT%\\Bloodborne.exe"')
    body = body.replace('Starting Revision 17', 'Starting ' + version)
    return (prefix + body).replace('\n', '\r\n').encode('utf-8')


def split(package, destination, *, repo=None):
    package, destination = Path(package), Path(destination)
    report = validate(package, repo=repo)
    version = report['version']; runtime_root = report['root']
    destination.mkdir(parents=True, exist_ok=True)
    runtime = destination / package_name(version)
    developer = destination / (runtime.stem + '-Developer.zip')
    for path in (runtime, developer, runtime.with_suffix('.zip.sha256'), developer.with_suffix('.zip.sha256')):
        require(not path.exists(), 'Output already exists; keep the earlier package: ' + str(path))
    regular, development, original_files = {}, {}, {}
    with zipfile.ZipFile(package) as archive:
        for entry in archive.infolist():
            if entry.is_dir(): continue
            name = str(PurePosixPath(entry.filename).relative_to(runtime_root))
            data = archive.read(entry)
            original_files[name] = data
            if name in DIAGNOSTICS:
                development['diagnostics/originals/' + name + '.txt'] = data
                development['diagnostics/' + name] = diagnostic_wrapper(name, data, version, runtime_root)
            elif developer_file(name): development[name] = data
            else: regular[name] = data
    identity = json.loads(regular['BUILD-IDENTITY.json'])
    development['DEVELOPER-IDENTITY.json'] = (json.dumps({
        'project': identity.get('project', 'Bloodborne: The Crowned Workshop'),
        'version': version, 'source_commit': identity['source_commit'], 'source_tree': identity['source_tree'],
        'runtime_executables': {k: v for k, v in identity['executables'].items() if not developer_file(k)},
        'developer_executables': {k: v for k, v in identity['executables'].items() if developer_file(k)}}, indent=2) + '\n').encode()
    development['READ-ME-FIRST.txt'] = (
        'Bloodborne: The Crowned Workshop — TatsunaKyo developer tools\n\n'
        'I keep the source records, regression programs and specialist captures in this optional archive. '
        'The ordinary game ZIP contains every existing upscaler, Frame Generation runtime, launcher dependency, guide and license.\n\n'
        'Extract this folder beside the game folder. Run a diagnostic from diagnostics, or pass the game folder as its first argument. '
        'Keep the original scripts in diagnostics/originals for reference. Tests are under bin; add the game folder bin directory to PATH before running them. '
        'Some fixtures take arguments: their corresponding Python drivers are included under source/modified-files/tests. '
        'The Vulkan fixtures require a compatible GPU/driver. Source and verification records are under source. '
        'The complete revision patch remains in the game ZIP for existing updater and source verification compatibility.\n').encode()
    # Retain every original file byte-for-byte in at least one archive, except the
    # runtime identity, which records the new placement. Original scripts stay too.
    for name, data in original_files.items():
        if name == 'BUILD-IDENTITY.json': continue
        retained = (development['diagnostics/originals/' + name + '.txt'] if name in DIAGNOSTICS
                    else development[name] if developer_file(name) else regular[name])
        require(retained == data, 'A file changed or was lost during separation: ' + name)
    development['ORIGINAL-BUILD-IDENTITY.json'] = regular['BUILD-IDENTITY.json']
    identity['executables'] = {k: v for k, v in identity['executables'].items() if not developer_file(k)}
    try:
        write_zip(developer, runtime_root + '-Developer', development)
        identity['developer_bundle'] = {'filename': developer.name, 'sha256': checksum(developer),
                                         'source_commit': identity['source_commit'], 'optional_for_play': True}
        identity['package_layout'] = 'runtime-with-developer-companion-v1'
        regular['BUILD-IDENTITY.json'] = (json.dumps(identity, indent=2) + '\n').encode()
        write_zip(runtime, runtime_root, regular)
        runtime_report = validate(runtime, repo=repo, require_sidecar=True)
        validate_developer(developer, runtime_report, require_sidecar=True)
    except BaseException:
        # Only our new partial outputs are removed; the complete input is untouched.
        for path in (runtime, developer, runtime.with_suffix('.zip.sha256'), developer.with_suffix('.zip.sha256')):
            path.unlink(missing_ok=True)
        raise
    return {'runtime': str(runtime), 'runtime_sha256': checksum(runtime), 'runtime_bytes': runtime.stat().st_size,
            'developer': str(developer), 'developer_sha256': checksum(developer), 'developer_bytes': developer.stat().st_size,
            'source_files_preserved': len(original_files), 'runtime_files': len(regular),
            'developer_files': len(development), 'original_sha256': checksum(package)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--repo', type=Path)
    args = parser.parse_args()
    print(json.dumps(split(args.package, args.destination, repo=args.repo), indent=2))


if __name__ == '__main__': main()
