# R53: Supermedo integration and reproduced renderer defects

The source merges Supermedo/windows at `652f9a494c47cc8c1ab16f28b456372eaa8103f8` (Windows 1.9), retaining this fork's presentation, HDR, XeSS, NVIDIA presets, launcher and explicit RTX 20/30 mod selection. The new native Supermedo generators are separate selectable SDR providers. This is an integration candidate; no target Bloodborne Windows/NVIDIA gameplay was executed here.

## Reproduced defects

* R52 increased `NUM_BUFFERS` to 56 while `DefinePushDataBlock` still described three offset vectors covering 40 bytes. Buffer accesses above that range could address missing vector components or scalar motion data. The SPIR-V validator rejects the actual R52 emitter's all-buffer fixture. R53 derives members and indices from `NUM_BUFFERS`. The exact old layout is upgraded before the shader reaches the driver; binary version 13 accepts/migrates version 12 without discarding translated shader metadata.
* R52 recreated an empty Vulkan driver pipeline cache on each launch. Translated SPIR-V is only one cache layer. R53 also persists the driver's cache, with bounded/checksummed/atomic storage, device/vendor/UUID checks, a write barrier and normal-exit saving. Driver pipeline creation and cache serialization have explicit synchronization.
* Sparse backing allocations had lost `VK_MEMORY_ALLOCATE_DEVICE_ADDRESS_BIT`, although the renderer uses buffer device addresses. The flag is restored. Small allocations retain slab pooling. Under device-memory exhaustion, only host memory types admitted by the buffer's actual `memoryTypeBits` may be tried; this cannot manufacture host backing support on drivers that expose device-local-only sparse memory.
* Cached pipeline loading failed to restore the corresponding shader runtime information. R53 restores it before constructing pipelines, including generated auxiliary stages.
* The integration tests caught audio downmix/output-size conflicts, missing launcher state, an uninitialized input-binding field and cap arbitration errors. Downmix preserves background pause/retained PCM and saturates integer output. Native FIFO and total-output caps are combined; an off or restart-pending provider cannot reduce the game cap through stale active-FG state.

## Integration boundaries

| Area | Result |
|---|---|
| Renderer refresh / memory tracking | R52's coordinated 0.20.1 renderer and issue-time copy fences retained; Supermedo memory-budget image allocation and compatible sparse heap fallback incorporated. |
| Supermedo native FG | Full native FSR 3.1 and direct NGX DLSSG code; owned per-frame outputs, camera matrices, pre-UI capture, adaptive display/FIFO policy and bounded overload pause. New choices: `native_fsr`, `native_dlss`. |
| Original NVIDIA FG / Encore | Existing Streamline path, HDR, presets and explicit RTX 20/30 gate retained. Default ABI1 SR bridge remains. Native DLSS uses the renamed ABI2 bridge only after restart and does not load Streamline's DLSSG plugin. Both feature DLL paths carry the same original NVIDIA DLL. |
| CPU / input / mouse / audio / saves / network | Upstream branch changes integrated, including CPU compatibility, controller/keyboard remapping, direct mouse camera, audio fold-down, atomic save replacement, mod/file handling and network backends. |
| Other forks | IFreemz's push-layout work guided the shader audit. Visy's persistent driver cache and resident preupload informed the port. Runtime compile-ahead snapshots all inputs and waits strictly at use; draw-skipping asynchronous compilation was not adopted because missing geometry is already a reported symptom. |
| Linux host-import memory model | Investigated; its Windows exclusion and different memory ownership model prevent treating it as a drop-in Windows fix. No claim of a completed host-import backend or an API rewrite. |

Compile-ahead uses at most four workers and 128 outstanding jobs, copies shader/user/runtime/fetch data, deduplicates keys, rebinds live stage data on publication, drains workers before teardown and retries a failed speculative job synchronously. Cached graphics pipelines are preloaded in parallel. Resident preupload only considers already-backed, quiet CPU-authored ranges, rejects GPU-authored/aliased ranges and uses the normal ordered copy path. Its budgets are 2 MiB, 256 scanned chunks and a 300 microsecond between-chunk time check; the check cannot preempt an individual driver call. `BB_PIPELINE_COMPILE_AHEAD=0` supports controlled comparisons. Resident preupload is opt-in with `BB_PREUPLOAD=1`; it is not enabled by default before target traversal timings are available.

## Evidence and limits

The actual old/current shader emitter and migration were validated for Vulkan 1.2. Current and migrated modules were also executed on Mesa Lavapipe: all 56 offset accesses plus motion/scene data produce the expected checksum. The production motion shader was executed across separate Vulkan allocations to verify relocation and current-buffer addressing. Driver pipeline-cache data was round-tripped through Vulkan.

Production-code fixtures cover compile snapshots, strict waiting, publication, failures/backpressure/drain, native provider/cap/FIFO/hysteresis decisions, real protected mappings, copy/fence ordering, descriptor reuse, sparse allocation/rebinding, cache I/O, and SR initialization with ABI1 and ABI2 with FG unavailable. ASan/UBSan checks ran with leak scanning disabled because this execution environment cannot enumerate sanitizer threads. The compiled launcher was exercised with real Tk widgets and the ImGui controls/layout fixture was regenerated. These tests do not execute NVIDIA's hardware FG implementation or measure the cemetery route.

The provided R52 log places large hitches before presentation, including shader compilation, draw-pipe drain, previous-submission retirement and arena migration. Those nested/overlapping spans must not be added together. The evidence does not justify attributing the FG-off cemetery hitch entirely to FG, shader compilation, or a corrupted local shader cache. R53 repairs reproducible faults and integrates alternative upstream providers; it does not certify that cemetery traversal, 119–121 output variation, stairs halos or transient geometry have disappeared.

## Pinned sources

* [Supermedo Windows 1.9 source](https://github.com/Supermedo/bloodborne_pc/commit/652f9a494c47cc8c1ab16f28b456372eaa8103f8)
* [Supermedo Windows 1.9 release](https://github.com/Supermedo/bloodborne_pc/releases/tag/windows-v1.9)
* [IFreemz push constant work](https://github.com/IFreemz/shadPS4-Bloodborne-DLSS-FSR/commit/20b345737e7e64419f072a87fb53934e5bb0b26e)
* [Visy driver pipeline cache](https://github.com/visy/bloodborne_pc/commit/63e8f514d18e9a0f946c49a12448cfbe23b5f6c1)

The runtime lock records both bridge identities and the original DLSSG file hash. Git is canonical; the release includes one source patch against the recorded upstream base and compact recovery data inside the playable ZIP.
