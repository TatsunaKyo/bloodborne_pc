# R49 follow-up: protection work remains on the dependency path

The owner reports unchanged traversal hitching and pacing in R49. The supplied `session(9).json`, `session(9).log` and `Traversal-diagnostic(3).zip` identify commit `82f0ce54634fbad2a3faeedf1befb2cb7272fe72`, tree `b54eb28b114f124dec6fd1b4d1918e6de9f4df01`. All four executable hashes agree with the delivered R49 identity. ZIP CRC and each diagnostic manifest entry pass. The exported archive scrubs paths and selected sensitive records; its performance records agree with the external log. The ordered protection worker is active.

## Observed remaining stalls

Submission 1600, at 34.108 seconds, has a 41.656 ms real interval, 41.31 ms GPU-thread flip interval, 16.46 ms guest submit interval and 28.528 ms submit-to-flip interval. Final present/SDK work is 0.10 ms.

| Stage | Clipped inclusive wall time | Calls |
| --- | ---: | ---: |
| DrawRecord, draw recording | 17.501 ms | 1545 |
| RecordHostCopy, Vulkan recording | 14.822 ms | 1788 |
| Native protection worker | 9.468 ms | 537 |
| Protection dependency, GPU decode | 8.851 ms | 231 |
| Protection dependency, Vulkan recording | 7.851 ms | 184 |
| Command chunk acquisition, draw recording | 5.883 ms | 270 |
| Protection dependency, host-copy thread | 3.533 ms | 28 |

These are nested/concurrent wall times, not additive CPU service times. Buffer uploads touching the window total 197,177,344 whole-operation bytes, and deferred requests total 270,147,584 bytes. Neither is a unique-data or disk-I/O count.

R49 moves protection work off the draw thread, but consumers still wait. The change did not establish a shorter frame critical path. R48/R49 route captures are not deterministic matched replays, so differences in their draw totals are not a measured causal speedup.

There are other stall classes. At 52.272 seconds, a 26.72 ms interval includes GPU finish/timeline waits, new image allocations and host copies, while native protection totals only 0.257 ms. At 58.916 seconds, a 27.29 ms interval includes 8.637 ms of shader/pipeline compilation on GPU decode and only 0.115 ms of native protection. The compile label encloses actual new graphics/compute-pipeline creation or shader-module compilation; the aggregate does not identify which key/module missed or why. Shader-cache deletion is not a justified remedy.

## Reproduced false dependency

`MemoryManager::CopySparseMemory` calls `runtime_memory_wait_page_protection()` before every snapshot. The installed callback seals and waits for the **entire issued queue**, not only watches covering the copied address range. A small snapshot can therefore wait for unrelated later resource preparation which happened before the copy callback began. Fence tickets capture earlier sequences, but that does not make each snapshot's global wait resource-specific.

A local control reuses `tests/test_async_page_watch.py`'s actual C runtime, R49 queue, memory/page trackers and extracted production sparse-copy bodies, with real protected shared-memory mappings. It uploads/protects A, queues a held protection for disjoint B, then snapshots unchanged A. A blocks until B is released, and its contents remain correct. The forced delay tests dependency shape, not gameplay performance. Result:

> REPRODUCED: the actual R49 CopySparseMemory of already-protected range A waits for pending protection of disjoint range B. Releasing B unblocks A with unchanged data.

The next synchronization change must prove that A can finish while unrelated B remains pending, while retaining the existing pre-install-write, post-snapshot-fault, permission-grant, remap, alias and guest-fence coherence controls. Removing the wait wholesale is unsafe. Resource/range dependencies also need explicit lifetime handling when addresses are recycled; replacing a global sequence with an unchecked address cache would not meet that contract.

## Information needed to close the investigation

The current flight recorder exports aggregate spans, not dependency edges or complete chronological events. It cannot show which sequence/range a wait needs, which thread releases it, why each resource became dirty, or whether a long native call was running versus descheduled.

The useful additions are:

- Bounded chronological resource events: request/installation/snapshot/retirement identifiers, address ranges, dirty/invalidation reasons and mapping generations. This distinguishes genuine first uploads or guest writes from repeated invalidation/re-upload.
- A target Windows critical-path recording with CPU samples, context switches/ready-thread events and matching native symbols, correlated with submission IDs and GPU queue/fence activity. [Microsoft's wait-analysis workflow](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/optimizing-performance-and-responsiveness-exercise-3) distinguishes running, ready and waiting states; aggregate wall-time scopes cannot substitute for that.
- Actual presentation/display intervals for pacing, rather than the SDK's current FPS estimate. [PresentMon](https://github.com/GameTechDev/PresentMon/blob/main/README-ConsoleApplication.md) documents present/display timing and Vulkan support; generated-frame classification requires the corresponding application/driver instrumentation and must not be assumed available.

Existing inputs are sufficient to work on the demonstrated cross-resource dependency without requesting another identical diagnostic. A target replay is still needed to establish the actual improvement and any remaining cause. No Windows/NVIDIA replay, displayed-frame validation or image-input capture ran locally. No R50 gameplay fix or graphics-API rewrite is claimed by this analysis. The R49 ZIP/checksum remain unchanged.
