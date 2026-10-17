# R48 capture: rebuild write-watch installation and its dependencies

The supplied `session(8).json`, `session(8).log` and `Traversal-diagnostic(2).zip` identify revision 1.6-tatsunakyo.48. The archive passes CRC validation and its build identity matches R48. The owner still observes the cemetery hitch and irregular pacing. R48 is not considered a successful gameplay fix.

## What the new capture establishes

At 26.001 seconds, submission 1040 has a **40.02 ms** real interval, a 39.68 ms GPU-thread flip interval and a 17.15 ms guest submission interval. Submit-to-flip is 26.35 ms, preparation 0.27 ms and present/SDK work 0.12 ms.

| CPU stage | Inclusive clipped time | Calls | Whole-operation bytes touching the window |
| --- | ---: | ---: | ---: |
| DrawRecord, draw-recording thread | 25.033 ms | 1622 | — |
| Draw resource binding | 10.899 ms | 1646 | — |
| Guest page protection | 8.401 ms | 704 | — |
| Read-only write-watch installation | 8.337 ms | 704 | 280,264,704 |
| Vertex input preparation | 8.114 ms | 1615 | — |
| RecordHostCopy, separate recording thread | 6.924 ms | 1764 | — |
| Sparse/VMA copy preparation | 6.433 ms | 1560 | — |
| Buffer upload batches | 5.852 ms | 284 | 201,404,416 |
| Shader/pipeline work, decode thread | 3.942 ms | 4 | — |
| Object history/index work | 2.981 ms | 1081 | — |
| R48 eligible upload-window queries | 0.083 ms | 302 | 19,791,872 |

These stages overlap or nest and must not be added. Byte totals describe whole operations touching the interval, not unique bytes, disk reads or a precise time-weighted bandwidth. The bounded trace reports one cumulative lost record and no collision at this flip; it is not a complete instruction trace.

The R48 upload policy is active, but most reported traffic is larger than its small resident-block read-ahead window. This is evidence against treating another small-page grouping adjustment as a sufficient solution. Map logs appear at startup, not at this event: streaming can reuse existing mapped heaps. The capture does not establish a host remap or disk read as the cause. Nor does its small final present time implicate FG as the cause of this particular hitch.

The final cadence window has mean 59.568 real FPS, median 16.637 ms, p95 17.475 ms, p99 21.836 ms and maximum 40.020 ms; SDK output is 120.116 FPS. This does not measure the spacing of individual displayed/generated frames. An earlier 57.62 ms event includes about 40.45 ms of present/SDK work and remains a separate startup event.

## R49 protocol

R49 replaces synchronous Windows read-only write-watch installation in eligible resource preparation with one ordered, bounded worker. The queue holds at most 2048 pending segments. It processes up to 64 already-ready requests at a time, with no artificial delay to fill a batch. Within one committed Windows mapping view and native permission mode, overlapping or adjacent segments can share an actual `VirtualProtect` call. Holes, separate views and read-only versus execute-read segments stay separate. Dependency capture seals the queue boundary, so later requests cannot be merged into an earlier fence's batch.

This changes where the syscall runs and can reduce syscall count; it does not eliminate protection work or copying. If the worker cannot keep up, snapshots and retirement still wait. The expected benefit is overlap with draw preparation and fewer repeated native calls, which requires gameplay measurement to quantify.

The correctness contract is explicit:

- A new write watch is recorded before queuing its permission revocation. A guest store before the OS protection becomes active is included in the later snapshot.
- Host upload snapshots wait for installation. Hash shortcuts that can avoid an upload wait as well. Stores after installation retain the existing fault/invalidation path.
- Image watches defer only for CPU-dirty, single-sample images which must obtain a fresh snapshot. Already-current images and multisampled images retain synchronous installation.
- Permission grants, no-access/readback tracking and mapping changes drain preceding revocations before changing permissions or the underlying host view. No queued protection may land on a reused address after that drain.
- Guest-visible host-copy fences capture their own installation ticket. Their completion waits for that ticket and existing copy retirement, without waiting for future frames' requests. `WaitHostCopies` also waits when there are no outstanding copies.
- The raw worker callback uses captured address/size/native protection only. It never acquires VMA, tracker, GPU or queue locks during `VirtualProtect`, so a mapping thread can drain it while holding the VMA writer lock.

Windows request clipping happens under the existing VMA reader lock and captures the committed mapping-view identity. This is necessary because `VirtualProtect` requires committed pages within a compatible reserved allocation/mapped view; merging by virtual address alone is unsafe. See [Microsoft's API contract](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-virtualprotect).

The service is installed before GPU mapping hooks are replayed. Linux production retains synchronous protection. `BB_ASYNC_PAGE_WATCH=0` is a maintainer's synchronous control, not an additional launcher option. The startup log identifies whether the worker is active. Optional hitch tracing distinguishes queued read-only requests, actual native protection calls and dependency waits.

## Verification

`tests/test_async_page_watch.py` compiles the actual C runtime, C++ queue, page/memory trackers and sparse snapshot bodies. Real protected shared-memory aliases exercise stores before installation, snapshot blocking, post-snapshot write faults, synchronous grants/remaps under the VMA writer lock, precise readback and 2000 write/upload cycles. Both asynchronous and synchronous controls pass. A separate 6000-job/eight-waiter stress checks wakeups; a capacity-two queue checks backpressure and captured sequence retirement.

`tests/test_page_watch_contract.py` compiles actual Windows dispatcher bodies with a recording WinAPI boundary and actual Scheduler fence/drain bodies with a recording completion backend. It verifies view clipping, placeholder exclusion, native RO/RX capture, synchronous grant/no-access paths and future-request exclusion. A real native `mprotect` fixture reduces 64 ready contiguous same-view requests to one call while checking data and all separation rules. These are operation/ordering controls, not a Windows game benchmark.

Both new fixtures pass normal and ASan/UBSan runs. Leak inspection is disabled in this host environment; intentional page faults in the shared-memory fixture use its own signal handler. Existing upload/first-use/VMA guards, host-copy ordering, queue-lock scope, trace and NVIDIA pacing policy controls pass. The Windows runtime and Python 3.14 launcher are rebuilt, six real-Tk launcher checks pass, and 1960 overlay layouts pass. Package validation checks source identity, executable/dependency hashes, PE closure, matching SR search paths, original NVIDIA runtime pin, CRC and SHA256.

## Encore report is a different compatibility problem

The community report is from an R40 installation using RTX Encore, not the owner's native RTX 5070 Ti R48 capture. Its FG provider is initialized with 177305 runs, but NR is requested with active engine `none`. The current reason is rejected Vulkan depth capture, format 130 (`D32_SFLOAT_S8_UINT`). The supplied JSONC already enables NR and selects the NVIDIA engine, so this is not an obvious missing enable switch. An enabled Open-only option is irrelevant while the NVIDIA engine is selected.

The port already creates cached images with `MUTABLE_FORMAT | EXTENDED_USAGE`, plus applicable flags; adding `MUTABLE_FORMAT` globally is not a diagnosis. Encore's message also permits other flags or a different view format as the rejection reason. A compatible capture/depth resource or an Encore-side adjustment needs investigation; R49 does not implement or claim NR compatibility. A depth-capture failure does not validate the NR DLL version/hash or establish that later model initialization would succeed. The requested FG preset B and overridden configuration read do not verify which model actually ran.

NR and FG are separate features. Keep NR disabled while using the working FG path; do not prescribe further DLL swapping as a remedy for this depth-capture error. Encore's [NR documentation](https://github.com/SilyNoMeta/rtx-encore/blob/main/docs/NEURAL-RENDERING.md) describes its experimental status, input requirements and version qualification. Format numbering is defined by [Vulkan](https://docs.vulkan.org/refpages/latest/refpages/source/VkFormat.html).

## Remaining limits

No Windows/NVIDIA Bloodborne session, cemetery replay, displayed FG timestamps or new image readbacks ran locally. R49 does not change motion shaders/history, the cap, FPS counters, NVIDIA feature libraries, or the native RTX 40/50 and opt-in RTX 20/30 selection. It therefore does not claim the cemetery route, 119–121 fluctuations, stairs halo or transient assets are resolved. A switch to another graphics API would still need correct resource preparation and retirement; the measured CPU path supports reconstructing that subsystem first, not promising an unmeasured full API rewrite.

One complete R49 ZIP and its checksum contain runtime, required dependencies/licenses, source changes, verification and compact recovery. No extra developer package is needed.
