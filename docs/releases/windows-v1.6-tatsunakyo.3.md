> Historical/upstream record: statements and test results below describe their original revision or environment. [Current guides](../index.md) · [Current reports](../known-issues.md) · [Published releases](../releases/index.md)

<!-- crowned-workshop-navigation -->
> Historical document. [The Crowned Workshop current guides](../index.md) · [Current reports](../known-issues.md). This page retains its original context and credits.

# Bloodborne for Windows v1.6 — TatsunaKyo revision 3

I added optional resolution information to the OSD and a choice for what the game should do when you switch to another window. I wanted the information available without forcing a larger overlay on everyone.

## Changes

- I added **Show input/output resolution in overlay** to Display & FPS and the R3+L3 / Insert menu. It starts off. When enabled, actual scene and output sizes appear on the existing line, such as `854x480>1920x1080`.
- I kept the OSD on one row. Extra details fit within a compact width; font size can decrease by up to 15%. The basic overlay and optional DLSS preset readout remain separate choices.
- I added **When in background** to both interfaces: Keep running, Pause game and rendering, Limit to 30 FPS, or Limit to 60 FPS. Keep running is the default.
- On Windows, pause freezes the native game process, including its rendering and window threads. The launcher supervisor resumes it when the game regains focus. Guest clocks exclude the paused time so the game does not treat it as a long frame. Background FPS limits throttle game flips and restore the foreground cap when you return.
- Save the background choice immediately in-game and replace the shared settings file atomically, so the focus supervisor reads a complete policy.

English and Russian remain the in-game menu languages. Frame Generation and the additional gameplay cheats are not implemented in this build; they remain on [the revision roadmap](../tatsunakyo-next.md).

## Installing

Extract **Bloodborne-Windows-v1.6-TatsunaKyo-Revision-3.zip** into a fresh folder and open **Bloodborne.exe**. The sidebar shows `v1.6-tatsunakyo.3` and **TatsunaKyo revision**. `Start-Verified-Launcher.cmd` verifies the included EXE.

For an existing installation, close the game and launcher, preserve saves, mods, `bbport.ini` and `bbport.menu.ini`, and update all program files, including `bin/`, `scripts/`, `run.py` and `_internal/`. No game files are included.

## Validation

I rebuilt the Windows launcher and native game executable. Launcher preference and updater tests, real ImGui control and OSD layout tests, background transition tests, the Windows job-structure ABI check, and guest clock continuity tests pass. The package includes build details, source changes and executable SHA-256 hashes.

The process-suspension approach could leave the game unresponsive on return. I replaced it with cooperative pause in Revision 4. My gameplay checks and that fix are documented in [Testing and known issues](../testing.md).

## Credits

Revision by **TatsunaKyo**. Original Windows port by **Supermedo**; native port by **deadinside28**, with **shadPS4** and the projects in the [README](../../README.md#credits). Existing copyrights and licenses are retained.
