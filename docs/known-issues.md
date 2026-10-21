# Current reports

**Published baseline: R55, 21 October 2026 (CEST).** [Later source maintenance](maintenance.md) requires a subsequent binary build. Gameplay evidence, controlled tests and unverified hardware have different scope.

## Latest gameplay evidence

| Report | Status |
|---|---|
| Repeated cemetery-exit traversal hitch | **Open.** Repeats at the streaming boundary with FG on or off; an existing or reset shader cache has not established a fix. |
| Uneven delivery around 120 output FPS | **Open.** Reported 119–121 variation and movement unevenness need real/displayed cadence measurements; the counter is not clamped to hide changes. |
| Character halos/ghosting, especially stairs | **Open.** Camera/depth/history checks do not establish affected-scene disocclusion/transparency quality. |
| Brief foreground/flashing geometry when turning | **Open.** Earlier scene-specific corrections do not establish that every current artifact is gone. |
| NVIDIA FG preset C error or unknown model | Requests and feedback are present. Driver acceptance and evaluated-model evidence remain required. |
| RTX Encore NR unavailable/crashing | Third-party NR is unsupported here. New mod configurations disable NR and no NR DLL is bundled. Depth-view/NR failures are separate from FG initialization. |
| Blood Echoes multiplier | Recheck positive awards, recovery, spending and save/reload against genuine game behavior. |

R41–R55 address reproduced invalidation, locking, resource churn, cache and motion-input cases. The [R55 integration record](investigations/2026-10-20-upstream-integration.md) states each check's scope; none guarantees a cemetery-route fix or exact physical 120-Hz delivery.

## Packaging and UI maintenance

- R53's packaged 30-real-FPS regression mixed current scripts with old patch data. R54/R55 replace and verify all startup/runtime sources, including XML and red-zone data. Modern caps/Auto supersede legacy preferences; incompatible executables retain their deliberate fingerprint guard.
- The R55 Achievements page can fail because trophy UI constants were lost in integration. Current source restores them and tests rendering/filtering.
- Current source fixes the overlay's four-label/ten-resolution mismatch and the ultrawide transition restart warning.
- Current source fixes the release assembler's overwritten final ZIP path. This does not change an already-published download.

## Inherited reports and implementation limits

The empty character-creation preview and some AMD world-loading reports need current hardware comparisons. They are not established failures of every installation. The HUD remains in FG input; HUDless colour/UI recomposition is unfinished. Native Supermedo FSR/DLSS FG is SDR-only, while the existing provider routes retain HDR10. Native DLSS selection needs restart. Dynamic MFG, XeSS FG/XeLL and AMD ML FG are not included Vulkan backends.

Earlier NameError, ignored-checkbox, background-refocus and legacy stable-tag corrections remain in their [revision records](releases/index.md). Hardware evidence is revision-specific: [Compatibility](compatibility.md).

## Reproduction and capture

**Capture-Traversal.cmd** works with FG on or off and needs no F8 readback. **Capture-NVIDIA-FG.cmd** optionally captures tagged images and still exports CPU logs without images. Review diagnostics before manually sharing them; nothing uploads automatically.

Compare the same save/route/settings and report revision, GPU/driver, Windows version, both resolutions/caps, upscaler/model, FG provider/multiplier and HDR. [Capture guide](performance.md#comparing-a-change-during-play) · [Verification scope](testing.md)
