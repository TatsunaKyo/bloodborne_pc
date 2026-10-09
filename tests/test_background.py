# SPDX-License-Identifier: GPL-2.0-or-later
"""Check pause/resume and clock publication without suspending the test runner."""
import sys
import ctypes
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from background import JobLimits, PauseController, menu_mode


class BackgroundTests(unittest.TestCase):
    def test_windows_job_structure_matches_the_x64_abi(self):
        self.assertEqual(ctypes.sizeof(JobLimits), 144)
        self.assertEqual(JobLimits.flags.offset, 16)
        self.assertEqual(JobLimits.io_counters.offset, 64)
        self.assertEqual(JobLimits.process_memory_limit.offset, 112)

    def controller(self):
        self.time = 0
        self.events = []
        return PauseController(lambda: self.events.append('suspend'),
                               lambda: self.events.append('resume'),
                               lambda ns: self.events.append(('clock', ns)),
                               lambda: self.time)

    def test_pause_once_and_resume_with_clock_published_first(self):
        c = self.controller()
        c.update(True, 'pause')
        c.update(False, 'pause', window_exists=False)
        self.assertEqual(self.events, [])
        self.time = 100
        c.update(False, 'pause')
        c.update(False, 'pause')
        self.assertEqual(self.events, ['suspend'])
        self.time = 100100
        c.update(True, 'pause')
        self.assertEqual(self.events, ['suspend', ('clock', 100000), 'resume'])
        c.update(True, 'pause')
        self.assertEqual(c.paused_ns, 100000)
        self.time = 200000
        c.update(False, 'pause')
        self.time = 300000
        c.close()
        self.assertEqual(self.events[-2:], [('clock', 200000), 'resume'])
        c.close()
        self.assertEqual(len(self.events), 6)

    def test_capped_modes_do_not_suspend_and_changing_mode_resumes(self):
        c = self.controller()
        for mode in ('run', '30', '60'):
            c.update(False, mode)
        self.assertEqual(self.events, [])
        c.update(False, 'pause')
        self.time = 1234
        c.update(False, '30')
        self.assertEqual(self.events, ['suspend', ('clock', 1234), 'resume'])

    def test_failed_suspend_does_not_claim_a_pause(self):
        def fail():
            raise OSError('suspend failed')
        c = PauseController(fail, lambda: self.fail('must not resume'), lambda _: None)
        with self.assertRaises(OSError):
            c.update(False, 'pause')
        self.assertIsNone(c.started)
        c.close()

    def test_resume_retry_does_not_double_count_a_pause(self):
        c = self.controller()
        c.update(False, 'pause')
        self.time = 1000
        def fail():
            raise OSError('resume failed')
        c.resume = fail
        with self.assertRaises(OSError):
            c.update(True, 'pause')
        self.assertEqual(c.paused_ns, 0)
        self.time = 2000
        c.resume = lambda: self.events.append('resume')
        c.close()
        self.assertEqual(c.paused_ns, 2000)
        self.assertEqual(self.events[-2:], [('clock', 2000), 'resume'])

    def test_settings_are_live_and_bad_values_are_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'custom.ini'
            menu = config.with_suffix('.menu.ini')
            self.assertEqual(menu_mode(config), 'run')
            for mode in ('pause', '30', '60', 'run'):
                menu.write_text(f'menu_language=en\nbackground_mode={mode}\n')
                self.assertEqual(menu_mode(config), mode)
            for value in ('invalid', '', '30 FPS'):
                menu.write_text(f'background_mode={value}\n')
                self.assertEqual(menu_mode(config), 'run')


if __name__ == '__main__':
    unittest.main()
