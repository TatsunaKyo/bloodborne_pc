"""Construct every current launcher page and round-trip shared Workshop settings.

Runs actual Tk widgets; pass the compiled Bloodborne.exe to inspect its code.
"""
import sys
from workshop_launcher_fixture import launcher_window

with launcher_window(sys.argv[1] if len(sys.argv) > 1 else None) as (module, app, root, config):
    for name in app.pages:
        app.show(name)
        root.update()
    for key, _ in module.workshop.FRAME_GENERATORS:
        app.var('frame_generation', 'menu').set(key)
        app.collect()
        menu = module.load_menu()
        graphics, _ = module.load_ini()
        assert menu['frame_generation'] == key, (key, menu)
        assert graphics['frame_gen'] == module.workshop.ROUTE_TO_NATIVE.get(key, 'off'), (key, graphics)
    for upscaler in ('xess', 'dlss', 'fsr3', 'fsr411', 'fsr412', 'taa'):
        app.var('upscaler', 'ini').set(upscaler)
        app.collect()
        root.update()
        assert module.load_menu()['xess_preset'] == '5'
    app.var('frame_cap', 'app').set('75')
    app.var('generated_fps_limit', 'menu').set('130')
    app.var('limit_generated_fps', 'menu').set(True)
    app.collect()
    assert module.load_ini()[0]['frame_cap'] == '75'
    assert module.load_menu()['real_fps_limit'] == '75'
    assert module.load_menu()['generated_fps_limit'] == '130'
    # External overlay edits survive a launcher save when its control was untouched.
    module.save_menu({'nvidia_fg_preset': 'c'})
    app.refresh_menu_settings()
    app.collect()
    assert module.load_menu()['nvidia_fg_preset'] == 'c'
    print(f'PASS: {len(app.pages)} actual launcher pages, seven FG routes, XeSS quality isolation, caps and live-edit persistence.')
