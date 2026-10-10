# Temporal stability and renderer performance

Revision 10 implements the camera-history and renderer work described below. The changes are by TatsunaKyo; the underlying bbport/shadPS4 renderer and vendor integrations retain their credits.

## Shared camera reset

The captured main camera is now checked once per frame. A move of at least 10 world units, a rotation over 100 degrees in one frame or an abrupt projection change requests a history reset. Ordinary movement, gradual zoom and rotations across the ±π boundary keep history. Missing cameras, invalid matrices and render/provider changes invalidate it; the first valid camera seeds both views again.

On that frame, reconstruction receives the same reset in native and scaled paths. Previous camera and jitter are seeded from the current sample, and old object vectors are ignored. Discarding previous object tables preserves this frame's GPU allocation cursor, so a late camera capture cannot overwrite positions already reserved by a draw. DLSS and XeSS feature recreation also forwards the reset to the already captured FG inputs. FSR, TAA, XeSS, DLSS and FG therefore agree on the transition.

This prevents the renderer from deliberately reprojecting an unrelated preceding scene after a discontinuity. It is a targeted stability change, not a blanket fix for all DLSS shimmering. NVIDIA's [integration checklist](https://developer.nvidia.com/rtx/streamline/get-started) identifies accurate motion, compatible jitter, mip bias and resets as part of the input contract.

## Avoidable work removed

- After the main camera has been captured, later G-buffer bindings skip the redundant guest-memory mapping lookup and signature inspection.
- The scene mip bias retains `log2(render/output)` but caches the value until either dimension changes, avoiding the logarithm on every sampler request.
- Upscaler activity uses one provider snapshot instead of repeatedly loading the atomic setting for each comparison.
- An object-motion image already in General layout can be read again without another read-to-read barrier. Color-attachment writes still transition and synchronize before a reader.
- Index-range verification now assigns each mesh a stable phase within the existing 32-frame interval. A new entry is checked again within 1–32 frames, then every 32 frames, with topology changes still detected and unused entries trimmed.
- Revision 4's cached upscaled-display image view is retained, as is the one-frame default GPU queue.

The production cache fixture loads 4,096 meshes together and uses them for 64 more frames. The old policy rescanned all 4,096 together every 32 frames. The new policy peaks at 149 scans in a periodic frame, with the same 12,288 total scans including the initial load. This measures the distribution of renderer work, not FPS in Central Yharnam.

## Remaining quality work

Motion coverage for particles, transparent surfaces, weapons and newly visible geometry remains worth checking against the color/depth buffers. The existing opaque/skinned-mesh path must keep exact draw identity and full-precision depth rejection. Reducing that precision just to save bandwidth can introduce incorrect distant motion.

FG quality around text needs real HUDless scene color and matching UI-alpha buffers. Further DLSS improvements may require moving scaled reconstruction earlier in post-processing: native AA uses HDR scene color, while scaled presets currently reconstruct the tonemapped scene. That requires a coordinated post-processing and SDR/HDR change, rather than changing one NGX flag.

The current mip bias already restores fine texture detail. More negative bias or stronger sharpening can increase shimmer, so those are tuning choices to compare on a moving scene. The optional profiler helps quantify future changes; it is not a prerequisite for removing redundant work that is identifiable in the code.

For the main gameplay configuration and open regression checks, see [Testing and known issues](testing.md).
