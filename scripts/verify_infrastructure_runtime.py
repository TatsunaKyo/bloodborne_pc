# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Developer self-test for the packaged Python runtime; operates only on temporary fixtures."""
import json
from pathlib import Path
import tempfile

from save_manager import SaveManager, verify_backup
from support_report import build_report, detect_system, export_report, verify_report
from release_integrity import package_name, safe_member
from pe_integrity import PE


def main():
    assert package_name('1.6-tatsunakyo.27') == 'Bloodborne-Windows-v1.6-TatsunaKyo-Revision-27.zip'
    assert PE is not None
    try:
        safe_member('Workshop/NUL.txt')
    except ValueError:
        pass
    else:
        raise AssertionError('Unsafe Windows update path accepted')
    print('PASS: packaged release/dependency validator imports and unsafe update path rejection.')
    import tkinter as tk
    from tkinter import ttk
    # Exercise Tcl/Tk's packaged scripts as well as the extension import. An
    # incomplete fresh freeze can import _tkinter but fail on the first window.
    window = tk.Tk()
    try:
        window.withdraw()
        style = ttk.Style(window); style.theme_use('clam')
        listing = ttk.Treeview(window, columns=('status',))
        listing.insert('', 'end', iid='fixture', text='Runtime fixture', values=('Verified',))
        listing.pack(); window.update()
        assert listing.item('fixture', 'values') == ('Verified',)
        print('PASS: packaged Tcl/Tk window and controls (' + str(window.tk.call('info', 'patchlevel')) + ').')
    finally:
        window.destroy()
    with tempfile.TemporaryDirectory(prefix='workshop-runtime-selftest-') as folder:
        root = Path(folder)
        user = root / 'fixture user'; user.mkdir()
        data = user / 'savedata/0/CUSA03173/SPRJ0005/userdata0010'
        data.parent.mkdir(parents=True); data.write_bytes(b'fixture-only original data')
        (user / 'last_run.log').write_text('Password: EXCLUDE-THIS-FAKE-CREDENTIAL\nFrames: fps=75\n')
        system = detect_system(include_profile=True)
        candidate = build_report(root, user, {'online_password': 'EXCLUDE-THIS-FAKE-CREDENTIAL'},
                                 {'upscaler': 'dlss'}, {'frame_generation': 'off'}, 'self-test',
                                 include_profile=True, system=system)
        assert all(b'EXCLUDE-THIS-FAKE-CREDENTIAL' not in value for value in candidate.entries.values())
        report = export_report(candidate, root / 'support.zip'); assert verify_report(report)
        submission = json.loads(candidate.entries['hardware-submission.json'])
        assert submission['reviewed'] is False and submission['status'] == 'unverified'
        manager = SaveManager(user)
        backup = manager.snapshot('Temporary test fixture'); assert verify_backup(backup)
        data.write_bytes(b'fixture-only later data')
        restored = manager.restore(backup); assert data.read_bytes() == b'fixture-only original data'
        manager.restore(restored['rollback']); assert data.read_bytes() == b'fixture-only later data'
    print('PASS: packaged runtime imports, local hardware query, inspected support ZIP, unreviewed submission and save/rollback round trip.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
