# Bloodborne: The Crowned Workshop — Revision 16

Revision 15 was better on my PC, but I still had assets appearing and disappearing in the Hunter's Dream. I went back through the geometry uploads first. I also rebuilt the in-game menu: it needed proper tabs and a more compact layout.

## The next geometry-read correction

Some small copies could remain in the draw thread's private batch after its draw queue was marked drained. The command thread's copy wait could not see that unpublished work, so the game could replace its source memory before the copy actually ran.

I now publish the batch at the end of a queued draw burst, before reporting the queue drained. The existing completion wait then finishes those reads before ConstRam or a guest-visible write replaces their source. Copies remain batched, and the threaded renderer, constant ring, upscalers and FG remain available.

The regression runs the actual draw queue and copy pool with short, medium and long bursts. The old code leaves all 384 snapshots unfinished and later copies replacement data into them; the corrected code preserves all 384 original snapshots. Address and undefined-behavior checks pass too, alongside the existing ConstRam regression. I am keeping the Hunter's Dream report open for the same-scene comparison on this build.

## A smaller menu with tabs

**Insert / L3+R3** now opens seven sections:

| Tab | What you find there |
|---|---|
| Image | Upscaler, DLSS model/XeSS quality, quality scale and resolution. |
| Frames | Real-game FPS, FSR/NVIDIA FG, multiplier, optional output cap, Reflex and Anti-Lag 2. |
| Window | Window mode, borderless V-sync, background behavior and menu language. |
| Overlay | The performance overlay and its optional preset, resolutions, FG and latency details. |
| Cheats | The existing live and startup cheats, with their availability/restart state. |
| Effects | Model detail and game effects, in two columns when there is enough room. |
| Advanced | Sharpening, jitter, reactive mask and motion-vector diagnostics. |

I kept Close and Apply/restart outside the scrolling page, put each FPS drag control beside its exact numeric entry on one row, wrapped long checkbox labels and kept stable control IDs across languages. The selected tab survives a language change or resize. Slate panels, brass accents and my crowned TK mark bring the menu into the workshop's design.

![The Crowned Workshop in-game settings](../assets/crowned-workshop-menu.png)

The existing controls, shared settings and English/Russian support are retained. This revision reorganizes the cheats; firing with several cheats, sustained sprint stamina and Echoes multiplication remain the next gameplay fixes.

## Build and checks

I rebuilt **Bloodborne.exe** and the native Windows components. The real ImGui regression checks mouse/keyboard/controller activation, dropdowns, checkboxes, exact FPS entry and saving through the new tabs. It also passes **1,960 layouts** across both languages, all upscalers, 100–200% scaling and viewports from 960×540 to 4K, including child scrolling, resizing and the pinned footer. The compiled launcher still passes its preferences/update checks, **180 layouts** and **84 XeSS popup selections**.

My gameplay configuration is Windows 11 with an RTX 5070 Ti. The Hunter's Dream was still affected in my Revision 15 test, and it is the first scene to compare on Revision 16. The test logs distinguish command/memory and UI checks from gameplay results. Reports from other configurations are welcome.

Extract the complete ZIP into a separate folder and keep your saves, preferences and mods. No game files are included. The ZIP checksum and prepared release page accompany the package. [Testing and open issues](../testing.md) · [Development roadmap](../tatsunakyo-next.md).

Revision and art direction: TatsunaKyo. Original game, port, renderer, community and vendor credits and licenses are retained.
