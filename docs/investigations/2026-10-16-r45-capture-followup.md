# R45 capture: traversal allocation burst and missing archive

The owner's new session is explicitly revision `1.6-tatsunakyo.45`. The native NVIDIA path is in use on an RTX 5070 Ti; the optional legacy-card provider is off. CPU flight recording is enabled, GPU timestamp profiling is off, and the normal parallel renderer is running. The owner also reports the same traversal spike with FG disabled. FG is therefore not a prerequisite for investigating this traversal defect.

## What the trace identifies

| Submission | Real interval | Submit to GPU flip | DrawRecord, inclusive | vkAllocateMemory inside that work | Final present + SDK state |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1107 | 35.22 ms | 24.89 ms | 23.882 ms / 1193 calls | 10.254 ms / 97 calls | 0.12 ms |
| 1416 | 65.32 ms | 52.09 ms | 50.781 ms / 1527 calls | 24.393 ms / 261 calls | 0.19 ms |

The second trace contains 27.605 ms of vertex-input preparation, 9.405 ms of resource binding, 8.360 ms of object-history/index work, and 6.706 ms of guest page protection on the draw-recording thread. These spans are nested and overlap; adding them would be incorrect. The GPU-decode thread is waiting for that thread at `ProcessCeUpdate`, and the guest's previous-submission wait overlaps the same delay. The sparse queue bind at the end is only 0.181 ms. The allocation burst is actual work on the producer, rather than a wait whose cause is unknown.

A separate early interval, submission 399, spends 38.98 ms in present/SDK state. That is a different path and is not evidence that the later traversal spike is caused by FG. Small steady FPS fluctuations and the visible halo/foreground artifact also remain separate unresolved measurements.

All these numbers are CPU elapsed spans from an instrumented run, not GPU execution durations. The trace adds overhead. The logs contain no F8-request or completed image-readback lines, and metadata says `frame_capture.status=no_frames`; there is no captured image sequence to attribute the halo to SR, FG, or guest geometry.

## R46 intervention

The old `EnsureResident` called `vkAllocateMemory` once for every request that discovered a new sparse backing range. R46 uses a physical sparse-memory pool. Small requests suballocate aligned, disjoint slices from slabs up to 16 MiB; the size is capped further on small heaps and by the driver's allocation-size limit. Best-fit remaining tails can be reused. Requests at least one quarter of the slab size use exact-size allocations when no existing tail fits. If optional slab growth fails with an out-of-memory result, an exact-size allocation is tried before reporting the original failure.

Only missing guest ranges are bound and uploaded. This does not pre-map extra guest addresses, replace live backing, evict memory, change guest data, alter semaphores/queue ownership, or wait for a new background allocator. Physical allocations survive every arena migration and are freed after the arena buffers. Backing offsets in the interval map now consistently use sparse-block units; actual Vulkan bind offsets remain bytes. This preserves interval splitting/coalescing and rebinding when a pooled slice has a nonzero offset.

The regression fixture executes the actual R45 and R46 `EnsureResident` and `GetArena` bodies against a recording Vulkan allocation backend. A controlled case of 261 new 64 KiB bindings needs 261 driver allocations in R45 and two in R46. This is a control for the code change, **not a replay of the owner's exact allocation sizes or a measured improvement in Bloodborne**. Tests additionally cover sparse alignments, holes, resident reuse, non-overlapping physical ranges, coalescing, arena migration, large allocations, small heaps, allocation failures and teardown; address/undefined-behavior sanitizer execution is separate.

The new data justifies removing this allocation burst from the critical path. It does not prove that the whole 65 ms hitch, the recurring route after residency has warmed, the output cadence, or the image defects are resolved. Exact per-allocation byte sizes were not present in R45, and the remaining work in DrawRecord is substantial.

## Archive correction and FG-independent capture

The exporter returned `no_frames` before packaging anything when there were no image readbacks. Consequently even a successful CPU trace produced no ZIP. R46 always packages the sanitized current-session CPU log, settings, system/build identity and integrity record after an explicitly requested diagnostic run. An archive without images is marked `logs_only` and its image state is stated separately; it is never presented as a successful image capture. Failed exports retain the previous archive atomically.

`Capture-Traversal.cmd` runs the current settings with `--traversal-diagnostic`: FG can be off, FSR or NVIDIA; no F8 press or image readback is required. It enables the bounded CPU trace, keeps GPU timestamp profiling off, preserves parallel renderer settings and saves `Traversal-diagnostic.zip`. `Capture-NVIDIA-FG.cmd` remains available for the optional tagged-image investigation and now also exports a logs-only archive if F8/readbacks were absent. F8 image readbacks can disturb subsequent timing; reproduce the clean traversal before requesting images.

## RTX Encore community report

The supplied screenshot shows a different user's R40 installation, `Neural Rendering stopped`, a `310.8.0 SHA256 mismatch`, FG `Waiting`, and the game at its title screen. It is not a confirmation of working frame generation in a rendered gameplay scene.

Encore's [Neural Rendering documentation](https://github.com/SilyNoMeta/rtx-encore/blob/main/docs/NEURAL-RENDERING.md) distinguishes NR, SR and FG. `nvngx_dlssnr.dll` is for its optional Neural Rendering stage. It requires the qualified NVIDIA 310.8.0 build and rejects other versions. A matching version label alone cannot establish matching bytes. The image's rejection therefore explains an NR initialization refusal; it does not diagnose a separately reported crash with a different DLL. Vulkan FG on RTX 20/30 remains [experimental in Encore's compatibility matrix](https://github.com/SilyNoMeta/rtx-encore/blob/main/docs/COMPATIBILITY.md).

For FG-only validation, leave NR off, restart, enter gameplay, and obtain Encore's System → Copy report and the relevant `rtx-encore-logs` crash/NR log if NR itself is being tested. Shimmering at x2 does not identify preset C as the cause without a comparison at identical settings. Do not bypass the checksum check or supply an arbitrary NR DLL as a fix.

The port's integration continues to download only the pinned opt-in FG provider for a verified real RTX 20/30, into its private directory before Streamline starts. It installs no root proxy and no NR DLL; new Encore settings explicitly keep NR off. Existing user preferences are preserved. The original NVIDIA path on RTX 40/50 and both required SR DLL search locations remain intact. Encore's source is not public, so an internal NR crash cannot be claimed fixed by this port change. Updating its provider version is a separate compatibility decision, not part of the allocator correction.
