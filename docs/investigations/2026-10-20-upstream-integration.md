# R55 upstream integration and renderer review

R55 integrates Supermedo Windows 1.9.2 into the existing R54 branch. It also adapts specific resource-management and compilation changes from other forks. The integration does not establish that the cemetery traversal hitch, NVIDIA presentation jitter or all reconstruction artifacts have been eliminated on the player's hardware.

## Reviewed sources

| Source | Pinned revision | Integration decision |
| --- | --- | --- |
| [Supermedo Windows](https://github.com/Supermedo/bloodborne_pc/tree/de2e38af055f09f819946951075c6bb119e62ae6) | `de2e38af055f09f819946951075c6bb119e62ae6` | Integrate the changes since the existing 1.9 baseline `652f9a4`; retain fork versioning, updater validation and the existing presentation architecture. |
| [andrecabralgit performance work](https://github.com/andrecabralgit/bloodborne_pc/tree/426a3b0ea4239e5e4a41bed27de827e51802fed2) | `426a3b0ea4239e5e4a41bed27de827e51802fed2` | Adapt per-size motion targets, texture hash retention, demanded-pipeline priority and migration of disabled readbacks. |
| [emurphy04 renderer fixes](https://github.com/emurphy04/bloodborne_pc/tree/c6454fbb99947ed6698550a177f06e42476b513b) | `c6454fbb99947ed6698550a177f06e42476b513b` | Adapt staging/copy sizing from `859f9e4f7fe954c87f1b53b51d8b96e1dada12b9`; preserve GPU-owned image data and keep reserve memory conditional on lack of host fallback. |
| [iannitram FSR memory fix](https://github.com/iannitram/bloodborne_pc/commit/904129c4017d915571970d78f00a1e2c95c77063) | `904129c4017d915571970d78f00a1e2c95c77063` | Carry the protected-memory exclusion as FSR patch 0005, alongside the existing mutex patches and the new upstream allocation-retirement patch. |
| [deadinside28](https://github.com/deadinside28/bloodborne_pc), [visy](https://github.com/visy/bloodborne_pc_windows_port), [bbhost](https://github.com/droogie/bbhost), [LanternEngine](https://github.com/Awakenchan/LanternEngine), [Jgamrot](https://github.com/Jgamrot/bloodborne_pc) | Reviewed architecture and relevant changes | Their different renderer histories and Linux timing approaches are not drop-in replacements for this Windows/Streamline branch. Existing equivalent queue/copy ordering fixes are retained. |

The upstream head was checked during this revision: Windows 1.9.2 remained the current Supermedo Windows branch head.

## Concrete renderer changes

The previous motion-vector implementation held one image. Switching between scene and reflection/pass sizes destroyed and recreated it, calling `Scheduler::Finish()` each time. A four-entry cache retains a target for each size and returns the scene-size target to composition. Each target is cleared once per frame. A fifth distinct size retires queued work before evicting the least recently used image. Existing motion-history matching, camera fallback and read-to-read barrier elision remain in place.

The production-method regression runs both the old and current implementation against the same deferred Vulkan recorder. Across 1,000 frames alternating three sizes, R54 creates 3,000 images and drains 2,999 times; R55 creates three and drains zero times during that alternation. The test also checks current-frame validity, no repeated clear after composition, and safe fifth-size eviction. These counts are resource-lifetime evidence, not a frame-rate benchmark.

The existing bounded pipeline queue now allows a draw to claim its own pending compilation. It does not create a second compiler or drop uncompiled draws. Immutable input snapshots, the 128-job bound, strict wait and synchronous failure fallback remain intact. A blocked FIFO control and 1,000 double-claim races check priority and exactly-once execution; queue shutdown waits for work claimed by another thread.

Texture refresh reuses valid guest-memory mip hashes for GPU-dirty refreshes. CPU invalidation, untracking and downloads invalidate that baseline. A large ordinary texture whose first upload skipped hashing cannot claim a valid baseline when promoted to a GPU-written image. Serial and parallel execution use identical chunked digests; changing worker availability or live debug flags cannot invent a CPU change. Tests use separate guest, GPU-buffer and image byte arrays, including writes to the last byte of a 4-MiB target.

The device-local staging pool keeps 32 MiB and trims after 600 frames, while host upload staging retains its existing policy. Depth/color transfer intermediates use the backing images' actual allocation sizes instead of a fixed 128-MiB request. Sparse arena slabs retain their R54 pooling and semaphore ordering. An emergency VRAM reserve is used only when the device has no compatible host-memory fallback; failed reservation is nonfatal and live slices are never reused.

## Upstream compatibility decisions

Supermedo's new input combinations, three binding slots, mouse/camera handling, device-specific prompts, FOV, background muting, external FPS-patch precedence, THD polling and fault reporting are included. The FSR 3.1 bridge now retires per-frame allocations. Its native FG policy no longer pauses generation because of one isolated hitch.

The following existing behavior is preserved:

| Area | Compatibility requirement |
| --- | --- |
| Startup and timing | R54's fingerprint guard, modern real-frame cap precedence, restart environment and complete packaged patch payload. An incompatible game executable still receives the deliberate guarded fallback. |
| NVIDIA | Original DLSS SR and both existing FG routes; matching SR DLLs in both NGX search paths; stock native FG libraries. RTX Encore remains explicitly opt-in and adapter-gated for RTX 20/30. |
| Presentation | One owner for pacing on each provider route; existing Reflex, total-cap, focus/pause, swapchain retirement and queue-lock rules. No additional limiter copied from another fork. |
| Reconstruction | Existing expanded shader-offset layout and newer cache versions, motion identity/history and scene-resolution policies. No wholesale renderer rollback. |
| Other providers | FSR, XeSS quality modes and AMD Anti-Lag controls. |
| User state | Launcher branding and verified fork update channel, Save Manager, settings, mods and user caches. Other Versions uses the same exact package-name and stable-release validation as the updater. |

Readbacks Off is migrated to Relaxed: disabling required GPU-to-guest transfers can leave FaceGen and streamed geometry stale. Precise remains available. Unreadable GPU-owned tiled image contents are not discarded simply because they are old; guest memory may not contain a recoverable copy.

The experimental draw-skipping and asynchronous guest occlusion-query paths were not enabled. A blanket rollback from the current renderer to 1.8.2 would also undo this branch's memory coherency, temporal and shader-layout repairs. These choices require target-GPU evidence before they can be treated as compatible optimizations.

## Verification and limits

The release includes its actual validation results in `source/verification/summary.json`: Windows cross-compilation, portable production-code tests, compiled Python 3.14 launcher checks, real Tk/ImGui layout checks, packaged synthetic-ELF startup and rejection, DLL hashes and PE dependency closure. GPU entry points in the CPU fixtures are explicit recorders or completed byte transfers. Windows-specific CPU instruction execution and a physical NVIDIA GPU are not simulated by those fixtures.

The final ZIP must be replayed using its own compiled launcher and patch files. Every tracked runtime/startup source is compared with the recorded source commit, including `Bloodborne.xml` and `redzone.json`. The shipped library paths are checked independently of PE imports because NGX loads them dynamically.

No local result is a cemetery-route measurement, a guarantee of fixed 120-Hz presentation or proof that every ghosting/geometry artifact is gone. A reproducible game traversal with and without FG is still the necessary acceptance measurement for those symptoms.
