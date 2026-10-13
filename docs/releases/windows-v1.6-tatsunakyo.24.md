# Bloodborne: The Crowned Workshop — Revision 24

I started the next renderer work with shader-cache recovery. Closing the game now finishes accepted cache writes, and a damaged or rejected cached pipeline can be rebuilt instead of stopping preload. The Hunter's Dream flashing correction and the separate real/FG output limits are retained.

## Shader cache

New records include a checksum and exact-length/type header; existing records remain readable. The loader checks lengths before allocation, rejects malformed SPIR-V and clears partial preload state after failures. Missing or incompatible GPU profiles start a fresh cache, and empty permutation slots cannot be selected as compiled shaders. Temporary writes still replace a completed record only after successful output.

Four concurrent producers and immediate shutdown retain all 400 accepted records in the production IO regression. The actual warm-up body also recovers from malformed profiles and rejected pipelines while allowing later valid entries to load. Windows and Linux CI run these regressions alongside the existing launcher, support-report and save-integrity checks.

I can't guarantee that this will increase FPS on different configurations. It removes lost cache work and failure paths; I would welcome same-scene comparisons, especially where frame delivery is uneven. Further FG scheduling, HUD separation and particle motion remain on the roadmap.

## Documentation and visual proposals

The README's download/installation table is centered, with its guide links grouped beneath those two choices. My original introduction, banner and feature illustrations are retained. New diagram/UI proposals and FG/launcher animations are available separately for review before replacing the current illustrations.

## Installation

Extract the complete ZIP into a new folder, open **Bloodborne.exe** and select your existing game and saves locations under **Game & files**. You need your own decrypted Bloodborne CUSA03173 1.09 dump. The package includes its build identity, source changes and SHA-256 verification; saves, settings and mods remain yours.

[Cache recovery](../shader-cache.md) · [Roadmap](../tatsunakyo-next.md) · [Current reports](../known-issues.md)
