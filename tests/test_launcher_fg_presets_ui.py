# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Exercise the actual NVIDIA FG popup and gated Encore control."""
import sys
from workshop_launcher_fixture import launcher_window, reveal, select_popup

exe = sys.argv[1] if len(sys.argv) > 1 else None
choices = 0
for language in ('en', 'ru'):
    for scale in (1.0, 1.5, 2.0):
        with launcher_window(exe, language=language, scale=scale) as (module, app, root, _):
            app.show('graphics')
            route = app.var('frame_generation', 'menu')
            box, mod = app.nvidia_fg_preset_row, app.nvidia_fg_mod_row
            for key, _ in module.workshop.FRAME_GENERATORS:
                route.set(key)
                root.update()
                for row in (app.nvidia_multiplier_row, box, mod):
                    assert all(bool(w.winfo_ismapped()) == (key == 'nvidia')
                               for w in row.workshop_widgets), key
            route.set('nvidia')
            root.update()
            reveal(root, app.pages['graphics'], box)
            options = module.workshop.NVIDIA_FG_PRESETS
            labels = [module._(*labels) for _, labels in options]
            for index, (key, _) in enumerate(options):
                select_popup(root, box, labels, index)
                assert app.var('nvidia_fg_preset', 'menu').get() == key
                app.collect()
                assert module.load_menu()['nvidia_fg_preset'] == key
                choices += 1
            for expected in ('1', '0'):
                mod.invoke()
                app.collect()
                assert module.load_menu()['nvidia_fg_mod'] == expected
            route.set('native_fsr')
            app.collect()
            assert module.load_menu()['nvidia_fg_preset'] == 'c'
print(f'PASS: {choices} real FG popup selections; seven routes and Encore opt-in persistence.')
