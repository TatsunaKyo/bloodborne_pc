> Historical/upstream record: statements and test results below describe their original revision or environment. [Current guides](../index.md) · [Current reports](../known-issues.md) · [Published releases](../releases/index.md)

<!-- crowned-workshop-navigation -->
> Historical document. [The Crowned Workshop current guides](../index.md) · [Current reports](../known-issues.md). This page retains its original context and credits.

# Bloodborne: The Crowned Workshop — Revision 15

Assets were still appearing and disappearing in my Revision 14 tests, so I went back through the rendering commands instead of stopping at motion history. This revision corrects a delayed geometry-read dependency, gives the launcher the workshop's full visual identity and replaces the outdated development plan with the current inventory and release order.

## Queued geometry reads

Before replacing ConstRam data, the port waited for the draw queue. Some vertex/index copies were still waiting on another recording thread or a copy worker, though, and could read the next contents of that memory. I now complete those reads before the replacement. The constant ring, threaded renderer, upscalers and FG remain available.

I compiled the actual command branch into a delayed-read regression. The old behavior corrupts 2,048 of 3,072 snapshots; the corrected branch preserves all 3,072. This covers direct, recorder and worker copies with both draw-pipeline states. The flashing report remains open for the affected-scene comparison on this build; the earlier temporal-history safeguards are retained too.

## The workshop in the launcher

Play now uses my workshop painting, the hunter, lantern and pale-red moon, with live lettering and the crowned TK mark. I changed the whole interface's palette, framed the Play panels, added a clear active navigation row and brought the headings, controls and Play button into the same slate-and-brass design. Keyboard navigation works alongside mouse selection.

The small-window layout has a compact hero so the quick settings still fit. DLSS and XeSS keep their conditional selectors, the NVIDIA multiplier keeps its own row, and the FG label is shortened on Play so its selected value fits. The sidebar retains my name, version and the credit to Super Medo's original port. The existing game/save paths and updater stay the same.

## A current development plan

The roadmap now reflects the code after Revision 14 and this revision's work, rather than the old Revision 10 audit. It records the unresolved flashing, firing, sprint stamina and Echoes reports; scopes the first Save Manager; separates input/ultrawide/HUD work; and checks all fourteen proposed cheats against the existing hooks and patches. Dynamic MFG, XeSS FG/XeLL, AMD ML FG and FG model presets stay in their own feasibility stage.

I am tackling existing gameplay bugs next, followed by closed-game save backup/restore. Progression cheats wait for save protection. Each stage has concrete checks before I call it complete.

## Build and checks

Bloodborne.exe and the native Windows components are rebuilt together. The compiled launcher checks cover 180 layouts in English/Russian at 100–200% scaling, the live hero's text/artwork, minimum size, keyboard navigation and 84 XeSS popup selections. Shared preferences/update checks and the geometry-read regression pass. The limiter and motion-history checks remain covered, and the package records the compiled programs and runtime hashes.

My gameplay baseline remains Windows 11 with an RTX 5070 Ti. The visual issue was still present in Revision 14; this package is ready for the same-scene comparison. The [testing page](../testing.md) keeps the other open bugs and hardware checks together.

Extract the complete ZIP into a separate folder and keep your saves, preferences and mods. No game files are included. The checksum and prepared release page accompany the package.

Revision and art direction: TatsunaKyo. Original game, port, renderer, community and vendor credits and licenses are retained. [Upstream issue 44](https://github.com/deadinside28/bloodborne_pc/issues/44) was a useful reference when tracing the ConstRam dependencies; this fork's host-copy ordering correction is described in the source and regression.
