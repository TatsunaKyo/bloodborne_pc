# Current reports

R45 is a targeted investigation build. The owner's R44 log still shows the
69.88 ms cemetery hitch and the reported FG/reconstruction symptoms remain
open. See `docs/investigations/2026-10-16-frame-pipeline.md` for the measured
critical phase, inactive-helper caveat, upstream memory comparison and the
single-run capture procedure. R45 does not claim a target-game fix.

I keep confirmed problems, old reports and hardware coverage separate. A missing test on a different GPU does not mean that the feature is broken there. Likewise, a report from an older revision is useful, but it needs a current-build comparison before I call it a current regression.

## Launcher startup in Revision 26

Revision 26 stops before opening the launcher with `NameError: UPDATE_DIR is not defined`. I reproduced it using the delivered executable and removed the obsolete updater cleanup reference in [Revision 27](releases/windows-v1.6-tatsunakyo.27.md). Use the latest build instead. The startup checks now exercise the real main function and the Windows executable's normal entry point, as well as the existing interface and runtime tests.

## Latest gameplay evidence

The cemetery test with [Revision 34](releases/windows-v1.6-tatsunakyo.34.md) finally resolved the flashing and duplicated coffins on my Windows 11 / RTX 5070 Ti PC with NVIDIA DLSS FG. The correction checks each pose binding behind a shared mesh and avoids positional history for instance slots without a verified object mapping. I am keeping those protections intact.

I previously found NVIDIA FG choppy at 60 real + 60 generated FPS, while 146 output (73 + 73) felt smoother on my 154 Hz / G-SYNC setup. In my latest Revision 35 retest that particular effect is no longer happening. I am keeping it under observation before calling it resolved. Revision 35 corrects a simulation-token handoff race and moves capped NVIDIA FG pacing to Reflex before simulation.

I still see a traversal hitch when leaving the cemetery and uneven frame delivery while rotating the camera. My latest recording stays near 120 output FPS, but its real-frame graph reaches roughly 22 ms and then drops into shorter intervals; the PC-latency readout also spikes. That is enough to make movement feel uneven despite the average FPS. The cemetery hitch repeats at the same boundary, including later passes. I am treating that as a traversal/streaming report. R36's shader-cache preparation changes did not establish its cause. R37 removes the shared synchronous file-object path from positioned reads of read-only Windows game assets: each request uses its own offset/event on a separate overlapped reader, while close waits for outstanding reads. The Windows regression checks concurrent reads, exact data, cursor preservation and descriptor lifetime. This removes a concrete streaming bottleneck; the repeatable cemetery route still needs a gameplay comparison before I can mark its hitch resolved.

Background Pause also left the music playing. Revision 36 connects the audio device and output threads to the same pause state, preserving queued samples and resetting their cadence on resume. The regression reproduces the old behavior and checks repeated pause/resume, startup out of focus, silent/failed devices and closing a paused port.

I also reproduced the startup focus failure at the window event-pump boundary: starting in the background can leave the 30 FPS policy active after returning to the game. Revision 29 reconciles the actual foreground window instead of relying on event order. The production-code regression covers a single return to 65 real / 130 total FPS, the pause gate and FG/Reflex policy.

The optional real-frame graph helps compare render delivery. NVIDIA's displayed-frame timing also includes hardware scheduling, so I keep that distinction when comparing FG. The other older reports below remain available for comparison.

| Earlier report to recheck | What to compare |
|---|---|
| Blood Echoes multiplier | Award source, selected multiplier and the value before/after the award. |
| Uneven delivery with NVIDIA FG | Same scene, real/output caps, HDR, upscaler and FG mode; distinguish real-frame graph from displayed-frame measurements. |

## Inherited reports and implementation limits

- The upstream empty character-creation preview and some AMD world-loading crashes need confirmation on this fork/current hardware. They are inherited reports, not confirmed failures of every current installation.
- The game's HUD is still included in FG input. HUD separation remains planned; moving UI can produce interpolation artifacts.
- Dynamic NVIDIA MFG, XeSS FG/XeLL and AMD ML FG remain separate roadmap items. NVIDIA FG presets A/B/C now have a per-installation profile selector; C requires the newer NVIDIA beta runtime and the menu distinguishes driver confirmation from an unverified request. Their unavailable controls are not broken implementations in this package.

## Resolved or superseded reports

| Report | Available result |
|---|---|
| Flashing/duplicated geometry with NVIDIA FG | Revision 34 confirmed in the affected cemetery on Windows 11 / RTX 5070 Ti; its motion-history protections remain included. |
| Ignored in-game checkboxes | Actual click/navigation/save checks cover the shared controls; the interface work remains included. |
| Fixed FPS readout with NVIDIA FG | The overlay uses confirmed NVIDIA presentation counts and has an optional active-FG field. |
| Background pause failing to regain focus | Cooperative pause/refocus handling and its regression remain included. |
| Stable release with a legacy `-preview` tag rejected by updater | Reproduced using the published Revision 21 metadata and corrected in Revision 22; existing public tags stay intact. |

If one of these happens again, report the current revision and reproduction details. More hardware coverage belongs in [Compatibility](compatibility.md), and the automated checks are in [Testing](testing.md).

## Code review after Revision 25

I corrected the swapchain recovery lock order and synchronized its GPU drain in Revision 26. The updater now verifies the downloaded SHA-256, build identity, binaries, runtimes and Windows archive paths before starting the candidate. These were reproduced at their production code boundaries; they remain separate from the gameplay comparisons above. [Review findings and remaining work](code-review-2026-10-13.md) explains the checks and the next comparisons.

## Revision 38 follow-up

The owner confirms that Revision 37 did **not** remove the repeated cemetery-exit traversal hitch. R38 adds range-based preparation of large file-read destinations through the existing GPU invalidation callback. Reads of at least 64 KiB notify intervals of at most 1 MiB before the existing page touches. Windows skips already writable spans, avoiding GPU synchronization for ordinary CPU staging buffers. This reduces repeated CPU protection faults during asset streaming while retaining readback, dirty tracking, draw/upload ordering and the per-page fallback. It changes neither shader compilation nor resource lifetime fences. A protected-memory regression checks unchanged destination bytes, unaligned buffers, small reads and invalid-range guards. Its reduction in fault count is not a target-gameplay result. The cemetery hitch remains open.

The owner also reports C working in other applications but producing an error here. R38 corrects Streamline's disabled OTA flags and adds process/profile telemetry and exact error categories. Actual C execution and the cemetery route still require the target Windows/NVIDIA comparison; no Linux test establishes either.

R41 still reproduces the reported problems: its latest launch log includes a 48.19 ms real-frame interval. [R42](releases/windows-v1.6-tatsunakyo.42.md) corrects fetch-record tails that invalidated cache entries, makes motion vertex binaries relocatable across launches, fixes stale completion-tick capture in command-buffer reuse, permits FG/render queue overlap under explicit input ownership, removes native-AA prefiltering from temporal launches, and separates model selection from driver DLL replacement. Its automatic CPU frame path supplies the attribution missing from that R41 hitch. The cemetery boundary, smoothness on the owner's NVIDIA system, actual C model and final DLSS image quality remain runtime-verification items.

[R43](releases/windows-v1.6-tatsunakyo.43.md) additionally fixes viewport-dependent camera projection and depth/pass pairing, removes guest reads from speculative registry lock scopes, repairs recording-chunk handoff and separates NVIDIA presentation from rendering when a second same-family queue is available. The camera error is reproduced against vertex projections and the corrected shader executes on software Vulkan. The target-game symptoms remain open until measured in-game; queue-routing/ownership tests do not establish fixed display cadence.

[R44](releases/windows-v1.6-tatsunakyo.44.md) fixes the texture-helper draw-snapshot handoff, moves speculative template cloning outside the registry lock, replaces long draw/helper busy waits with notified waits, and adds frame-overlap CPU attribution. The R43 controls reproduce each CPU correctness/contention defect. The cemetery route, displayed FPS cadence and remaining image artifacts still require target-game verification; synthetic tests do not establish those outcomes.
