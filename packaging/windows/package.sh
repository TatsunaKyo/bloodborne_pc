#!/usr/bin/env bash
# Builds the frozen Windows launcher, then the single verified release ZIP and SHA256.
# Bloodborne.exe (the launcher, frozen
# with PyInstaller so players need no Python), bb-probe.exe with the MSYS2 CLANG64 DLLs it needs,
# the preparation scripts and run.py. Run from an MSYS2 CLANG64 shell after `bash build.sh`.
# Freezing uses a Windows Python 3.10+ (python.org; WINPYTHON overrides) and a private venv in
# out/pyenv with PyInstaller. FSR 4 assets in fsr4_shaders/ are included when present.
set -euo pipefail
cd -- "$(dirname -- "$0")/../.."
source ./msys2-env.sh
[[ ${1:-} == --launcher-only ]] || [[ -f out/bb-probe.exe && -f out/bb-gpu-capabilities.exe && -f out/bb-fg401-capabilities.exe && -f out/bb-play.exe ]] || { echo 'Build first: bash build.sh' >&2; exit 1; }

# A Windows Python (not MSYS2's) for PyInstaller.
python=${WINPYTHON:-}
if [[ -z $python ]]; then
    for candidate in /c/Python3*/python.exe "${LOCALAPPDATA:-/c/Users/$USER/AppData/Local}"/Programs/Python/Python3*/python.exe; do
        [[ -x $candidate ]] && python=$candidate
    done
fi
[[ -n $python ]] || { echo 'Need a Windows Python 3 (python.org) or WINPYTHON=path\to\python.exe' >&2; exit 1; }
# Windows Python needs USERPROFILE (some MSYS2 shells start without it).
export USERPROFILE=${USERPROFILE:-$(cygpath -w "/c/Users/$(id -un)")}
if [[ ! -x out/pyenv/Scripts/python.exe ]]; then
    "$python" -m venv out/pyenv
fi
out/pyenv/Scripts/python.exe -m pip install -q --disable-pip-version-check PyInstaller==6.19.0 Pillow==12.3.0
out/pyenv/Scripts/python.exe tools/freeze_launcher.py

if [[ ${1:-} == --launcher-only ]]; then
    echo 'Compiled launcher: out/pyi-dist/Bloodborne'
    exit 0
fi

# Keep one canonical assembler: it verifies native-test evidence, replaces all current
# runtime sources, resolves DLLs and writes one ZIP plus its checksum.
out/pyenv/Scripts/python.exe tools/assemble_windows.py \
    --baseline "$(cygpath -w "$PWD/out/dependencies/runtime-baseline.zip")" \
    --dll-dir "$(cygpath -w /clang64/bin)" --channel "${RELEASE_CHANNEL:-stable}"
