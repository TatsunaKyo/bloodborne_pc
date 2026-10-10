# SPDX-License-Identifier: GPL-2.0-or-later
"""Launch the native game. Background pause is handled at native frame boundaries.

The window event thread must stay runnable to receive Windows activation messages.
Never suspend the process containing that thread.
"""
import subprocess


def run_game(command, *, config, env, **kwargs):
    # config remains part of the launch interface; the renderer reads its menu INI.
    child = subprocess.Popen(command, env=env, **kwargs)
    return child.wait()
