# Bloodborne: The Crowned Workshop — Revision 13

I added Radeon Anti-Lag 2, brought the real-frame FPS control into the in-game menu and corrected several sources of invalid temporal data after reports of flashing assets. This revision also gives the fork its own workshop identity and crowned TK emblem.

## AMD Anti-Lag 2

You can enable it in **Graphics** or from **Insert / L3+R3** while playing. I use the driver's `VK_AMD_anti_lag` interface on Radeon GPUs that expose its feature. The launcher probes that support, and the native renderer checks it again when creating the device. Unsupported devices keep their normal rendering path.

The input marker runs before the game samples the pad. I carry its frame ID through submission to the matching real presentation; FSR's extra frame and redisplays do not become new simulation frames. Anti-Lag does not add another FPS cap, so the real-frame and optional FG-output limits continue to work as before. It is independent of the upscaler and FSR FG. NVIDIA Reflex remains independent too.

## Real FPS in the in-game menu

I added **Real game FPS**, with Auto, Custom cap and No cap, plus a drag control and exact number field. You can enter 75, 93 or another value between 30 and 120. The shared preference is also used by Display & FPS in the launcher, and I migrate the older launcher-only cap without losing it.

Choose **Unlocked** timing in the launcher to change game FPS during play. A session started with a fixed game-timing patch keeps that timing, so its live control is disabled with an explanation. I still recommend 120 or below for real game frames. The separate FG-output control remains available from 30 to 1000, since generated frames do not advance game logic.

## Flashing assets and temporal data

I found cases where the draw and its motion tracking could use different data:

- The recording thread read camera constants from guest memory even though the draw used an earlier constant-ring snapshot. I now read the same snapshot as the draw, including small-skeleton motion tracking.
- Cached index bounds could survive changed contents at the same address for several frames. I now verify the contents on each draw and immediately reject history when the mesh changes. Unchanged meshes still reuse their range scan.
- A point behind the previous camera, or an extreme vector, could overflow the FP16 motion texture. I reject those vectors before they reach reconstruction or FG. GPU-written index data is also excluded from CPU-derived object history.

These changes cover the shared reconstruction path, including use without FG. I want to compare the affected scenes on the gameplay PC before closing the flashing-assets report; other causes may remain.

## The Crowned Workshop

I wanted an identity that feels like my own workbench: a quiet hunter, worn tools, lantern light and a pale-red moon through a Gothic window. The banner has the project name and my signature, with an original crowned TK emblem. I kept the feature list in the README, where it is easier to read.

The assets include two 1800 × 700 PNG banner concepts, editable SVG lettering, the separate vector emblem, transparent icon exports and a Windows ICO. The launcher window and native component icons use the new emblem. Bloodborne.exe and the repository URL keep their existing names for compatibility.

## Checks and hardware

I rebuilt the launcher and native Windows components. The compiled launcher goes through 108 layout checks and 84 actual XeSS popup selections. The actual ImGui controls select, edit and save the real FPS cap in both languages, and check that fixed timing and unsupported Anti-Lag controls stay disabled. The native Anti-Lag adapter checks input/present ID matching, queued frames, focus, device lifetime and presentation progress during a driver input wait. FPS, camera snapshot and reused-index history checks pass too.

The shader fixture includes behind-camera reprojection, stale/nonfinite object vectors and FP16 overflow cases. It is included for running on the target Vulkan device. The package logs distinguish executed build-host checks from compiled GPU fixtures and earlier retained results.

My gameplay setup for this fork is **Windows 11 with an RTX 5070 Ti**. I still need a Radeon gameplay result for the new Anti-Lag integration and a comparison of the reported flashes on this revision. The shooting crash, broader frame pacing, continuous-running stamina and other open cases remain in [Testing and known issues](../testing.md).

## Installation

Extract the full **Bloodborne-Windows-v1.6-TatsunaKyo-Revision-13.zip** into a separate folder and keep your saves, mods and preferences. Use the entire package, since the launcher, renderer and shared settings changed together. `Start-Verified-Launcher.cmd` checks the included launcher before opening it. The matching `.zip.sha256` file gives the archive checksum.

No game files are included. You need your own decrypted Bloodborne CUSA03173 1.09 dump.

Maintained by TatsunaKyo. Original game, bbport, Supermedo, shadPS4, community patch and vendor credits are preserved.

References: [Vulkan Anti-Lag API](https://docs.vulkan.org/refpages/latest/refpages/source/vkAntiLagUpdateAMD.html), [matching presentation IDs](https://docs.vulkan.org/refpages/latest/refpages/source/VkAntiLagPresentationInfoAMD.html) and [AMD's integration guide](https://gpuopen.com/learn/integrating-amd-radeon-anti-lag-2-sdk-in-your-game/).
