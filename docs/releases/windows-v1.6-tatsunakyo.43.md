# TatsunaKyo Revision 43 — camera guides and renderer synchronization

R42 still shows the owner's cemetery hitch, output-FPS variation and temporal
artifacts. This revision repairs reproduced code defects; target-game testing
on the owner's RTX 5070 Ti remains required before those reports can be closed.

## Changes

- **Viewport-aware camera motion.** The projection now includes the signs of
  the actual G-buffer viewport. R42 always assumed one orientation, producing
  wrong background motion during pitch and vertical movement. This affects
  temporal reconstruction and the scene guides passed to FG. Field of view
  remains positive when the screen projection has a negative vertical scale.
- **Camera and depth belong to the same pass.** A later G-buffer depth target
  captures its own camera instead of inheriting the first camera of the frame.
  Each pass compares with the previous completed scene. Preliminary cameras
  cannot replace that baseline; missing final-pass data cannot use their camera.
- **Speculative workers no longer hold up shader publication during guest
  reads.** The shared registry lock no longer covers resource-table walking,
  fetch parsing or specialization. Workers safely recheck the current module
  list and yield if a publication is in progress. Fault recovery clears its
  expired jump-buffer pointer.
- **Recording keeps a current chunk during handoff.** A replacement is installed
  before publishing the previous chunk, protecting recording re-entry and order.
- **NVIDIA presentation uses a second same-family queue when available.**
  Presentation acquisition/FG waits previously shared the guest-rendering queue.
  The presenter now submits to its own queue, retaining frame-ready semaphores,
  SDK input-ownership fences and the common queue-operation exclusion used by
  device drains. Font uploads use the presentation queue. Adapters with one
  queue and non-NVIDIA adapters retain the previous queue selection.
- **Current-run evidence in the ordinary log.** `last_run.log` includes launcher
  version and selected graphics/pacing settings even without developer profiling.
  The bounded hitch journal also covers draw-pipe waits, host copies, deferred
  guest signals, shader publication, sparse copying/VMA lookup and page protection.

The original SR/FG DLLs, required SR search paths, existing presets and isolated
opt-in RTX 20/30 mod path are retained. The FPS counter is not clamped or snapped
to the configured cap. No shader-cache-format change is introduced by R43.

## Verification and limits

The camera regression compares independent vertex projections with the actual
camera decoder and production motion kernel across 24 synthetic scenes, all four
viewport sign combinations, vertical movement, pitch and jitter. The unchanged
R42 control fails 81,965 of 151,320 comparisons (peak 7.76528 pixels at 97x65).
The corrected CPU float32 path passes every comparison, peak 0.000025 pixels.
Execution of the production SPIR-V on native Mesa Lavapipe passes all 151,320
comparisons, peak 0.002002 pixels after RG16F storage.

Deterministic concurrency fixtures reproduce the old registry obstruction and
missing recording chunk, then verify publication during a paused guest read,
module-vector growth, busy-registry fallback, recovered faults and command order.
Actual submission methods are captured at Vulkan entry points to check queue
selection and acquisition/frame-ready waits. These are dispatch/ownership tests,
not measurements of NVIDIA GPU parallelism.

Windows cross-compilation, launcher-bytecode/UI and package/dependency checks are
reported separately in `source/verification/summary.json`. No Windows bootloader,
Bloodborne session or NVIDIA hardware was executed locally. The exact cemetery
route, final character-halo/asset behavior, actual C execution and constant 120
displayed frames per second have **not** been confirmed by these tests.

Delivery: one complete Windows ZIP and its matching `.zip.sha256`. Source,
verification and compact recovery material are inside that ZIP.

Technical attribution and original log observations:
[investigation](../investigations/revision43.md).
