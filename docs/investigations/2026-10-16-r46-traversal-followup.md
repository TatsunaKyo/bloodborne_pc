# R46 traversal capture: cold page watches and instance identity work

The supplied R46 session and `Traversal-diagnostic.zip` are consistent and the archive passes CRC checks. This is a CPU traversal capture with normal parallel rendering, HDR, DLSS L at 1920×1080 → 3840×2160, a 120 total-FPS target, and no image readbacks. The owner reports the same traversal hitch with FG disabled. FG is not a prerequisite for this investigation.

## Residual hitch

Submission 1066 has a 44.464 ms real interval, a 44.12 ms GPU-thread flip interval and a 32.375 ms submit-to-flip window. Within that window:

| CPU stage | Inclusive time | Calls |
| --- | ---: | ---: |
| DrawRecord, draw-recording thread | 30.917 ms | 1620 |
| Draw resource binding | 10.517 ms | 1641 |
| Guest page protection | 10.178 ms | 788 |
| Vertex-input preparation | 9.462 ms | 1611 |
| Object history and index work | 8.108 ms | 1088 |
| Shader/pipeline work, GPU-decode thread | 3.284 ms | 4 |

These spans are nested or concurrent, not additive. Final present/SDK work takes 0.11 ms, sparse binding 0.135 ms, and preparation 0.243 ms. The previous allocation burst is no longer among the dominant trace categories, but that alone does not prove an exact R45/R46 speedup: the route timing, visible draw count and allocation sizes are not identical replays. The new capture still contains a genuine hitch.

Shader/pipeline work is not literally zero, despite the existing cache. It does not account for the approximately 31 ms of draw-recording work. New geometry also needs host memory tracking, uploads and guide preparation. A separate early present/SDK interval of 42.45 ms and the initial loading intervals are different events from submission 1066.

## First-use page tracking

The old buffer tracker protects CPU-modified ranges when their first upload is requested. On Windows, many small first-use resources enter `VirtualProtect` individually. The R46 hitch contains 788 calls through the guest-page-protection wrapper.

R47 retains the existing VRAM-copy model and its submission ordering. On Windows, when a page is first protected for upload, adjacent **cold** pages within its 64 KiB window may share the protection operation. A cold page has never been uploaded or explicitly invalidated/written since that tracker region was created. Expansion requires the whole window to be GPU mapped and excludes GPU-modified and hot pages.

Protection and upload status are deliberately separate. Neighbours protected in advance remain CPU-dirty and must still be copied when first bound. A new `protected_dirty` mask tracks these pending pages. Their later upload clears the dirty bit without another protection transition. A write releases only pending cold watches in the small group; it does not mark nearby clean meshes dirty. Fault routing checks the pre-invalidation dirty state under the region lock, including a second fault that arrives after another writer already released the group. Genuine writes to clean, uploaded buffers retain the existing fault-window behaviour. Unmapping invalidation removes pending watches through the normal tracker path.

Linux's production tracking path stays at its previous protection granularity. A maintainer can disable the Windows grouping with `BB_BATCH_COLD_WATCH=0`; this is a control for the specific change, not a launcher feature or a proposed gameplay setting. The runtime reports whether this path is enabled.

The regression fixture compiles the actual R46 and current RegionManager, MemoryTracker, page-watcher implementation, BufferCache fault helper and Rasterizer fault-routing bodies. It uses real protected host pages and the runtime's two-view storage arrangement on the Linux test host, with a recording/completion backend for GPU copies. In a sequential controlled case of 788 first-use 4 KiB pages, R46 performs 788 host-protection calls and R47 performs 50. Both upload exactly the 788 requested pages with matching contents. This is not a replay of the owner's actual resource sizes or Windows kernel timings.

The same fixture checks real read/write faults, pending-neighbour writes, concurrent writers, ordinary modified buffers, GPU readbacks, mapping holes, tracker boundaries, unmapping and 10,000 mixed writes/uploads. Address/undefined-behaviour sanitizers cover these paths; leak inspection is disabled because of executor process-inspection restrictions, and the fixture owns its SIGSEGV handler for the intentional page faults.

## Ordered instance identities

The traced object-history block included a serial byte-at-a-time FNV hash over world transforms in instance records. R47 collects the same ordered 3×4 transforms into a bounded 1536-byte snapshot, rejects non-finite values and hashes the packed bytes with the existing XXH3 dependency. The hash now uses the same snapshot whose floats were validated. It still reads the current transforms on every call; there is no address-only reuse or skipped index-content validation.

Actor/weapon pose bindings, index bounds/topology, unknown-batch rejection, camera guides and shader calculations are retained. The old FNV overload is preserved for compatibility and verified to return the old result. Production ring and guest-memory readers use the compact XXH3 path. Tests verify all transform components, ordered/replaced instances, camera-only bytes, invalid matrices and zero-hash normalization, plus the existing production pose-binding/history fixtures.

A controlled local CPU comparison of 40,000 calls with 32 model records measured 103.661 ms for the old path and 22.083 ms for the compact path (4.69×). This is host microbenchmark data, not a measured Bloodborne gain. Extra opt-in trace labels distinguish model-identity work and index hashing in a subsequent capture.

## Validation and limits

Windows cross-compilation, the rebuilt launcher, CPU/page-fault tests, sanitizers and final archive/DLL/source checks are separate from gameplay on NVIDIA. The new build preserves the one-ZIP-plus-SHA256 format, both required SR DLL locations, the original RTX 40/50 path and the opt-in RTX 20/30 provider.

No claim is made that the cemetery route or the 119–121 displayed-output fluctuation is verified resolved. The latter must not be hidden by clamping or smoothing the counter. This intervention targets measured work that delays real frames; actual before/after route timing is still needed. Image artifacts also have not been verified resolved by these host-side changes.
