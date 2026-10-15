# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Run the existing CPU/provider-contract regressions as part of portable CI."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = 'gpu/shim/bbport_settings.cpp'
CASES = {
    'frame_pacing': [], 'frame_metrics': [], 'frametime': [],
    'temporal_history': [], 'motion_history': [],
    'background_pause': ['gpu/shim/bbport_background.cpp'],
    'real_fps': [SETTINGS], 'overlay_settings': [SETTINGS],
    'nvidia_preset_state': [SETTINGS],
    'upscaler_support': [SETTINGS], 'xess_presets': [SETTINGS],
    'amd_antilag': [SETTINGS, 'gpu/shim/bbport_amd.cpp'],
    'xess': [SETTINGS, 'gpu/shadps4/video_core/renderer_vulkan/vk_xess.cpp'],
}


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='workshop-cpu-tests-') as directory:
        for name, sources in CASES.items():
            binary = Path(directory) / name
            flags = ['-DBB_XESS_TESTING'] if name == 'xess' else []
            command = ['g++', '-std=c++23', '-O1', '-pthread', '-UNDEBUG',
                       '-I.', '-Igpu/shim', '-Igpu/shadps4', '-Iout/test-headers',
                       '-Iout/test-headers/vma', *flags, 'tests/test_' + name + '.cpp', *sources, '-o', str(binary)]
            print('Production integration: ' + name, flush=True)
            subprocess.run(command, cwd=ROOT, check=True)
            subprocess.run([str(binary)], cwd=ROOT, check=True, timeout=30)

    with tempfile.TemporaryDirectory(prefix="workshop-cheat-tests-") as directory:
        binary = Path(directory) / "cheats"
        subprocess.run(["gcc", "-O2", "-mavx", "-Isrc", "tests/test_cheats.c",
                        "tests/test_cheats_fixture.S", "-o", str(binary)], cwd=ROOT, check=True)
        subprocess.run([str(binary)], cwd=ROOT, check=True, timeout=30)
