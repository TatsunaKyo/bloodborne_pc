# Bloodborne for Windows v1.6 — TatsunaKyo revision 10

The renderer now resets temporal history when the camera teleports, turns abruptly, changes projection or returns after loading/menu frames without a camera. DLSS, FSR, XeSS, TAA and FG receive the same transition. Ordinary movement and gradual zoom keep accumulation. Stale object history is discarded without rewinding GPU position allocations, and DLSS/XeSS feature recreation also resets FG inputs.

The update also removes repeated camera mapping checks, caches unchanged scene mip bias, skips repeated object-image read-to-read barriers and spreads index-buffer revalidation across 32 frames. In the production cache fixture with 4,096 meshes, the periodic peak is 149 scans/frame instead of 4,096; the maximum verification interval and total work remain the same. This is a renderer-work comparison, not a measured gameplay FPS increase.

The README now has a project graphic and a complete guide to the fork's features. Gameplay testing on TatsunaKyo's Windows 11 / RTX 5070 Ti PC, automated regression coverage and open issues are collected on a shared testing page. Historical release notes retain their original checks and link to that coverage.

The launcher and native Windows components are rebuilt. Production camera-history and motion-history tests pass, including smooth motion/FOV, discontinuities, loading gaps, invalid data, recovery and late object-history invalidation. Launcher settings/update/layout checks and package integrity are included with the build. The source commit, executable hashes and ZIP SHA-256 identify the exact package.

The shooting crash remains under investigation. FG HUD separation, Dynamic MFG, XeSS FG, AMD ML FG and FG model presets A/B are not added by this update. Current gameplay regression checks are listed in [Testing and known issues](../testing.md).

Revision by TatsunaKyo. Original port and third-party credits/licenses are retained.
