# Bloodborne Windows v1.6 — TatsunaKyo revision 9

I corrected the Play layout after the DLSS preset dropdown shifted left and the NVIDIA FG multiplier overlapped Output. The preset now lines up with the other quick settings, and the multiplier has a separate row above Output. Both optional rows keep their assigned positions when hidden and shown again. At smaller window sizes and higher DPI, the banner shrinks and the Ready check text wraps to leave room for the settings.

I kept Show performance overlay on Play and replaced the separate preset-overlay checkbox with Customize overlay…, which opens the options in Display & FPS. That keeps the main page simpler while leaving preset, input/output resolution, FG mode and PC latency independently selectable there and in the in-game menu. The link also works with Enter or Space.

I extended Infinite Stamina to cover the continuous drain used while running, plus direct character/script updates and state synchronization. My earlier attack fix missed those paths. The extra hooks use the game's existing no-consumption branches for the player; they do not change maximum stamina, regeneration or NPC stamina. All 23 hook signatures were checked against the privately supplied 1.09 executable.

I rebuilt both Bloodborne.exe and bin/bb-probe.exe. The UI regression checks exercise English/Russian, three window sizes, 100/150/200% scaling and six sequences of upscaler/FG changes. They check alignment, visibility, overlaps, available space and the overlay link using real Tk widgets and the Python entry point extracted from the rebuilt launcher. Cheat tests execute the actual Windows-compiled runtime object and the original continuous stamina updates, including 50 consecutive drain ticks, disabled cheats, NPCs, negative stamina and regeneration. No game code or assets are distributed.

My Windows 11 / RTX gameplay results and the continuous-running check are documented in [Testing and known issues](../testing.md). I kept the graphics providers, FG pacing and SDK runtimes unchanged from Revision 8. Temporal-quality and renderer changes followed in Revision 10; see [Quality and performance](../quality-and-performance.md).

Extract the complete archive into a new folder and launch Bloodborne.exe. Keep your game files, saves, mods and settings. Revision by TatsunaKyo; original project credits and third-party licenses are retained.
