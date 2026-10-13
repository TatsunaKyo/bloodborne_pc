# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Validate a complete Windows package before preparing or publishing a release."""
import argparse
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat
import struct
import subprocess
import tempfile
import zipfile

VERSION_RE = re.compile(r'(\d+(?:\.\d+)*)-tatsunakyo\.(\d+)')
TAG_RE = re.compile(r'windows-v(\d+(?:\.\d+)*)-tatsunakyo\.(\d+)(?:-preview)?')
CORE = ('Bloodborne.exe', 'Play Bloodborne.exe', 'bin/bb-probe.exe', 'bin/bb-gpu-capabilities.exe')
DATA = ('run.py', 'bbport.menu.ini', 'README.md', 'LICENSE', 'scripts/patches.py')
RUNTIMES = ('bin/bbport_dlss.dll', 'bin/nvngx_dlss.dll', 'bin/xess/libxess.dll',
            'bin/streamline/sl.interposer.dll',
            'bin/streamline/sl.common.dll', 'bin/streamline/sl.dlss_g.dll',
            'bin/streamline/sl.reflex.dll', 'bin/streamline/sl.pcl.dll',
            'bin/streamline/NvLowLatencyVk.dll', 'bin/streamline/nvngx_dlssg.dll')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def version_parts(version):
    match = VERSION_RE.fullmatch(version) if isinstance(version, str) else None
    require(match, 'Invalid TatsunaKyo Windows version')
    return match[1], int(match[2])


def package_name(version):
    base, revision = version_parts(version)
    return f'Bloodborne-Windows-v{base}-TatsunaKyo-Revision-{revision}.zip'


def canonical_tag(version, channel):
    version_parts(version)
    require(channel in ('stable', 'preview'), 'Unknown release channel')
    return 'windows-v'+version+('-preview' if channel == 'preview' else '')


def checksum(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe_member(name):
    require(isinstance(name, str) and name and '\\' not in name and '\x00' not in name,
            'Unsafe archive path')
    path = PurePosixPath(name)
    require(not path.is_absolute() and not PureWindowsPath(name).drive
            and all(part not in ('.', '..') and ':' not in part for part in name.rstrip('/').split('/')),
            'Unsafe archive path: '+name)
    for part in path.parts:
        require(not part.endswith(('.', ' ')) and not any(ord(c) < 32 or c in '<>"|?*' for c in part)
                and not re.fullmatch(r'(?i)(CON|CONIN\$|CONOUT\$|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\..*)?', part),
                'Unsafe Windows archive path: '+name)
    return path


def verify_pe(data, name):
    require(len(data) >= 64 and data[:2] == b'MZ', 'Missing Windows executable header: '+name)
    offset = struct.unpack_from('<I', data, 60)[0]
    require(offset+26 <= len(data), 'Invalid PE offset: '+name)
    require(data[offset:offset+4] == b'PE\0\0' and struct.unpack_from('<H', data, offset+4)[0] == 0x8664
            and struct.unpack_from('<H', data, offset+24)[0] == 0x20b,
            'Expected an AMD64 Windows executable: '+name)


def source_version(data):
    for node in ast.parse(data).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'VERSION' for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError('Launcher source has no VERSION')


def validate(package, *, expected_version=None, repo=None, require_sidecar=False):
    package = Path(package)
    require(package.is_file(), 'Package does not exist')
    with zipfile.ZipFile(package) as archive:
        infos = archive.infolist()
        require(infos and len(infos) <= 100000, 'Empty or excessive archive')
        require(sum(i.file_size for i in infos) <= 8 * 1024**3
                and all(i.file_size <= 1024**3 and not i.flag_bits & 1 for i in infos),
                'Excessive or encrypted release archive')
        paths = [safe_member(i.filename) for i in infos]
        require(len({i.filename.casefold() for i in infos}) == len(infos), 'Duplicate Windows archive paths')
        require(all(not stat.S_ISLNK(i.external_attr >> 16) for i in infos), 'Archive symlinks are not supported')
        require(len({p.parts[0] for p in paths}) == 1, 'Expected one package root')
        root = paths[0].parts[0]
        names = {i.filename for i in infos if not i.is_dir()}
        require(all(p.name.lower() not in ('eboot.bin', 'param.sfo', 'image.bin') for p in paths),
                'Game files must not be distributed')
        require(archive.testzip() is None, 'Corrupt ZIP member')
        def read(name):
            require(root+'/'+name in names, 'Package is missing '+name)
            return archive.read(root+'/'+name)
        identity = json.loads(read('BUILD-IDENTITY.json'))
        require(isinstance(identity, dict), 'Invalid build identity')
        version = identity.get('version'); base, revision = version_parts(version)
        require(package.name == package_name(version), 'Package filename and build version disagree')
        require(expected_version is None or version == expected_version, 'Unexpected package version')
        commit, tree = identity.get('source_commit'), identity.get('source_tree')
        for label, value in (('source commit', commit), ('source tree', tree)):
            require(isinstance(value, str) and re.fullmatch('[0-9a-f]{40}', value), 'Invalid '+label)
        hint = TAG_RE.fullmatch(identity.get('release_tag', ''))
        require(hint and hint[1]+'-tatsunakyo.'+hint[2] == version, 'Build release tag and version disagree')
        hashes = identity.get('executables')
        require(isinstance(hashes, dict) and set(CORE).issubset(hashes), 'Missing executable provenance')
        for name, expected in hashes.items():
            safe_member(name)
            require(isinstance(expected, str) and re.fullmatch('[0-9a-f]{64}', expected), 'Invalid binary checksum')
            data = read(name)
            require(hashlib.sha256(data).hexdigest() == expected, 'Executable checksum mismatch: '+name)
            if name.lower().endswith(('.exe', '.dll', '.pyd')):
                verify_pe(data, name)
        for name in DATA: read(name)
        for name in RUNTIMES: verify_pe(read(name), name)
        python_dlls = [name for name in names if re.fullmatch(re.escape(root)+r'/_internal/python3\d+\.dll', name)]
        require(len(python_dlls) == 1, 'Expected one versioned Python runtime')
        verify_pe(archive.read(python_dlls[0]), python_dlls[0])
        runtimes = identity.get('runtime_files')
        if runtimes is not None:
            require(isinstance(runtimes, dict) and set(RUNTIMES).issubset(runtimes), 'Missing runtime provenance')
            for name, expected in runtimes.items():
                safe_member(name)
                require(hashlib.sha256(read(name)).hexdigest() == expected, 'Runtime checksum mismatch: '+name)
        else:
            # Published packages predate runtime_files. Their pinned vendor
            # manifests remain valid evidence; no existing package is rewritten.
            for file, folder in (('nvidia-runtime-manifest.json','bin/streamline'),
                                 ('microsoft-runtime-manifest.json','bin/streamline'),
                                 ('xess-runtime-manifest.json','bin/xess')):
                manifest = json.loads(read('source/verification/'+file))
                require(isinstance(manifest.get('files'), dict) and manifest['files'], 'Empty vendor manifest')
                for name, record in manifest['files'].items():
                    safe_member(name)
                    require(hashlib.sha256(read(folder+'/'+name)).hexdigest() == record['sha256'],
                            'Vendor runtime checksum mismatch: '+name)
        launcher = 'source/modified-files/launcher/bbport_launcher_win.py'
        require(source_version(read(launcher)) == version, 'Packaged launcher source and identity disagree')
        notes_path = f'docs/releases/windows-v{version}.md'
        notes = read(notes_path).decode('utf-8')
        require(notes.strip(), 'Empty release notes')
        if repo is not None:
            repo = Path(repo)
            def git(*args, env=None):
                return subprocess.check_output(['git', *args], cwd=repo, env=env)
            require(git('rev-parse', commit+'^{tree}').decode().strip() == tree, 'Source commit/tree mismatch')
            require(git('show', commit+':launcher/bbport_launcher_win.py') == read(launcher),
                    'Launcher source differs from its recorded commit')
            require(git('show', commit+':'+notes_path) == notes.encode(), 'Release notes differ from their recorded commit')
            upstream = identity.get('upstream_base')
            require(isinstance(upstream, str) and re.fullmatch('[0-9a-f]{40}', upstream), 'Missing source patch base')
            import os
            with tempfile.TemporaryDirectory() as tmp:
                env = dict(os.environ, GIT_INDEX_FILE=str(Path(tmp)/'index'))
                git('read-tree', upstream, env=env)
                patch = Path(tmp)/'revision.patch'; patch.write_bytes(read('source/tatsunakyo-revision.patch'))
                subprocess.run(['git', 'apply', '--cached', '--whitespace=nowarn', str(patch)], cwd=repo, env=env, check=True)
                require(git('write-tree', env=env).decode().strip() == tree, 'Source patch does not reproduce the build tree')
        # Resolve actual DLL imports/exports too: file presence alone cannot
        # detect a dependency built against an incompatible DLL version.
        from pe_integrity import verify_directory
        with tempfile.TemporaryDirectory() as tmp:
            native_root = Path(tmp)/root
            for name in names:
                if PurePosixPath(name).suffix.lower() in ('.exe','.dll','.pyd'):
                    target=Path(tmp)/name; target.parent.mkdir(parents=True,exist_ok=True)
                    target.write_bytes(archive.read(name))
            try:
                closure = verify_directory(native_root)
            except (AssertionError, IndexError, struct.error, UnicodeError) as failure:
                raise ValueError('Invalid Windows dependency table') from failure
    sha = checksum(package)
    sidecar = package.with_suffix('.zip.sha256')
    if sidecar.exists() or require_sidecar:
        require(sidecar.is_file(), 'Checksum sidecar is missing')
        match = re.fullmatch(r'([0-9a-fA-F]{64})[ \t]+\*?([^\r\n]+)\s*', sidecar.read_text(encoding='utf-8').strip())
        require(match and match[1].lower() == sha and match[2] == package.name, 'Checksum sidecar mismatch')
    return {'version':version, 'revision':revision, 'identity':identity, 'root':root,
            'source_commit':commit, 'source_tree':tree, 'sha256':sha, 'bytes':package.stat().st_size,
            'executables_checked':len(hashes), 'source_verified':repo is not None, 'notes':notes, **closure}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('--repo', type=Path)
    parser.add_argument('--expected-version')
    parser.add_argument('--require-sidecar', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = validate(args.package, repo=args.repo, expected_version=args.expected_version,
                      require_sidecar=args.require_sidecar)
    result.pop('notes')
    text = json.dumps(result, indent=2)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(text)
    print(text)


if __name__ == '__main__':
    main()
