# Bloodborne for Windows v1.6 — TatsunaKyo revision 1

Based on [Supermedo's Windows v1.6 port](https://github.com/Supermedo/bloodborne_pc/tree/windows-v1.6).

## Changes

- The **in-game menu** opened with **L3+R3 / Insert** defaults to English. English and
  Russian can be selected in the launcher and in-game independently of the game language.
- **Borderless fullscreen** is available in the launcher and in-game, alongside
  Windowed and Fullscreen. In-game switching applies immediately. Borderless uses
  the desktop resolution and refresh rate without changing display mode or minimizing
  on focus loss.
- **V-sync in borderless** is selectable. With V-sync off the renderer requests Vulkan
  Immediate presentation, then Mailbox/FIFO if necessary. With V-sync on it requests
  Mailbox, then FIFO. The existing one-frame GPU queue limit is retained. Immediate
  can tear; Windows presentation behavior and latency depend on the system and driver.
- **DLSS render presets** can be selected in the launcher and the in-game menu. They
  are separate from Quality/Balanced/Performance and do not change render resolution.
  In-game changes recreate the DLSS feature on the next frame without restarting the
  game. The launcher selector remains available with other upscalers selected; the
  saved preset takes effect when DLSS is used.
- The **top-right performance overlay** can be enabled or disabled from both interfaces.
  A separate **Show DLSS preset in overlay** choice in the launcher and in-game keeps
  the original basic overlay or adds the active preset letter on the same line:
  `DLSS (M)`. `DLSS (K>M)` shows a pending change from K to M; Default is written as
  `Default` and `-` means no accepted feature yet. There are no extra OSD rows or
  model-generation descriptions. This option defaults to off. The readout tracks
  the accepted feature's requested preset; NVIDIA driver/profile overrides can
  choose a different internal model.
- Menu language, window mode, borderless V-sync, DLSS preset and both overlay preferences
  are shared through `bbport.menu.ini`. Launcher saves preserve changes made in-game.
  Existing fullscreen and `show_fps` preferences are migrated automatically.
- The launcher is branded **TatsunaKyo revision**. Its updater uses this fork and
  accepts only matching Windows revision releases and packages.
- Windows header casing fixes support cross-compilation on case-sensitive systems.

The DLSS dropdown contains these exact choices, in this order:

| Choice | Description |
|---|---|
| Default | Driver default |
| E | CNN / legacy |
| F | CNN / legacy |
| J | Transformer 1st gen |
| K | Transformer 1st gen |
| M | Transformer 2nd gen |
| L | Transformer 2nd gen |

Removed and reserved preset IDs are excluded.

## Installing

Download **Bloodborne-Windows-v1.6-TatsunaKyo-Revision-1.zip**, extract it into a fresh
folder and run the included **Bloodborne.exe**. The launcher title and sidebar show
**TatsunaKyo revision**. Select your game folder and existing saves folder before playing.
No game files are included.

When updating an existing installation manually, close the game and launcher, keep
your saves, mods, `bbport.ini` and `bbport.menu.ini`, and copy all program files, including
`bin/` and `_internal/`. The package's initial menu defaults are English, borderless,
V-sync off, DLSS Default and basic performance overlay on. Keep your existing menu INI to
retain previous choices.

## Build and validation

The package includes rebuilt Windows x64 executables, source changes, build details
and SHA-256 hashes. `Start-Verified-Launcher.cmd` checks and starts the included launcher.
The release tag provides the complete corresponding source; the included patch also
reproduces it from upstream `windows-v1.6`.

Checks cover the compiled launcher settings and update channel, saved preferences,
in-game ImGui controls, DLSS feature recreation with mocked NGX/Vulkan, Windows
compilation/linking and packaged DLL imports. Windows gameplay, real Tk popup rendering
and GPU latency have not been tested on this build host; these need testing on Windows.

## Credits and licenses

Revision by **TatsunaKyo**. Original Windows port by **Supermedo**; native port by
**deadinside28**, with the **shadPS4** renderer and the projects listed in the
[README](../../README.md#credits). Existing copyrights and licenses are retained.
The main project is GPL v2 or later; included third-party components retain their own
licenses, including the NVIDIA DLSS runtime.
