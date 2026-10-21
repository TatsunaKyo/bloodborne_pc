> Historical/upstream record: statements and test results below describe their original revision or environment. [Current guides](../index.md) · [Current reports](../known-issues.md) · [Published releases](../releases/index.md)

<!-- crowned-workshop-navigation -->
> Historical document. [The Crowned Workshop current guides](../index.md) · [Current reports](../known-issues.md). This page retains its original context and credits.

# Bloodborne Windows v1.6 — TatsunaKyo revision 6

I added the first experimental FSR Frame Generation path here. Choose **FSR Frame Generation (2x)** in Graphics or the Insert / L3+R3 menu. It works with the temporal upscalers, including DLSS, and starts off. This initial implementation uses SDR. With HDR enabled or the upscaler switched off, it keeps presenting real frames; HDR support followed in Revision 7.

I keep each frame's color, depth and motion alive through interpolation and presentation. Resizing and background pauses reset history. Pause and the 30/60 FPS background limits suspend generation while the window is unfocused. Real-frame FPS limits are unchanged; one interpolated frame adds another presentation update, with its own GPU and pacing cost.

I checked FSR's actual optical-flow and interpolation dispatches, resource copies, generated pixels, history resets, resizing and background transitions with the headless Vulkan integration fixture. Synchronization validation reported no errors or warnings. I rebuilt the native Windows renderer and launcher from this revision. The tests also click the FG selector in both menu languages and check that launcher settings preserve it.

Gameplay coverage is documented in [Testing and known issues](../testing.md). The game's HUD is included in interpolation and may show artifacts; the port's OSD and settings are drawn afterward. I would welcome performance and latency comparisons from other setups. See [the Frame Generation guide](../frame-generation.md) for details. NVIDIA FG, Multi Frame Generation, their A/B presets and AMD ML FG are not included yet.

All revision 5 changes are included: the live cheats, cooperative background pause, working in-game controls, 75 FPS choice, conditional DLSS preset selector, compact optional overlay details and image-view reuse. Extract the full archive to a new folder and start its **Bloodborne.exe**. Keep `bin`, `_internal` and the runtime assets together; replacing only the launcher does not update the native renderer. Game files are not included.

Revision by TatsunaKyo, based on Supermedo's Windows port. Existing credits for shadPS4, FSR-Vulkan, AMD FidelityFX, NVIDIA NGX, Dear ImGui and community patches are preserved with their licenses.
