# Current reports

I keep confirmed problems, old reports and hardware coverage separate. A missing test on a different GPU does not mean that the feature is broken there. Likewise, a report from an older revision is useful, but it needs a current-build comparison before I call it a current regression.

## Launcher startup in Revision 26

Revision 26 stops before opening the launcher with `NameError: UPDATE_DIR is not defined`. I reproduced it using the delivered executable and removed the obsolete updater cleanup reference in [Revision 27](releases/windows-v1.6-tatsunakyo.27.md). Use the latest build instead. The startup checks now exercise the real main function and the Windows executable's normal entry point, as well as the existing interface and runtime tests.

## Latest gameplay evidence

The cemetery test with [Revision 34](releases/windows-v1.6-tatsunakyo.34.md) finally resolved the flashing and duplicated coffins on my Windows 11 / RTX 5070 Ti PC with NVIDIA DLSS FG. The correction checks each pose binding behind a shared mesh and avoids positional history for instance slots without a verified object mapping. I am keeping those protections intact.

I previously found NVIDIA FG choppy at 60 real + 60 generated FPS, while 146 output (73 + 73) felt smoother on my 154 Hz / G-SYNC setup. In my latest Revision 35 retest that particular effect is no longer happening. I am keeping it under observation before calling it resolved. Revision 35 corrects a simulation-token handoff race and moves capped NVIDIA FG pacing to Reflex before simulation.

I still see a traversal hitch when leaving the cemetery and uneven frame delivery while rotating the camera. My latest recording stays near 120 output FPS, but its real-frame graph reaches roughly 22 ms and then drops into shorter intervals; the PC-latency readout also spikes. That is enough to make movement feel uneven despite the average FPS. The recording alone does not identify whether each spike comes from compilation, streaming, GPU work or presentation. Revision 36 removes unnecessary patch-directory checks and per-element cache-table copies during shader preparation; I still need to repeat the route and camera movement with the rebuilt package.

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
- Dynamic NVIDIA MFG, XeSS FG/XeLL, AMD ML FG and selectable FG model presets are separate roadmap items. Their unavailable controls are not broken implementations in this package.

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
