> Historical/upstream record: statements and test results below describe their original revision or environment. [Current guides](./index.md) · [Current reports](./known-issues.md) · [Published releases](./releases/index.md)

# Integration review after Revision 25

I reviewed the current Windows branch after finishing Revision 25, keeping that package as the comparison point. I focused on the code shared by everyday play: reconstruction, frame generation, presentation, latency controls, live settings, diagnostics, saves and updates. I also revisited the current GitHub guides. My introduction, banner, approved feature illustrations and upstream attribution remain intact.

## Corrections in Revision 26

| Finding | Why it matters | Correction and check |
|---|---|---|
| README badge stayed at Revision 23 | The opening did not identify the build I had delivered. | Generate the badge/notes link from the launcher version; CI rejects a stale badge. Download latest continues to follow the published release. |
| Failed-present recovery held the queue lock before requesting NVIDIA's lifecycle lock | Another lifecycle operation can need those locks in the opposite order. | Enter recovery without the queue lock; retire NVIDIA input ownership first. The production recovery fixture reproduces the old ordering and checks the new scope. |
| Resize/HDR recreation drained the device without consistently excluding client queue operations | The drain shares Vulkan's queue synchronization requirements with submissions and presents. | Lock the GPU drain inside swapchain destruction, after SDK retirement. A held production drain excludes competing queue work. |
| HDR mode change waited for the device twice | Recreation already drains the device before rebuilding its resources. | Use the synchronized recreation drain once. |
| Recreated swapchain kept the previous acquisition slot | A smaller image count could leave the next semaphore access outside its new array. | Reset image/acquisition indices with the new semaphore arrays. The production method covers 49 count transitions: 21 invalid old slots become zero. |
| Update worker started a downloaded executable without validating the published checksum or build | A corrupt or mismatched package could become an installed update despite the release checks. | Reuse the release validator before extraction/execution. The actual worker rejects a wrong checksum and reaches the expected candidate only after complete validation. |
| Update installer ignored the old-launcher wait result | A timeout could start copying while the old launcher was still running; its process handle also lacked an explicit 64-bit return type. | Type the Windows API, check success/timeout/failure and stop before copying when closure is not confirmed. |
| Updater used one shared temporary folder | Two launcher instances could erase each other's staged update. | Give each attempt its own folder and clean rejected downloads. |
| Windows archive names could alias files or name devices | Case checks alone do not cover trailing dots/spaces and DOS device names. | Reject those names, unsafe characters, encrypted entries and excessive expanded sizes before extraction. |
| Nonfinite INI image-tuning values reached the renderer | NaN/infinite values are outside the controls' useful ranges and can propagate through shaders. | Bound them before use; production settings checks load malformed values and verify finite results. |

## Areas reviewed

| Area | What I checked | Remaining work |
|---|---|---|
| NVIDIA FG/MFG and Reflex | Tokens, input-completion fences/epochs, queue/lifecycle order, supported multipliers, independent caps and completed latency reports. Streamline 2.14.1 remains the latest official release checked on 13 October. | Matched real/displayed cadence and focus/resize/HDR comparisons on RTX hardware. Dynamic MFG and FG model selection remain separate features. |
| FSR FG | Owned depth/motion/color, FI/OF submission retirement, history seeding/reset, HDR encoding, pending-frame budget and the half-frame presentation interval. | Measure delivered cadence on Radeon/other hardware before changing the half-frame schedule. Keep the existing software-Vulkan evidence distinct from gameplay. |
| DLSS, FSR and XeSS reconstruction | Provider/size changes, reset propagation, SDK resource layouts, feature retirement and FSR fallback. XeSS 3.0.2 remains the latest official release checked on 13 October. | Particle/transparency/weapon motion coverage and reconstructing the scaled scene earlier in HDR post-processing. These need scene comparisons before joining a release. |
| Temporal history | Immutable draw/camera snapshots, camera discontinuities, index identity/content, skeleton batches, depth rejection and invalid vectors. | Preserve the Hunter's Dream correction while extending motion coverage; avoid lowering precision or resetting every frame to hide artifacts. |
| Frame limits and overlay | Timer phase after wake jitter/stalls, real vs generated caps, negotiated vs observed multiplier, raw real-frame graph and missing/stale Reflex reports. | Individual generated display timestamps are not supplied by the SDK output count. Use actual presentation evidence for output cadence. |
| Window/background | Cooperative pause, live mode policy, minimized/acquisition-failure ownership and refocus. | Real Windows focus/minimize/resize tests with FG and HDR on supported drivers. |
| Shader/pipeline cache | Bounded/checked records, legacy migration, failed preload recovery, accepted-write draining and incompatible profiles. | Compare cold/warm routes and damaged-cache recovery on different drivers. |
| Cheats and save protection | Player-only guarded hooks, instruction mismatch gates, save writer lease, snapshot/restore verification and interrupted recovery. | Blood Echoes awards still need the requested gameplay comparison. Named save profiles remain the next Save Manager stage; no unsupported live snapshots. |
| Launcher/live settings | Seven shared categories, separate DLSS/XeSS quality state, exact FPS fields, persisted live controls and restart exceptions. | Native mouse/remapping and ultrawide/HUD remain on the gameplay roadmap. |
| Diagnostics, updates and release tooling | Whitelisted/redacted reports, inspect-before-export, archive integrity, version/channel compatibility, binary/runtime identity and publication metadata. | Make update installation transactional with rollback; the current copy-over phase can still leave a partial update if interrupted. This needs its own recovery design and tests. |

## Verification

The review adds the existing frame-limit, frame-pacing, background, frame-count/latency, frametime, camera/object-history, settings, FSR-support, XeSS and AMD contract fixtures to portable CI. The XeSS adapter checks all seven modes at four output sizes in SDR/HDR, including execute failure and context recreation. AMD checks input-to-real-present IDs and keeps presentation able to progress during a driver input wait.

The new swapchain test executes the extracted production blocks from Revision 25 and the corrected source. The updater test uses real ZIPs and the actual launcher worker with local transport/process boundaries: altered bytes, runtimes, metadata, checksums, version and Windows paths are rejected before candidate execution. Existing geometry/depth, cache, Support Report, Save Manager and real Tk/ImGui checks remain in the suite. Windows CI also executes native MSVC recovery fixtures and the frozen Python runtime.

These tests cover the code contracts they exercise. My actual gameplay evidence remains in [Compatibility](compatibility.md) and [Current reports](known-issues.md). I still want same-scene comparisons, especially Hunter's Dream with 75 real / 120 output FPS, against Revision 25 before drawing conclusions about driver-level pacing.

## GitHub and documentation

Current guides now include the cache/presentation work and this review. Historical upstream pages and dated releases remain historical records, with their original credits. The README stays focused on features; detailed changes live here and in release notes.

Repository Issues are still disabled in the metadata checked on 13 October. Enable **Settings → General → Features → Issues** to expose the existing bug, performance and feature forms. Actions is already running with pinned actions and read-only workflow permissions. Publication and file uploads stay manual. The social-preview export and a possible documentation site remain lower-priority work.

[Gameplay roadmap](tatsunakyo-next.md) · [Testing](testing.md) · [Release preparation](releasing.md)

References: [Vulkan device-wait synchronization](https://docs.vulkan.org/refpages/latest/refpages/source/vkDeviceWaitIdle.html), [Streamline 2.14.1](https://github.com/NVIDIA-RTX/Streamline/releases/tag/v2.14.1), [XeSS 3.0.2](https://github.com/intel/xess/releases/tag/v3.0.2).
