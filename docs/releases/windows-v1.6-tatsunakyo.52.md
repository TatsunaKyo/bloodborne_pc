# TatsunaKyo revision 52

Rebuild the rendering/memory-cache subsystem around Supermedo's shadPS4 0.20.1 update. Fix the reproduced LRU termination defect and moving cache-object storage, and retain recently off-screen textures using age in seconds. Update the corresponding shader compiler, per-buffer barriers, image readbacks and index bounds as one compatible change.

Preserve native NVIDIA FG/Reflex, the explicit RTX 20/30 mod gate, launcher controls, issue-time copy fences, temporal history safeguards and bounded direct vertex uploads. Retire the old speculative watch/prefetch policies. Fix precise writable snapshot ordering and persist generated fragment shader payloads. Incompatible shader-cache records rebuild once (versions 12/9/7).

Verification includes the Windows build, actual compiled launcher UI, protected host mappings and the real asynchronous worker/C runtime, old/current cache controls, serialization and SPIR-V validation. A controlled 9000-resource growth moves no existing cache objects; a termination callback stops after one item instead of 10000; the controlled collector retains resources seen 33 ms earlier instead of evicting ten. These are local correctness/operation-count results, not gameplay performance measurements.

The cemetery hitch, displayed FG cadence, stairs halo and transient geometry still require target gameplay validation. The package is an investigation build; it is not evidence that those symptoms are eliminated.

[Full source comparison and verification limits](../investigations/2026-10-17-renderer-refresh.md).
