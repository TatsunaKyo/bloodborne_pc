# Hardware compatibility

My main gameplay PC runs Windows 11 with a GeForce RTX 5070 Ti. I welcome results from other configurations, especially Radeon and Intel GPUs. I record the revision and type of evidence so the table stays useful.

**Tested** means gameplay evidence on the named setup. **Partially tested** means the implementation has component/contract checks or only some gameplay paths covered. **Unverified** means I do not yet have a reviewed gameplay result for that hardware. These labels describe coverage, not a promise that an unverified feature fails.

| Setup / feature | Coverage | Evidence |
|---|---|---|
| Windows 11 / RTX 5070 Ti, normal gameplay and DLSS | Tested | Maintainer gameplay and the Revision 18 scene capture; DLSS Performance, preset L was recorded. |
| Same setup, NVIDIA x2 FG with HDR10 | Tested | Captured configuration and latest Revision 19 affected-scene report; flashing resolved in that report. |
| Other NVIDIA GPUs, higher MFG multipliers | Unverified | Capability gating and runtime integration exist; no broad GPU gameplay matrix yet. |
| FSR FG SDR/HDR pipeline | Partially tested | Capture/FI/OF, HDR highlights, resize/lifetime and Vulkan-validation checks on Lavapipe; this is pipeline evidence, not Radeon gameplay. |
| Radeon gameplay, AMD Anti-Lag 2 | Unverified | Vulkan adapter/capability/input/present checks exist; Radeon driver gameplay results are still needed. |
| Intel gameplay, XeSS SR | Unverified | Seven quality modes, initialization contracts, scene sizing and shared controls are checked; Intel gameplay remains unverified. |
| Windows 10 and other monitors/drivers | Unverified | Supported platform target; broader current-build results are welcome. |

The public seed records are in [hardware/compatibility.json](hardware/compatibility.json). Only reviewed results should become confirmed rows. [Generate Support Report](support-reports.md) now provides an optional anonymous JSON submission, which stays unreviewed until actual gameplay evidence is reviewed.

Provider requirements and fallbacks: [Upscaling](upscaling.md), [FG](frame-generation.md) and [latency](latency.md). For existing reports rather than coverage gaps, use [Current reports](known-issues.md).
