<!-- crowned-workshop-navigation -->
> Historical document. [The Crowned Workshop current guides](../index.md) · [Current reports](../known-issues.md). This page retains its original context and credits.

# Bloodborne: The Crowned Workshop — Revision 21 preview

I wanted the settings to be easier to find before launching and while playing. Both interfaces now use the same seven categories: **Image, Frames, Window, Overlay, Cheats, Effects and Advanced**. Reflex and Anti-Lag 2 are together in Frames, sharpening and object motion are in Image, model detail and game effects are in Effects, and background behavior stays in Window. Menu language is in Advanced.

I separated the launcher's Settings pages from the launcher tools and added bordered sections within each page. Each complete control has one home. Play keeps the quick choices you already use, grouped into Image, Frames and Window/overlay, with conditional DLSS/XeSS controls and a separate NVIDIA FG multiplier. Customize overlay… opens Overlay. Game files, mods, online setup and logs keep their own launcher pages.

I kept my updated upscaling, FG and latency introductions and gave the other README features the same treatment. The main page now explains the benefits and available choices, including exact real/FG output caps and background Pause / 30 / 60 modes. The eleven editable feature images use concrete examples and the workshop's existing identity. Detailed implementation notes remain in the linked guides.

**Bloodborne.exe and the native Windows menu component are rebuilt.** The controls extracted from the compiled launcher pass 180 layout cases and 84 XeSS popup selections. The actual ImGui controls pass 1,960 menu layouts, click/save checks and twenty compact frametime-overlay layouts. The category check matches 54 shared settings and verifies that each complete launcher control has one owner. Labels in all eleven new figures fit their measured widths; the exports were also inspected at mobile width.

The Revision 19 flashing correction and Revision 20 pacing work/optional frametime graph remain included. This revision reorganizes their controls without changing the rendering pipeline or cheat hooks. My Windows 11 / RTX 5070 Ti gameplay report remains the latest comparison for the flashing fix; further pacing comparisons and reports from other PCs are welcome. The firing, sustained-running stamina and Echoes reports remain on the roadmap.

Extract the full package into a separate folder, choose your existing game and saves folders in **Game & files**, and start Bloodborne.exe. Your saved choices use the same keys, so the category changes do not require reconfiguring them. No game files are included; you need your own decrypted Bloodborne CUSA03173 1.09 dump.

Maintained by TatsunaKyo, based on Super Medo's native Windows port and bbport/shadPS4. Original and vendor credits and licenses remain included.
