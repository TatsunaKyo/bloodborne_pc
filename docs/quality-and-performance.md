# Temporal stability and renderer performance

I focused on stopping stale history from carrying across unrelated scenes and removing repeated work from the renderer. The current build also includes the foliage-history and preserved-depth corrections that resolved the Hunter's Dream flashing in my Windows 11 / RTX 5070 Ti test. The underlying bbport/shadPS4 renderer and vendor integrations retain their credits.

## Shared camera reset

I check the captured main camera once per frame. A move of at least 10 world units, a rotation over 100 degrees in one frame or an abrupt projection change requests a history reset. I keep history during ordinary movement, gradual zoom and rotations across the ±π boundary. Missing cameras, invalid matrices and render/provider changes invalidate it; the first valid camera seeds both views again.

On that frame, reconstruction receives the same reset in native and scaled paths. Previous camera and jitter are seeded from the current sample, and old object vectors are ignored. Discarding previous object tables preserves this frame's GPU allocation cursor, so a late camera capture cannot overwrite positions already reserved by a draw. DLSS and XeSS feature recreation also forwards the reset to the already captured FG inputs. FSR, TAA, XeSS, DLSS and FG therefore agree on the transition.

I made this change so a teleport or loading transition starts from the new scene. It addresses stale history; other causes of DLSS shimmering still need work. NVIDIA's [integration checklist](https://developer.nvidia.com/rtx/streamline/get-started) identifies accurate motion, compatible jitter, mip bias and resets as part of the input contract.

## Avoidable work removed

- After the main camera has been captured, later G-buffer bindings skip the redundant guest-memory mapping lookup and signature inspection.
- The scene mip bias retains `log2(render/output)` but caches the value until either dimension changes, avoiding the logarithm on every sampler request.
- Upscaler activity uses one provider snapshot instead of repeatedly loading the atomic setting for each comparison.
- An object-motion image already in General layout can be read again without another read-to-read barrier. Color-attachment writes still transition and synchronize before a reader.
- Index bounds remain cached, but Revision 13 checks the index contents on each draw before using them. Changed contents immediately invalidate the cached topology, including changes that leave the bounds unchanged. GPU-written indices are excluded from CPU-derived history.
- Revision 4's cached upscaled-display image view is retained, as is the one-frame default GPU queue.

Revision 10 spread periodic scans across frames. After the flashing-assets report, I revisited that shortcut: memory can be reused between checks, and bounded history access alone does not make the old contents valid. Revision 13 keeps a full content hash on each draw and reuses the range scan only when it matches. In the 4,096-mesh fixture, unchanged meshes keep their bounds and 16 changed allocations are rejected immediately. I can't guarantee an FPS increase on different configurations yet, so I would welcome tests from other users, especially in places where frame delivery is uneven.

## Camera snapshots and invalid vectors

The draw pipeline copies read-only constants before the recording thread binds them. I now decode the camera and compare small-skeleton palettes from those same snapshots. Reading the live guest address later could give motion tracking a newer camera than the one used to render the image.

A point behind the previous camera has no valid reprojection. I reject that case and vectors that would overflow the FP16 motion texture before they enter reconstruction or FG. The GPU fixture covers behind-camera points, stale/nonfinite object vectors and excessive camera/object vectors. My Revision 19 Hunter's Dream comparison now suggests the flashing is resolved; I keep its corrections while checking the remaining pacing inconsistency.

## Remaining quality work

Next, I want to check motion coverage for particles, transparent surfaces, weapons and newly visible geometry against the color/depth buffers. The existing opaque/skinned-mesh path must keep exact draw identity and full-precision depth rejection. Reducing that precision just to save bandwidth can introduce incorrect distant motion.

I also want to improve text during FG by separating the HUD from the scene, with real HUDless color and matching UI-alpha buffers. Further DLSS improvements may require moving scaled reconstruction earlier in post-processing: native AA uses HDR scene color, while scaled presets currently reconstruct the tonemapped scene. I need to coordinate that with post-processing and SDR/HDR handling.

The current mip bias already restores fine texture detail. More negative bias or stronger sharpening can increase shimmer, so those are tuning choices to compare on a moving scene. The optional profiler helps quantify future changes; it is not a prerequisite for removing redundant work that is identifiable in the code.

For the main gameplay configuration and open regression checks, see [Testing](testing.md) and [current reports](known-issues.md).

## ConstRam and geometry reads

Draining the draw queue before `DumpConstRam` did not complete deferred vertex/index copies. The dump could overwrite their guest source while those reads were still queued on the Vulkan recorder or copy workers. I added the existing host-copy completion wait before that overwrite, preserving the constant ring and threaded path. The production-branch regression reproduces 2,048 damaged snapshots out of 3,072 with the previous code and zero with the correction. This was one part of the investigation; the later foliage/depth correction resolved the visible flashing in my affected-scene comparison.

## Draw-thread copies in Revision 16

I found that a draw could leave a small geometry copy in its thread's private batch. The command thread then drained the draw queue and waited for host copies, but that wait could not see the unpublished batch. I now hand over those copies at the end of a queued burst, before marking the draw work drained. The existing completion wait can finish them before the guest replaces their source data.

The test uses the actual queue and copy pool: all 384 old cases copied replacement data, and the corrected path preserves the original data in all 384. The copies stay batched, and the threaded renderer, constant ring and upscalers remain enabled. The dated comparisons are kept in [the test history](history/testing-through-21.md); [current reports](known-issues.md) describes the remaining pacing work.

## Queue-lock contention and real-frame pacing

In Revision 20 I moved the shared Vulkan queue lock away from command-recording and host-copy waits. The render and presentation schedulers share one queue, so their actual `QueueSubmit`, `QueueBindSparse` and `QueuePresent` calls still serialize. CPU preparation and local retirement can now proceed without preventing an already-ready frame from being presented. The sparse-binding callback takes its own queue lock and retains the timeline wait consumed by the render submission.

I reproduced the contention by holding five different preparation/retirement phases in the production submission methods. Revision 19 blocks presentation in each one; the new scope allows it to proceed. Recorded Vulkan calls still serialize, and the recorder/copy completions remain before the command-buffer submission. This removes a source of unnecessary delay; the gameplay comparison will tell me how much it helps my scene. The reconstruction-time depth copy and NVIDIA input-completion fences stay in place.

I also added the optional [frametime graph](display-and-overlay.md#reading-the-graph) so ordinary real-frame spikes can be seen without enabling the developer profiler. Its raw presentation intervals complement the FG output count and Reflex latency report.

## Presentation queue scope

In Revision 25 I narrowed another use of the shared Vulkan queue lock. NVIDIA's presentation wrapper collects FG state and latency after QueuePresent; that work used to keep the renderer from submitting its next command buffer on the same queue. The lock now covers the actual presentation call. SDK state collection remains on the presentation thread, under its existing NVIDIA lifecycle lock. Input-completion fences, owned scene depth, motion history and swapchain recovery are retained.

The production-block regression holds the SDK work before/after the queue call. Revision 24 prevents render-queue progress in both cases; the new scope permits it. Holding QueuePresent still blocks another queue operation. I removed this source of contention to improve frame delivery; the same-scene gameplay comparison will show how much it helps on my Windows 11 / RTX 5070 Ti setup and other configurations.
