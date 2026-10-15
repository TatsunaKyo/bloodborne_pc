# R43 investigation — work in progress

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

## Outstanding validation

No Windows target-game/NVIDIA execution is available locally. The tests above
reproduce specific defects; they do not establish that the cemetery route,
119–121 output variation, character halo, or every transient asset artifact is
resolved on the owner's system. Do not publish a stronger claim.
