# Bloodborne for Windows v1.6 — TatsunaKyo revision 4

This update fixes controls that did not toggle in the in-game menu and replaces the background pause that could leave the game unresponsive when you tried to return to it.

## Changes

- Fix in-game checkboxes and sliders reading their previous value with the Windows compiler. Record the click position even when no mouse movement event precedes it.
- Keep the Windows event thread running during background pause. Game submissions and presentation wait at native frame boundaries; guest clocks exclude paused time. The game can receive activation and close messages throughout the pause.
- Keep the DLSS preset dropdown visible in Quick settings and Graphics, but disable it unless DLSS is selected. Preserve the saved preset and remove the redundant note from Quick settings.
- Add 75 FPS to the launcher and unlocked-mode cap choices. Use the variable frame-time patch with the native limiter for that choice.
- Reuse the upscaled display buffer's cached Vulkan image view, avoiding a create/destroy cycle on every frame. This reduces driver work; a workload reduction is not a measured Central Yharnam FPS result.
- Correct DLSS GPU-profile labels, which previously appeared as FSR in the timing log. See [the performance capture steps](../performance.md) for comparing the Central Yharnam scene.
- Keep GitHub prose in complete paragraphs without forced line breaks.

## Installing

Extract **Bloodborne-Windows-v1.6-TatsunaKyo-Revision-4.zip** into a fresh folder and start **Bloodborne.exe**. The sidebar shows `v1.6-tatsunakyo.4` and **TatsunaKyo revision**. Update the full package, including `bin/`, `scripts/`, `run.py` and `_internal/`; replacing only the launcher does not update the native game. Keep your saves, mods and existing INI files. Game files are not included.

## Validation

The launcher and native Windows executables are rebuilt. Tests exercise the actual ImGui controls with the Windows Clang compiler: checkbox clicks, sliders, keyboard and controller activation, settings round trips, both menu languages and the compact OSD layout. Native pause tests cover repeated activation while frame workers are blocked, shutdown cancellation and clock accounting. Launcher tests check both preset dropdowns, retained selections, the 75 FPS environment and the fork's update channel. The package records source identity and executable hashes.

Gameplay coverage is documented in [Testing and known issues](../testing.md). Frame Generation and the new gameplay cheats were still on the roadmap at this hotfix.

## Credits

Revision by **TatsunaKyo**. Original Windows port by **Supermedo**; native port by **deadinside28**, with **shadPS4** and the projects credited in the [README](../../README.md#credits). Existing copyrights and licenses are retained.
