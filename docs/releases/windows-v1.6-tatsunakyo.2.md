> Historical/upstream record: statements and test results below describe their original revision or environment. [Current guides](../index.md) · [Current reports](../known-issues.md) · [Published releases](../releases/index.md)

<!-- crowned-workshop-navigation -->
> Historical document. [The Crowned Workshop current guides](../index.md) · [Current reports](../known-issues.md). This page retains its original context and credits.

# Bloodborne for Windows v1.6 — TatsunaKyo revision 2

Based on [revision 1](windows-v1.6-tatsunakyo.1.md), retaining its English in-game menu, borderless fullscreen, DLSS render presets and optional compact performance overlay.

I fixed the sidebar text that was getting clipped. This is a launcher update; the native components remain the verified Revision 1 build.

## Changes

- I moved the platform and full version onto separate, left-aligned lines. The text wraps within the sidebar at the launcher's current DPI instead of extending beyond it.
- I incremented the launcher version to `1.6-tatsunakyo.2`, so revision 1 can detect this update when it is published.

## Installing

Download **Bloodborne-Windows-v1.6-TatsunaKyo-Revision-2.zip**, extract into a fresh folder and run **Bloodborne.exe**. The sidebar shows `v1.6-tatsunakyo.2` and **TatsunaKyo revision**. `Start-Verified-Launcher.cmd` verifies and opens the included executable.

For an existing installation, close the launcher and game, preserve saves, mods, `bbport.ini` and `bbport.menu.ini`, and update all program files, including `bin/` and `_internal/`. No game files are included.

## Build and validation

I recompiled the Windows launcher entry point and checked both its source and the final `Bloodborne.exe`. Settings, DLSS choices, independent overlay controls and the fork update channel passed their regressions. The renderer and native helper executables are unchanged from the verified revision 1 native build. The full package includes source changes, build details and SHA-256 hashes.

Gameplay coverage is collected in [Testing and known issues](../testing.md). Frame Generation and additional cheats were not included in this launcher fix.

## Credits and licenses

Revision by **TatsunaKyo**. Original Windows port by **Supermedo**; native port by **deadinside28**, with **shadPS4** and the projects listed in the [README](../../README.md#credits). Existing copyrights and licenses are retained.
