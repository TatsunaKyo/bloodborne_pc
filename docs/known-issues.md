# Current reports

I keep confirmed problems, old reports and hardware coverage separate. A missing test on a different GPU does not mean that the feature is broken there. Likewise, a report from an older revision is useful, but it needs a current-build comparison before I call it a current regression.

## Launcher startup in Revision 26

Revision 26 stops before opening the launcher with `NameError: UPDATE_DIR is not defined`. I reproduced it using the delivered executable and removed the obsolete updater cleanup reference in [Revision 27](releases/windows-v1.6-tatsunakyo.27.md). Use the latest build instead. The startup checks now exercise the real main function and the Windows executable's normal entry point, as well as the existing interface and runtime tests.

## Latest gameplay evidence

Flashing and duplicated assets still occur in Revision 33 with NVIDIA DLSS FG enabled on my Windows 11 / RTX 5070 Ti PC. The latest cemetery test showed extra coffins appearing in the air and disappearing again; the earlier Hunter's Dream report also remains open. Turning FG off removes most of the problem. Revision 33 corrected two frame-tracking errors, but did not resolve this visual report.

[Revision 34](releases/windows-v1.6-tatsunakyo.34.md) checks the pose binding behind shared meshes and refuses positional history for instance batches without a verified object mapping. Its production-code control reproduces incorrect history matches in R33 and checks that valid actor, weapon and known world-instance motion remains available. The cemetery still needs a gameplay check before I call the report resolved.

I also reproduced the startup focus failure at the window event-pump boundary: starting in the background can leave the 30 FPS policy active after returning to the game. Revision 29 reconciles the actual foreground window instead of relying on event order. The production-code regression covers a single return to 65 real / 130 total FPS, the pause gate and FG/Reflex policy.

The earlier Hunter's Dream report confirmed that the Revision 19 fixes worked before this regression. I am still collecting pacing comparisons; the optional real-frame graph helps assess them. The other older reports below remain available for comparison.

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
| Earlier Hunter's Dream flashing report | Revision 19 was confirmed on Windows 11 / RTX 5070 Ti at the time. The later recurrence remains open above. |
| Ignored in-game checkboxes | Actual click/navigation/save checks cover the shared controls; the interface work remains included. |
| Fixed FPS readout with NVIDIA FG | The overlay uses confirmed NVIDIA presentation counts and has an optional active-FG field. |
| Background pause failing to regain focus | Cooperative pause/refocus handling and its regression remain included. |
| Stable release with a legacy `-preview` tag rejected by updater | Reproduced using the published Revision 21 metadata and corrected in Revision 22; existing public tags stay intact. |

If one of these happens again, report the current revision and reproduction details. More hardware coverage belongs in [Compatibility](compatibility.md), and the automated checks are in [Testing](testing.md).

## Code review after Revision 25

I corrected the swapchain recovery lock order and synchronized its GPU drain in Revision 26. The updater now verifies the downloaded SHA-256, build identity, binaries, runtimes and Windows archive paths before starting the candidate. These were reproduced at their production code boundaries; they do not change the latest affected-scene gameplay report above. [Review findings and remaining work](code-review-2026-10-13.md) explains the checks and the next comparisons.
