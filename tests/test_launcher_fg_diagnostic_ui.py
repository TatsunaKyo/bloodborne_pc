# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Operate the current diagnostic buttons in the actual Advanced page."""
import sys
from workshop_launcher_fixture import launcher_window, reveal

exe = sys.argv[1] if len(sys.argv) > 1 else None
layouts = 0
for language in ('en', 'ru'):
    for scale in (1.0, 1.25, 1.5, 1.75, 2.0):
        with launcher_window(exe, language=language, scale=scale) as (_, app, root, _):
            app.show('advanced')
            selected = []
            app.play = selected.append
            buttons = (app.nvidia_capture_button, app.nvidia_compare_button,
                       app.traversal_capture_button)
            for width, height in ((980, 660), (1280, 850)):
                root.geometry(f'{app.px(width)}x{app.px(height)}+0+0')
                root.update()
                page = app.pages['advanced']
                for button in buttons:
                    reveal(root, page, button)
                    assert button.winfo_ismapped()
                    assert button.winfo_width() >= button.winfo_reqwidth()
                    assert button.winfo_rootx() + button.winfo_width() <= page.viewport.winfo_rootx() + page.viewport.winfo_width()
                    button.invoke()
                assert selected[-3:] == ['inputs', 'generated-only', 'traversal']
                assert '_nvidia_diagnostic' not in app.app and '_traversal_diagnostic' not in app.app
                layouts += 1
print(f'PASS: {layouts} diagnostic layouts, three one-run commands and unchanged preferences.')
