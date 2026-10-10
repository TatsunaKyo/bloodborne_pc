# Bloodborne for Windows v1.6 — TatsunaKyo revision 10

I added a shared history reset so teleports, abrupt camera turns, projection changes and returning from loading/menu frames start from the new scene. DLSS, FSR, XeSS, TAA and FG receive the same transition. I keep accumulation during ordinary movement and gradual zoom. Stale object history is discarded without rewinding GPU position allocations, and DLSS/XeSS feature recreation also resets FG inputs.

I also removed repeated camera mapping checks, cached unchanged scene mip bias, skipped repeated object-image read-to-read barriers and spread index-buffer revalidation across 32 frames. I wanted to reduce avoidable work and the periodic bursts from checking all meshes together. In the production cache fixture with 4,096 meshes, the periodic peak is 149 scans/frame instead of 4,096; the maximum verification interval and total work remain the same. That is a renderer-work comparison. A gameplay FPS gain needs its own measurement.

I rewrote the README with a project graphic and a guide to the fork's features, so you can see what changed and where to find each option. My Windows 11 / RTX 5070 Ti gameplay results, automated regression coverage and open issues are collected on a shared testing page. Historical release notes retain the checks that were actually run and link to that coverage.

I rebuilt the launcher and native Windows components. Production camera-history and motion-history tests pass, including smooth motion/FOV, discontinuities, loading gaps, invalid data, recovery and late object-history invalidation. Launcher settings/update/layout checks and package integrity are included with the build. The source commit, executable hashes and ZIP SHA-256 identify the exact package.

I am still investigating the shooting crash. FG HUD separation, Dynamic MFG, XeSS FG, AMD ML FG and FG model presets A/B remain follow-up work. Current gameplay regression checks are listed in [Testing and known issues](../testing.md).

Revision by TatsunaKyo. Original port and third-party credits/licenses are retained.
