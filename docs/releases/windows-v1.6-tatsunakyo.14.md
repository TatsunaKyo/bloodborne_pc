<!-- crowned-workshop-navigation -->
> Historical document. [The Crowned Workshop current guides](../index.md) · [Current reports](../known-issues.md). This page retains its original context and credits.

# Bloodborne: The Crowned Workshop — Revision 14

I went back to the session logs after the FPS cap kept landing below the value I chose and assets were still flashing in Revision 13. This build corrects the timer drift, adds another safeguard to object motion history and fixes the missing NVIDIA FG inputs reported in that log. I also brought the launcher sidebar into line with The Crowned Workshop and added visual explanations to the README.

## The cap that kept falling short

In my Windows 11 session, a 75 FPS limit was landing around 73.4 FPS. With an x2 FG output limit of 120, the real frames were landing around 59 FPS. The limiter was adding each small timer delay to the following frame, so it kept slipping behind its own target.

I now preserve the timing schedule through ordinary timer delays. A genuine stall still starts a fresh interval, which keeps queued frames from rushing through after a hitch. The regression checks reproduce the delays from that session at 30, 60, 65, 75, 90 and 120 FPS. Real FPS and the optional FG-output cap remain separate: a 130 output cap at x2 still gives a 65 real-frame ceiling.

## Flashing assets and NVIDIA FG

Repeated instances of a mesh could exchange draw order after culling. Their occurrence number was then enough to match one object with another object's previous positions. I now reject that history when the instances cannot be distinguished safely and use camera motion for those draws. Unique object histories still work, including animation.

I also set the camera pinhole offset explicitly and give NVIDIA FG the correct render/output resource extents. Both were flagged in the diagnostic log. The shared object-history correction applies with FG off too.

I am keeping the flashing report open until I compare the affected scenes on this build. These are specific corrections to unsafe inputs; I still want to see whether any flashes remain in the same routes and settings.

## Launcher and README

- The sidebar now reads **BLOODBORNE: THE CROWNED WORKSHOP**, **by TatsunaKyo**, with the current version and a credit to Super Medo's Windows port. I kept the title on deliberate lines so it fits small windows and higher DPI.
- Play still shows the dedicated DLSS or XeSS selector only when that upscaler is selected. The NVIDIA multiplier keeps its own row above Output.
- The XeSS comparison table now includes **1080p, 1440p and 4K** output examples, calculated with the renderer's even-pixel rounding.
- Every main feature section now has an overview graphic, using the workshop's warm brass, dark panels and crowned TK emblem. The PNGs display on GitHub; their SVG sources and export script are included so I can edit them later.
- I kept my latest README introduction, screenshot and original credits while updating the explanations for this revision.

## Checks and hardware

I rebuilt **Bloodborne.exe** and the native Windows components together. The package includes the compiled-launcher layout and popup results, limiter/history checks, renderer/control regression logs and DLL import/export verification. The compiled launcher passed **180 Play-layout checks** and **84 real XeSS popup selections**. The layout is exercised in English and Russian at **100%, 125%, 150%, 175% and 200%** scaling, including the minimum window size and the longer sidebar title.

My gameplay setup remains **Windows 11 with an RTX 5070 Ti**. The diagnostic session that led to these fixes comes from that PC running Revision 13. The automated checks cover this rebuilt revision; the affected-scene gameplay comparison is the next check. The firing crash, sustained-running stamina and broader AMD/Intel coverage stay in [Testing and known issues](../testing.md).

## Installation

Extract the complete **Bloodborne-Windows-v1.6-TatsunaKyo-Revision-14.zip** into a separate folder, then keep your saves, mods and preferences. Use the whole package: the launcher and renderer changed together. `Start-Verified-Launcher.cmd` checks the included launcher before opening it. The accompanying `.zip.sha256` contains the archive checksum.

No game files are included. You need your own decrypted Bloodborne CUSA03173 1.09 dump.

Maintained by TatsunaKyo. The original game, bbport, Supermedo, shadPS4, community patches and vendor components keep their credits and licenses.
