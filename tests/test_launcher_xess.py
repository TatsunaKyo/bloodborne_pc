# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Exercise the actual XeSS popup, old INI migration and separate quality controls."""
import sys
from workshop_launcher_fixture import launcher_window, reveal, select_popup

exe = sys.argv[1] if len(sys.argv) > 1 else None
choices = 0
for language in ('en', 'ru'):
    for scale in (1.0, 1.5, 2.0):
        with launcher_window(exe, language=language, scale=scale) as (module, app, root, config):
            app.show('graphics')
            root.update()
            box = app.graphics_xess_row
            generic = app.graphics_preset_row
            dlss = app.graphics_dlss_row
            provider = app.var('upscaler', 'ini')
            for key, _ in module.UPSCALERS:
                provider.set(key)
                root.update()
                for row, visible in ((box, key == 'xess'), (generic, key != 'xess'),
                                     (dlss, key == 'dlss')):
                    assert all(bool(w.winfo_ismapped()) == visible for w in row.workshop_widgets), key
            generic_value = app.var('preset', 'ini').get()
            provider.set('xess')
            root.update()
            reveal(root, app.pages['graphics'], box)
            options = module.workshop.XESS_PRESETS
            labels = [module._(*labels) for _, labels in options]
            for index, (key, _) in enumerate(options):
                select_popup(root, box, labels, index)
                assert app.var('xess_preset', 'menu').get() == key
                app.collect()
                assert module.load_menu()['xess_preset'] == key
                assert module.load_ini()[0]['xess_preset'] == key
                assert app.var('preset', 'ini').get() == generic_value
                assert app.var('dlss_preset', 'menu').get() == 'l'
                choices += 1

            menu = config.with_suffix('.menu.ini')
            menu.unlink()
            for index, expected in enumerate(module.workshop.LEGACY_XESS_PRESETS):
                config.write_text(f'upscaler=xess\npreset={index}\n')
                assert module.load_menu()['xess_preset'] == expected
            config.write_text('upscaler=xess\npreset=3\nxess_preset=1\n')
            assert module.load_menu()['xess_preset'] == '1'
            menu.write_text('xess_preset=6\n')
            assert module.load_menu()['xess_preset'] == '6'
print(f'PASS: {choices} real XeSS popup selections; quality isolation and legacy migration.')
