# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Exercise the current launcher pages at two window sizes and five scales."""
import sys
from workshop_launcher_fixture import launcher_window

exe = sys.argv[1] if len(sys.argv) > 1 else None
layouts = 0
for language in ('en', 'ru'):
    for scale in (1.0, 1.25, 1.5, 1.75, 2.0):
        with launcher_window(exe, language=language, scale=scale) as (_, app, root, _):
            for width, height in ((980, 660), (1280, 850)):
                root.geometry(f'{app.px(width)}x{app.px(height)}+0+0')
                for name, page in app.pages.items():
                    app.show(name)
                    root.update()
                    assert page.winfo_ismapped(), (language, scale, name)
                    left = page.winfo_rootx()
                    top = page.winfo_rooty()
                    assert app.side.winfo_rootx() + app.side.winfo_width() <= left
                    assert left + page.winfo_width() <= root.winfo_rootx() + root.winfo_width()
                    assert top + page.winfo_height() <= root.winfo_rooty() + root.winfo_height()
                    if hasattr(page, 'viewport'):
                        view = page.viewport
                        assert view.winfo_ismapped() and view.winfo_height() > 0
                        assert left <= view.winfo_rootx()
                        assert view.winfo_rootx() + view.winfo_width() <= left + page.winfo_width()
                    layouts += 1
                assert app.brand.winfo_ismapped()
                assert 'by TatsunaKyo' in app.byline.cget('text')
print(f'PASS: {layouts} actual launcher page layouts in English/Russian at 100–200% scaling.')
