# Bloodborne: The Crowned Workshop — Revision 28

The motion-history change in this revision caused flashing geometry during gameplay and is rolled back in [Revision 29](windows-v1.6-tatsunakyo.29.md). Use Revision 29 for the corrected build; the notes below describe what Revision 28 originally changed.

I separated the download into the ordinary game package and an optional Developer archive. The game package keeps the launcher, native components, every existing graphics runtime, documentation and licenses. The Developer archive keeps the source records, regression programs and specialist capture scripts. Every file from the complete candidate is retained in one of the two archives; the complete source patch also stays in the game package for compatibility with installed updaters.

I corrected a temporal-history case for newly visible tracked geometry. A draw with no usable previous positions now marks its pixels explicitly, so reconstruction and FG can reject unrelated history instead of falling back to camera motion. The full-precision depth comparison still rejects vectors covered by a different surface. The shader cache version changes with this correction, so old compiled shaders cannot silently retain the previous behavior.

I also extended the existing frame capture with each draw's blend equation, alpha factors, write mask and blend constants. Those records are needed for the next HUD separation step, especially where additive UI highlights and translucent font edges behave differently. This build does not yet supply HUDless color or a genuine UI-alpha layer to FG. Particle and transparent-surface motion, and earlier HDR reconstruction for scaled DLSS, remain separate work.

## GitHub checks

The failed `9cc5370` regression run checked the launcher before its window had mapped. Revision 27 corrected that startup test, and its final Windows and Linux jobs passed. A separate published-release check had started before the ZIP was uploaded; rerunning it after the files were present passed. I now allow a short, bounded upload window and retain a structured failure record. Both new archives and their checksums must match the same revision and source commit before release preparation can succeed.

## Verification

The archive tests check retained contents, interrupted exports, missing or corrupted Developer packages, identity mismatches and old updater compatibility. The temporal test executes the production motion-shader body on the CPU for eight cases, including newly visible, covered, invalid and behind-camera pixels. The Vulkan fixture includes the same new cases for hardware testing. The gameplay comparison still needs to be made on my Windows 11 / RTX 5070 Ti setup; automated checks alone cannot show how a moving scene looks.

## Installation and publication

Extract the ordinary game ZIP into a new folder and select your existing game and saves locations in Game & files. Keep your saves, mods and settings. The Developer ZIP is optional for playing: extract it beside the game folder if you want its tests or capture scripts. A diagnostic also accepts your installation folder as its first argument.

Upload both ZIPs and both matching `.zip.sha256` files before publishing. The prepared release page records their exact hashes and source commit. No game files or personal saves are included.
