# Bloodborne Windows v1.6 — TatsunaKyo Revision 11

I started the roadmap with a small frame-pacing update. Revision 10 stays available with its original ZIP and source commit; this is a separate build so I can compare the two at the same settings.

## What I changed

I found that, after a stalled frame, the real-frame limiter could leave its next deadline in the past. If several frames were waiting, they could then be submitted almost back to back. That also gives FG an uneven stream of real frames to work with.

I changed the next deadline to allow one full real-frame interval after the actual submission. A late frame starts a fresh interval instead of triggering a burst of queued frames. I kept the game's vblank notifications and simulation timing separate from generated frames.

I also reused the Windows runtime's existing high-resolution waitable timer for the VideoOut waits and the FSR FG half-frame gap. FSR keeps its interpolation completion wait and resource protection. NVIDIA's generated-frame scheduling remains with Streamline, with Reflex available as before.

The ordinary FPS cap and optional FG output cap still work separately. For example, 75 real FPS with x2 can give up to 150 output FPS; adding a 130 output cap makes the real-frame ceiling 65. I kept the one-frame queue and did not force a 120 output cap.

## Checks and the next comparison

The production scheduling helper passes queued-frame tests at 30, 60, 65, 75, 90 and 120 FPS, including 50 ms and five-second stalls and rendering slower than the selected cap. Pause/refocus, stopping while paused, uncapped mode, changing caps and timer waits pass the native checks.

I rebuilt the Windows renderer and launcher. The compiled launcher passes shared-settings and update-channel checks, plus 108 actual Tk layouts covering English/Russian, three window sizes and 100/150/200% scaling. ImGui control activation and settings round trips also pass. The package includes the logs, with previous GPU and cheat checks keeping their original revision labels.

My gameplay setup is Windows 11 with an RTX 5070 Ti. For this first pacing change, I want to compare the same scene in both builds with FG off, FSR x2, NVIDIA x2 and MFG, then check the caps, HDR and returning to the window. I am keeping the broader pacing issue open while making those comparisons. The automated checks run on a Linux build host; the Windows timer fixture is compiled, but Wine cannot execute it here because its server socket is blocked.

The firing crash with certain cheat combinations, continuous-running stamina, character preview and AMD world loading remain on the roadmap. I want to address those before adding the next batch of cheats. The existing graphics, overlay, window and cheat choices are retained.

## Installation

Extract the full Revision 11 ZIP into a separate folder. Keep your existing saves, mods and settings. Update the complete application: both `Bloodborne.exe` and the native renderer in `bin/bb-probe.exe` are rebuilt. `Start-Verified-Launcher.cmd` checks the launcher hash before opening it.

No game files are included. You need your own decrypted Bloodborne CUSA03173 1.09 dump.

Maintained by TatsunaKyo. Original port, shadPS4, community patch and vendor credits and licenses are preserved.
