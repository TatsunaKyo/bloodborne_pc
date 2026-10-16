# Revision 44

This build addresses incorrect draw descriptors and CPU contention in the
parallel renderer. It includes the full Windows runtime in one ZIP with its
matching SHA256 file.

- Texture helpers receive the same immutable shader-data snapshots as the draw
  being recorded. They no longer fall back to shared data already updated for
  a later draw. All exit paths restore the helper's previous thread-local state.
- Speculative shader-template cloning runs outside the registry publication
  lock. A suspended background worker cannot keep the graphics thread waiting
  for that deep copy. Published templates are immutable.
- Long draw-pipeline and texture-helper waits block after a short spin rather
  than consuming a runnable CPU thread until the work completes. The change
  preserves packet order, memory ownership and the required synchronization.
- Hitch reports retain span start/end timestamps and show only the portions
  overlapping the current frame's pre-flip and preparation phases. Extra coarse
  scopes identify resource binding, render-target and vertex-input preparation.

## Verification

The R43 control reads incorrect descriptors in 144 of 576 handoff cases; the
corrected handoff passes all 576, including early exits and helper reuse. The
same checks pass with AddressSanitizer and UndefinedBehaviorSanitizer.

The production shader-preparation fixture reproduces the R43 lock being held
while cloning the template. Current code permits graphics-thread publication
during both cloning and guest-memory reads, with safe module-list rechecks.

In a deliberately held 40 ms task, R43 consumes approximately 40 ms of waiting
thread CPU time; current draw/helper waits consume approximately 0.13 ms.
Production-header checks also exercise ring wrap/backpressure, 6,000 drain
handoffs and 10,000 texture-helper handoffs. These are controlled CPU tests,
not a measurement of the cemetery route or a promised in-game FPS gain.

The complete Windows cross-build passed. All six compiled-launcher checks
passed using real Tk widgets, including startup, FG presets, geometry, window
settings, updates and XeSS. The overlay fixture passed 1,960 layouts across
four output sizes and both supported languages. The new handoff/wait checks
also passed AddressSanitizer and UndefinedBehaviorSanitizer.

## Remaining target validation

The owner's R43 log confirms the roughly 69 ms hitch occurs mostly before the
GPU-thread flip; that run already used separate graphics/presentation queues.
The recent 48 ms draw-pipeline wait narrows the investigation, but the old
250 ms aggregate cannot prove which operation held up that frame. R44's clipped
CPU-span reports improve that attribution without adding normal-frame logging.

Windows compilation, package/UI checks and CPU/dispatch tests are reported
separately from actual Bloodborne/NVIDIA execution. This environment cannot
validate the owner's cemetery route, displayed 120 FPS cadence or all image
reconstruction/foreground artifacts. This release does not claim those target
symptoms are conclusively resolved, and it does not clamp the FPS counter to 120.

The native DLSS runtime remains the default. The experimental RTX 20/30 FG mod
remains opt-in and the original SR/FG libraries and required search paths are
retained. Driver feedback still determines whether a requested FG preset is
confirmed; selecting C alone is not proof that the driver evaluated model C.

Keep the new run's last_run.log when comparing the same route. Source history,
verification and compact reusable build recovery are included in the ZIP.
