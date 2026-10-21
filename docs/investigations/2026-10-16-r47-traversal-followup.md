# R47 traversal capture: batch actual resident buffer uploads

The supplied `session(7).json`, `session(7).log` and `Traversal-diagnostic(1).zip` identify revision 1.6-tatsunakyo.47 and agree with the archive's build identity. The archive passes CRC validation. The owner reports no perceptible resolution. R47 is not considered a successful gameplay fix.

## Evidence

Submission 1152, at 28.009 seconds in the supplied log, has a **39.04 ms** real interval and a 38.70 ms GPU-thread flip interval. The guest submission interval is 17.07 ms; submit-to-flip is 25.30 ms. Preparation is 0.258 ms and present/SDK work is 0.10 ms.

| CPU stage | Inclusive clipped time | Calls |
| --- | ---: | ---: |
| DrawRecord, draw-recording thread | 24.032 ms | 1515 |
| Draw resource binding | 10.005 ms | 1535 |
| Vertex input preparation | 8.441 ms | 1502 |
| Guest page protection | 8.336 ms | 708 |
| RecordHostCopy, separate Vulkan-recording thread | 6.534 ms | 1785 |
| Shader/pipeline work, GPU-decode thread | 3.484 ms | 4 |
| Object history and index work | 2.927 ms | 1070 |
| Sparse backing allocation | 1.945 ms | 15 |

These are nested/concurrent spans, not quantities to add. The draw-pipe drain (15.701 ms inclusive) waits for production work. It is not proof of a slow final present, disk read or shader-cache failure. The 120 FPS output counter does not demonstrate correct individual displayed-frame spacing.

The final 512-frame window reports mean 59.592 real FPS, median 16.671 ms, p95 17.411 ms, p99 18.845 ms, maximum 39.844 ms and SDK output 119.861 FPS. Startup also contains a different 57.55 ms interval with 40.61 ms in present/SDK work, plus longer loading intervals. None is silently reclassified as fixed or excluded from the report.

R46/R47 captures are not identical deterministic route replays. Lower object-history cost or a lower single hitch cannot establish the actual before/after gain. The new log does establish that page protection and draw preparation remain substantial costs after R47.

## Why R47 was insufficient

R47 groups write watches only on pages classified as cold. Its original control started with populated memory and tested sequential first use. It did not exercise the normal invalidation notification before populating a tracked region. That notification cleared the cold classification even on pending pages which had never been watched or uploaded. An added regression reproduces this failure in the shipped R47 source; the corrected classification retains eligibility for untouched pending pages and still removes it from existing watched writers.

More broadly, a page can cease to be cold simply because an old asset once occupied that address. Streaming can recycle an existing mapped heap. Improving *first-ever* watch installation does not batch the actual uploads for that reuse. The supplied trace does not contain individual resource addresses or sizes, so it cannot prove what fraction of its 708 calls belongs to either case. This limitation is explicit.

## R48 change

For a read-only, non-texel buffer binding that already needs a CPU-to-GPU upload, R48 may include adjacent CPU-dirty pages within the same **already-resident sparse block**, capped at 64 KiB. The original binding's sparse residency has already been established by `EnsureResident`; the change requests no extra backing allocation. The extra pages join the existing staging snapshot and GPU copy. They become clean only as part of an actual upload, rather than merely sharing a speculative watch.

The mask excludes GPU-modified and hot neighbours. Expansion requires the whole small window to be GPU mapped and readable under the runtime's guest VMA permissions, including GPU-readable guest mappings. A new generation-validated VMA query rejects inaccessible padding, reservations, holes, overflow, flexible allocations and physical guest aliases. An alias could bypass another virtual address's watch, so a VMA sharing any physical storage is conservatively excluded. It checks underlying permissions, not the temporary GPU-tracking OS protection. A wholly requested window does not need an additional expansion query.

The policy handles previously uploaded and overwritten addresses as well as first use. Subsequent guest writes still invalidate prefetched pages through the existing write-fault path. Writable/storage bindings and texel buffers retain their previous upload extents. Precise readbacks, host-copy retirement, sparse-bind ordering and GPU barriers remain in their existing paths. The expansion backend is Windows-specific; Linux retains its prior upload extents.

The tradeoff is bounded read-ahead: unused CPU-dirty neighbours can be copied earlier than needed. That can increase upload traffic when allocations are sparse, although it cannot allocate additional resident blocks. This is not a universal promise that batching always wins. A maintainer control, `BB_PREFETCH_BUFFER_UPLOADS=0`, restores the unbatched extent policy for comparison; it is not a new player-facing setting.

## Checks

The new fixture compiles actual R47/current `SynchronizeMemory`, RegionManager, MemoryTracker and page-watcher/fault-routing bodies. The host uses real `mprotect`/SIGSEGV, two aliases of a shared mapping and a recording/completion backend for staging snapshots and GPU copies. Writable GPU inputs are snapshotted synchronously in that backend before precise read watches; read-only snapshots and GPU copies can be deferred until simulated retirement. It is not a Windows Vulkan driver or a replay of Bloodborne assets.

A controlled reuse case first uploads an existing region, invalidates and rewrites it, then binds 156 adjacent 20 KiB geometry ranges. R47 performs **156 protection operations, 156 staging batches and 156 copy commands**. R48 performs **49 of each**, with the same 3,194,880 uploaded bytes and all requested contents checked. The fixture also checks 1,000 reuse cycles, writes after prefetch, mapping holes, guest-inaccessible padding, GPU-written neighbours and readbacks, 16/64 KiB sparse blocks, tracker boundaries, and exclusion of writable/texel requests. This is a controlled operation-count comparison, not a measured game FPS improvement.

The expanded first-use fixture also checks a streaming invalidation before 788 first-use pages. The shipped R47 fails the 50-call assertion; the corrected path uses 50 protections and uploads all 788 requested pages. The former R46 control uses 788 protections. The existing concurrent-writer and 10,000 mixed write/upload cases are retained.

Both protected-page fixtures pass address/undefined-behaviour sanitizers on the host, with leak inspection disabled and intentional faults owned by the fixture's signal handler. The actual C runtime VMA guard is separately executed with normal and sanitized builds, including cache invalidation on alias creation/removal. Trace resource totals, clipped spans, thread separation, bounded concurrent ring wrap and command handoff are checked as well.

## Diagnostic precision and unresolved items

The optional CPU trace now records upload-batch bytes and separates page-watch changes into read-only, writable and no-access categories. It reports counts, bytes and start-address ranges for operations touching each hitch window. Whole-operation bytes are not time-weighted or claimed to be unique bytes. The ring is bounded and records no memory contents. This supplies the resource information absent from the R47 capture without requiring an extra tool or image readbacks.

The launcher/runtime are rebuilt together and delivered as one full ZIP plus SHA256. Final package checks include source identity, dependency closure, original NVIDIA runtime hashes and both required matching DLSS SR search paths. The original RTX 40/50 path and opt-in RTX 20/30 provider are preserved.

Cemetery traversal, displayed FG intervals and image artifacts have **not** been verified resolved on Windows/NVIDIA. The new attachment contains no image readbacks. No shader, image-history matching, DLSS preset, cap or displayed FPS value is changed by this intervention. A different rendering API would still need the resource preparation shown in this trace; this evidence does not justify representing an API rewrite as an established solution.

Primary reference for the Windows memory constraints: [Microsoft VirtualProtect documentation](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-virtualprotect). Broader upstream memory-model differences remain documented in `2026-10-16-frame-pipeline.md`; the Linux host-import model is not treated as a drop-in Windows fix.
