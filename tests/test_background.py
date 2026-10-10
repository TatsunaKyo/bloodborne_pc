# SPDX-License-Identifier: GPL-2.0-or-later
"""The launch path never suspends a Windows process or its window thread."""
import importlib.util
from pathlib import Path
from unittest.mock import patch, Mock
source = Path(__file__).resolve().parents[1] / 'scripts/background.py'
spec = importlib.util.spec_from_file_location('background', source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
child = Mock()
child.wait.return_value = 42
with patch.object(module.subprocess, 'Popen', return_value=child) as start:
    env = {'BB_CONFIG': 'custom.ini'}
    assert module.run_game(['bb-probe.exe'], config='custom.ini', env=env, cwd='game') == 42
    start.assert_called_once_with(['bb-probe.exe'], env=env, cwd='game')
    child.wait.assert_called_once_with()
assert 'NtSuspendProcess' not in source.read_text()
print('PASS: launcher waits for the native child without freezing the window thread.')
