# Shader-cache recovery

I want the cache to save work between sessions without becoming another reason for the game to fail. Revision 24 is the first small change in the frame-delivery and image-quality work: it improves loading and persistence of shader/pipeline records. The existing Hunter's Dream foliage-history fix, scene-depth copy and FG input fences stay in place.

## What changes

- New records carry their type, exact length and a CRC32 checksum. Existing records remain readable; a bad record can be rebuilt from the original shader.
- File and container lengths are checked before allocating memory or copying bytes. Truncated, oversized and misaligned records are ignored.
- Cached SPIR-V gets a structural check before it reaches the driver. A rejected cached shader, layout or pipeline skips that preload entry; later entries can still load. Fresh shader compilation retains its error checks.
- Partial preload selections are cleared, and incomplete pipeline objects are never inserted as usable cache entries. Missing permutations cannot be mistaken for compiled ones.
- A missing, damaged or incompatible GPU profile clears the old records before writing the current profile.
- Closing the cache rejects new requests and finishes every write already accepted. Failed temporary-file replacement keeps the previous target, and a failed write does not stop later writes.

The on-disk payload versions have not changed. Session-specific motion shaders still compile for their current buffer addresses. Save files, settings and mods are unaffected.

## Why this belongs in P1

Losing pending cache writes forces the next session to repeat compilation. A broken record can also interrupt warm-up instead of allowing the game to rebuild it. I removed those two causes first. I can't guarantee an FPS increase or smoother pacing on every configuration; gameplay comparisons from other users are welcome.

The next part concerns when real and generated frames reach the screen: GPU completion, Vulkan presentation and FG pacing. HUDless FG inputs and transparent/particle motion follow as separate image-quality changes. They need their own HDR and resource-lifetime checks.

## Verification

The regression executable uses the production serializer, cache IO worker and cached-shader creation function, with isolated paths and explicit driver responses. Four producers submit 400 writes while the worker is held; immediate shutdown must preserve all 400. Other cases cover old/new records, checksums, truncation, oversized files, missing records, temporary files, failed replacement and continued work after errors.

A second fixture compiles the actual `WarmUp` body with controlled cache/driver boundaries. It checks missing, malformed and incompatible profiles; unknown/stale pipeline kinds; failed shader/pipeline loading; later valid entries; and clearing partial selections. These automated checks run on Linux and Windows CI. They exercise recovery behavior, without claiming a measured gameplay improvement.

My gameplay setup remains Windows 11 with an RTX 5070 Ti. For a useful comparison, use the same Hunter's Dream view, settings, HDR mode and real/output caps on Revision 23 and 24. Existing records should load normally; after a damaged record is rebuilt, repeat the route once so its first compilation is separate from subsequent use. The [frametime graph](display-and-overlay.md#reading-the-graph) and an inspected [Support Report](support-reports.md) can help document the result.
