> Historical/upstream record: statements and test results below describe their original revision or environment. [Current guides](../index.md) · [Current reports](../known-issues.md) · [Published releases](../releases/index.md)

<!-- crowned-workshop-navigation -->
> Historical document. [The Crowned Workshop current guides](../index.md) · [Current reports](../known-issues.md). This page retains its original context and credits.

# Bloodborne for Windows v1.6 — TatsunaKyo revision 4

I fixed the controls that did not toggle in the in-game menu and replaced my background-pause implementation after it left the game unresponsive on return. The window's event thread now stays active while game work and rendering pause.

## Changes

- I corrected in-game checkboxes and sliders reading their previous value with the Windows compiler, and recorded the click position even when no mouse movement event precedes it.
- I kept the Windows event thread running during background pause. Game submissions and presentation wait at native frame boundaries; guest clocks exclude paused time. The game can receive activation and close messages throughout the pause.
- I kept the DLSS preset dropdown visible in Quick settings and Graphics, but disabled it unless DLSS is selected. The saved preset is preserved and the redundant Quick settings note is removed.
- I added 75 FPS to the launcher and unlocked-mode cap choices, using the variable frame-time patch with the native limiter.
- I reused the upscaled display buffer's cached Vulkan image view to avoid a create/destroy cycle on every frame. I made that change to reduce driver overhead. Results from other configurations are welcome.
- I corrected DLSS GPU-profile labels, which previously appeared as FSR in the timing log. See [the performance capture steps](../performance.md) for comparing the Central Yharnam scene.
- I kept GitHub prose in complete paragraphs without forced line breaks.

## Installing

Extract **Bloodborne-Windows-v1.6-TatsunaKyo-Revision-4.zip** into a fresh folder and start **Bloodborne.exe**. The sidebar shows `v1.6-tatsunakyo.4` and **TatsunaKyo revision**. Update the full package, including `bin/`, `scripts/`, `run.py` and `_internal/`; replacing only the launcher does not update the native game. Keep your saves, mods and existing INI files. Game files are not included.

## Validation

I rebuilt the launcher and native Windows executables. Tests exercise the actual ImGui controls with the Windows Clang compiler: checkbox clicks, sliders, keyboard and controller activation, settings round trips, both menu languages and the compact OSD layout. Native pause tests cover repeated activation while frame workers are blocked, shutdown cancellation and clock accounting. Launcher tests check both preset dropdowns, retained selections, the 75 FPS environment and the fork's update channel. The package records source identity and executable hashes.

Gameplay coverage is documented in [Testing and known issues](../testing.md). Frame Generation and the new gameplay cheats were still on the roadmap at this hotfix.

## Credits

Revision by **TatsunaKyo**. Original Windows port by **Supermedo**; native port by **deadinside28**, with **shadPS4** and the projects credited in the [README](../../README.md#credits). Existing copyrights and licenses are retained.
