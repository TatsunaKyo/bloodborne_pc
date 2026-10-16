# R43 investigation and reproduced defects

Baseline: `2fe3a67fc3c2930352bb88af57f881b9b0829494` (R42).

The owner's new `last_run(2).log` runs R42 on an RTX 5070 Ti, 1920x1080 DLSS
input and 3840x2160 output. The accompanying `session(3).json/log` instead
identify R19 on 12 October and cannot profile this R42 run.

At submission 1995, the real-frame interval is 45.77 ms, guest submission
interval 16.64 ms, GPU-thread flip interval 45.58 ms, submit-to-flip 32.98 ms,
preparation 0.19 ms, and present/SDK state 0.06 ms. The recent journal includes
17.95 ms of GNM previous-submission retirement. This locates the delay before
the GPU-thread flip; it does not distinguish all internal waits or prove a
particular filesystem, memory, shader, or GPU bottleneck. Another hitch at
submission 3578 includes an 8.45 ms Vulkan image allocation.

The steady real-frame mean is around 59.97–60.00 FPS, with SDK output samples
including 119.525 and 120.239 FPS. CPU presentation/sample-window timing is
insufficient to assert display cadence. The FPS value is not clamped to 120.

## Reproduced defects

- The old camera decoder ignores G-buffer viewport signs. Static vertex
  projection and the production camera kernel disagree during vertical travel
  and pitch. R42 control: 81,965 of 151,320 pixel comparisons fail, peak
  7.76528 pixels on 97x65 synthetic scenes. Current code: no failures, CPU
  float32 peak 0.000025 pixels. The same production SPIR-V executes on native
  Lavapipe across 24 scenes: peak 0.002002 pixels after RG16F storage.
- The first captured camera previously survived later G-buffer depth targets.
  Each candidate now belongs to its depth/viewport and compares with the
  previous completed frame. A preliminary pass neither replaces that baseline
  nor forces a reset of an otherwise continuous final scene. Missing final-pass
  camera data cannot be combined with another pass's camera. Field of view uses
  the magnitude of the signed screen projection.
- The speculative shader worker holds `programs_mutex` across guest-memory
  walking, fetch parsing and specialization. A paused guest read demonstrably
  blocks critical-thread shader publication in R42. Current code drops the
  registry lock before guest reads, reacquires it briefly to recheck modules,
  and yields speculative work if publication is busy. A test grows the module
  vector and registry during the paused read and confirms safe selection.
- The worker's fault recovery previously retained a pointer to an expired jump
  buffer. Recovery now clears that thread-local pointer.
- Chunk publication previously exposed a null current recording chunk before
  allocating its replacement. Re-entry at that point is reproduced in the R42
  control. Installing the replacement first keeps re-entered commands valid
  and ordered after the published commands.

Camera/recording investigation cross-checked the original project's fixes:
[0.3](https://github.com/deadinside28/bloodborne_pc/commit/4d4d20812c0af23a11c8b8d40f5e06a9054925ef),
[0.5-pre4](https://github.com/deadinside28/bloodborne_pc/commit/10baf9df25f106da9013433a2e7348839baf917a),
and [0.51](https://github.com/deadinside28/bloodborne_pc/commit/3c57da4198ad62039f63f33bfd205b9916518acf).
The newer upstream memory-layer page-table rewrite is absent from this fork;
its measured fix must not be represented as a fix to this fork's different
memory path. Camera coordinates here retain +y-up screen clip coordinates for
the existing TAA and NVIDIA matrices, with viewport signs included in projection.

## Queue separation and attribution

NVIDIA devices with at least two queues in the selected graphics family now
request a second same-family queue for presentation. `present_scheduler` submits
to that queue; guest rendering and sparse binds remain on queue zero. The existing
frame-ready/acquisition semaphores and SDK input-retirement fences are retained.
Font uploads run on the presentation queue. One-queue devices and other vendors
retain queue zero. Dispatch fixtures reproduce R42 routing every submission to
the graphics queue, then verify independent routing with the required waits.
These checks do not measure target NVIDIA scheduling or display timing.

The automatic journal now includes draw-pipe drain, host-copy drain, deferred
guest signals, shader registry publication, sparse guest copying/VMA lookups and
page protection. The ordinary last-run log records its version and requested
settings, so a stale optional session cannot silently supply another revision's
configuration. The CPU path retains the distinction between guest submission,
GPU-thread processing and actual hardware execution.

## Outstanding validation

No Windows target-game/NVIDIA execution is available locally. The tests above
reproduce specific defects; they do not establish that the cemetery route,
119–121 output variation, character halo, or every transient asset artifact is
resolved on the owner's system. Do not publish a stronger claim.

## Owner runtime feedback, 16 October 2026

The owner's R43 video still shows FPS variation, the cemetery-route hitch and
reconstruction/foreground geometry artifacts. The revision is not validated as
resolving those reported symptoms.

In the supplied R43 log extract, submission 1866 has a 69.19 ms real interval,
16.48 ms guest submission interval, 68.80 ms GPU-thread flip interval and
56.13 ms submit-to-flip delay. Preparation is 0.33 ms and present/SDK CPU work
0.08 ms. The recent journal includes draw-pipe drain 48.06 ms and GNM previous
submission retirement 41.28 ms. These are overlapping peaks from a 250 ms
window, not additive durations or proven per-submission attribution.

A separate earlier hitch, submission 590, has 24.54 ms FG-input/frame-slot
retirement and 24.64 ms preparation. It must not be conflated with submission
1866, whose preparation interval is small. Steady samples in the extract include
real means 59.928-59.986 FPS and SDK output 119.938-120.683 FPS; those CPU/window
samples still do not measure display cadence.

## Texture-helper snapshot handoff under review

RunDrawPacket installs the authoritative draw's Shader::Info snapshots in
stage B's thread-local storage. R43 RunTextureTask executes on a different
thread without installing those snapshots. On the unprepared descriptor path,
Info::FlatUserData then falls back to shared Info that stage A may already have
updated for another draw. Both helper eligibility and texture/sampler binding
can therefore consume the wrong draw's descriptors.

The proposed change publishes stage B's snapshot views with TextureTask, installs
them on the helper for the task's duration, and restores previous helper TLS on
all returns. Existing Fork/Join ordering keeps the packet storage alive until
the helper completes. Serial and prepared-resource paths are retained. A causal
CPU regression executes the production publication fragment, RunTextureTask
and Info accessors with later-draw shared descriptors. It also covers early
returns, helper reuse, prepared resources and zero-snapshot operation.

This is a source-level correctness finding. Neither the log nor the synthetic
handoff fixture establishes that this defect causes the cemetery stall, player
halo or foreground geometry flash. Windows compilation and target-game/NVIDIA
validation must be reported separately; do not label this a verified gameplay
fix or prepare a new release based only on this fixture.
