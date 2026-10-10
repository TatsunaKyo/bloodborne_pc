# Bloodborne Windows v1.6 — TatsunaKyo revision 9

The DLSS preset dropdown on Play now lines up with the other quick settings. Enabling NVIDIA Frame Generation puts its multiplier on a separate row above Output, so those controls no longer overlap. Both optional rows keep their assigned positions when hidden and shown again. At smaller window sizes and higher DPI, the banner shrinks and the Ready check text wraps to leave room for the settings.

Play keeps Show performance overlay. The separate preset-overlay checkbox is replaced by Customize overlay…, which opens the overlay options in Display & FPS. Preset, input/output resolution, FG mode and PC latency remain independently selectable there and in the in-game menu. The link also works with Enter or Space.

Infinite Stamina now covers the continuous drain used while running, plus direct character/script updates and state synchronization. The earlier attack fix missed those paths. The extra hooks use the game's existing no-consumption branches for the player; they do not change maximum stamina, regeneration or NPC stamina. All 23 hook signatures were checked against the privately supplied 1.09 executable.

Both Bloodborne.exe and bin/bb-probe.exe are rebuilt. The UI regression checks exercise English/Russian, three window sizes, 100/150/200% scaling and six sequences of upscaler/FG changes. They check alignment, visibility, overlaps, available space and the overlay link using real Tk widgets and the Python entry point extracted from the rebuilt launcher. Cheat tests execute the actual Windows-compiled runtime object and the original continuous stamina updates, including 50 consecutive drain ticks, disabled cheats, NPCs, negative stamina and regeneration. No game code or assets are distributed.

Gameplay coverage on TatsunaKyo’s Windows 11 / RTX PC and the continuous-running check are documented in [Testing and known issues](../testing.md). Graphics providers, FG pacing and SDK runtimes were unchanged from revision 8. Temporal-quality and renderer changes followed in revision 10; see [Quality and performance](../quality-and-performance.md).

Extract the complete archive into a new folder and launch Bloodborne.exe. Keep your game files, saves, mods and settings. Revision by TatsunaKyo; original project credits and third-party licenses are retained.
