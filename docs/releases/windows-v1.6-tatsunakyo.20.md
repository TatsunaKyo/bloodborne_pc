> Historical/upstream record: statements and test results below describe their original revision or environment. [Current guides](../index.md) · [Current reports](../known-issues.md) · [Published releases](../releases/index.md)

<!-- crowned-workshop-navigation -->
> Historical document. [The Crowned Workshop current guides](../index.md) · [Current reports](../known-issues.md). This page retains its original context and credits.

# Bloodborne: The Crowned Workshop — Revision 20 preview

My latest Revision 19 test suggests the Hunter's Dream flashing is finally resolved on my Windows 11 / RTX 5070 Ti. I still notice some inconsistent frame delivery, so I have kept that visual correction and focused this revision on pacing and a clearer way to see it.

I found the shared Vulkan queue lock was being held while the renderer waited for command recording and CPU copies, and while it prepared the next command buffer. An already-ready presentation could be delayed by those waits. I now keep the lock around the actual queue operations, including sparse binding, with the existing dependencies and FG input protections retained. The regression reproduces the old blockage and checks that presentation can proceed through all five host preparation/retirement phases.

I added **Show frametime graph in overlay** in the launcher's **Display & FPS** page and the in-game **Overlay** tab. It shows the last 240 real-frame presentation intervals, with the latest and peak time. I keep the samples raw so hitches are visible. The graph is small and optional; switching it off restores the overlay's original height.

With x2 FG at 120 output FPS, a steady 60 real FPS reads about 16.7 ms on the graph. The **Real** label makes that distinction clear. The existing output FPS still uses NVIDIA's confirmed presentation count. The graph and Reflex PC-latency readout measure different things; the [overlay guide](https://github.com/TatsunaKyo/bloodborne_pc/blob/windows/docs/display-and-overlay.md) explains them.

I also shortened the main README and kept it focused on the features. Upscaling and Frame Generation stay first; preset tables, XeSS examples, latency details, menu settings and rendering work now have their own linked pages. Revision-by-revision fixes stay in the release notes and technical guides.

**Bloodborne.exe and the native Windows components are rebuilt.** Checks cover 6,144 frametime samples, graph clicks/saving and twenty compact overlay layouts, 1,960 menu layouts, 180 compiled-launcher layouts and 84 XeSS popup selections. The queue test runs the production methods with recorded Vulkan entry points and address/undefined-behavior checks. These checks pass; I still want to compare the pacing change in the same scene on my PC before claiming a gameplay improvement. Reports from other configurations are welcome.

Extract the full package into a separate folder, select your existing game and saves folders, and start Bloodborne.exe normally. Keep the existing HDR, DLSS preset and FPS caps for the first comparison. The earlier upscaling, FG, window, menu, overlay, cheats and capture controls remain available. The firing crash, running-stamina and Echoes reports stay on the roadmap.

No game files are included. You need your own decrypted Bloodborne CUSA03173 1.09 dump.

Maintained by TatsunaKyo, based on Super Medo's native Windows port and bbport/shadPS4. Original and vendor credits/licenses remain included.
