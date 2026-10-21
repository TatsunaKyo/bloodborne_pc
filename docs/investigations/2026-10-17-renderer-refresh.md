# R52 renderer refresh after the failed R51 replay

The owner reports no improvement with R51. No R51 gameplay capture accompanied that report. The last measured target session remains R50: submission 936, 34.38 ms real interval, 21.33 ms submission-to-flip, 19.53 ms of overlapping draw-record spans, about 196 MiB in buffer-upload operations, and 0.11 ms in final presentation/SDK state. These observations establish a preparation/streaming investigation independent of FG. They do not identify every upload as redundant or prove which resource causes the cemetery hitch.

## Source comparison and decision

Compared these pinned sources against the shipped R51 commit `d7062615e1cd1ee68e591ca7e36956619de1f975`:

- [Supermedo 1.9](https://github.com/Supermedo/bloodborne_pc/commit/652f9a494c47cc8c1ab16f28b456372eaa8103f8), specifically its coherent [shadPS4 0.20.1 update](https://github.com/Supermedo/bloodborne_pc/commit/087bbf3ac40c9fca60ef14db081de52bad70923d). This updates memory tracking, buffer access/barrier bookkeeping, sparse backing, index-buffer capacity/null handling, image downloads, metadata and the matching shader compiler. Its upstream renderer is `5aa7ffa3`; Sirit is `fc2b42d`.
- [deadinside28/bloodborne_pc 0.51](https://github.com/deadinside28/bloodborne_pc/commit/3c57da41): texture retention in seconds, the stairs camera fix, and the newer game-memory module. In particular [0.5-pre4](https://github.com/deadinside28/bloodborne_pc/commit/10baf9df25f106da9013433a2e7348839baf917a) identifies 30–70 ms stalls from rewriting mirror page tables under the runtime memory lock. That module does not exist in our Windows renderer, so its particular page-table fix cannot simply fix this build.
- [IFreemz exp-2.1](https://github.com/IFreemz/shadPS4-Bloodborne-DLSS-FSR/commit/b7528b286c6c89bda150400eeb6788caca97c2a5): threaded recording, pacing, character motion and buffer residency work. Its implementation is an emulator fork with different runtime/fence ownership. Its release notes also distinguish texture reclamation from sparse buffer eviction and their validation status. Its performance claims are not measurements of our port.

R52 integrates the renderer update as a coupled subsystem, preserving this fork's settings, Streamline/Reflex/native NVIDIA path, optional RTX 20/30 mod gate, temporal history protections, worker snapshots, pooled sparse backing and issue-time copy/fence dependencies. It does not merge unrelated launcher/network changes from Supermedo or replace the NVIDIA libraries.

The old speculative cold-watch grouping and resident-neighbour upload prefetch policies are retired with the old tracker. They failed the target replay and depend on a different tracker contract. The direct-draw bounds introduced in R51 remain, adapted to the new fetch and index APIs. Large, unsafe, GPU-written, indirect and unsupported index paths retain their conservative fallback. A null base or count above the declared index capacity cannot enter the direct snapshot shortcut.

## Reproduced structural defects

`tests/test_renderer_cache_refresh.py` builds the actual R51 and current slot storage and LRU implementations, and executes each version's actual texture collector with controlled age/usage inputs.

1. Growing slot storage to 9000 resource objects moves 8192 existing addresses and calls 14336 move constructors in R51. Current storage reserves its address range and commits chunks: zero existing addresses or objects move. Slot erasure/reuse and destruction are checked. This removes dangling references during cache growth; it is not evidence identifying a particular transient asset in gameplay.
2. R51 tests `std::invoke_result<...>` rather than `std::invoke_result_t<...>` against `bool`. A callback requesting termination after its first item is therefore called 10000 times in the actual old LRU control. The current implementation stops after one. The refreshed collector also limits its own visits.
3. At a controlled 600 submissions/s, 12 textures last seen 20 submissions (33 ms) earlier lose ten entries in R51 despite being below the pressure threshold. Current retention loses zero; the same resources are reclaimed after the idle threshold. Under pressure, three-second-old resources remain and six-second-old resources are reclaimed. Critical-budget emergency reclamation is retained. The new collector reserves zero for unpopulated age-history slots and starts live resource ticks at one; the startup control verifies that first-submission resources are retained too. This demonstrates the eviction/re-upload mechanism, not a measured eviction count in the owner's cemetery run.

The new tracker uses range-bounded bitmap words and summaries rather than whole-manager protection-state reconstruction. `test_renderer_memory_refresh.py` executes the actual region manager, memory tracker, page-state accounting and fault dispatch on two views of a shared, genuinely protected mapping. It checks 10000 writes per readback mode (disabled, relaxed, precise), clean-upload skips, word/16-MiB region boundaries, GPU-authored neighbour isolation and overlapping watch ownership.

The Windows protection service is retained. `test_async_page_watch.py` now uses the refreshed production trackers with the real C runtime and ordered worker. It tests stores before watch installation, required snapshot waits, unrelated/aliased ranges, grants and remaps under the VMA writer lock, precise readbacks, 2000 write/upload cycles and bounded queue retirement. The existing page-watch contract tests verify native view boundaries and issue-time fence prefixes.

## Integration fixes and preserved data

Precise readbacks revoke CPU reads of GPU-owned pages. R52 completes a writable binding's staging snapshot before publishing that ownership, holding the relevant tracker locks across the transition. Only this precise writable path requires a synchronous snapshot; ordinary read-only and relaxed uploads retain their asynchronous path. The actual `SynchronizeMemory`/`ObtainVertexBuffer` control checks this ordering and byte equality. A 4-MiB descriptor with a proven 6000-byte footprint uploads 8192 bytes, preserves the original binding offset, leaves unused pages dirty/unresident, uploads later demand and preserves GPU-owned bytes. This is a byte-volume test, not an FPS result.

Generated fragment shaders in graphics-pipeline support data were omitted from serialization. The actual R51 writer/reader control loses them; the current writer/reader preserves them. Shader/meta/pipeline versions are now 12/9/7, past R51 and the adopted upstream history. Existing incompatible records rebuild once. The fetch-record serializer, stale vertex descriptor rejection, portable motion SPIR-V, warm-up rejection/recovery and CPU DMA snapshot ordering have separate production-source controls.

## Camera, FG and the alternate memory architecture

The Linux stairs fix changes a vertical projection convention. Our R44 decoder already derives the screen projection sign from the actual viewport and its independent viewport-reference test covers both signs. Copying only the Linux shader sign change into that convention would be inconsistent. R52 preserves that camera decoder, motion rejection and history ownership. It does not claim the stairs halo is fixed.

The newer Linux memory module is a substantial alternative: host imports or dma-buf chunks, separate VRAM mirrors, game allocation/loader hooks, GPU command copies and different fence handling. Its source uses `memfd`, `mmap`, Linux fault contexts and driver self-tests. Its NVIDIA notes explicitly reject the old sparse-import variant after very long sparse binding stalls and discuss unvalidated hardware paths. It is not a DLL swap or a safe direct Windows cherry-pick. R52 therefore adopts the coherent Windows renderer refresh first; it does not enable untested host imports on users' machines or claim a Direct3D rewrite would remove CPU preparation stalls.

The current NVIDIA pacing controls still pass for x2/x3/x4/x6, arbitrary ceilings, focus changes, errors and cap ownership. Neither an SDK estimate near 120 FPS nor a rounded counter proves equal spacing of displayed frames. R52 does not force that estimate to 120 or claim the 119–121 report is resolved.

## Verification boundary

Windows cross-compilation, compiled launcher UI checks, production-source CPU controls, ASan/UBSan checks and SPIR-V validation are recorded with the package. No target Windows/NVIDIA Bloodborne session, cemetery replay, displayed-frame timestamp capture or new gameplay image comparison ran here. This is a structural renderer rebuild with reproduced defects corrected; it is not a verified final fix for the owner's three visible symptoms. Keep the investigation PR in draft until target validation.
