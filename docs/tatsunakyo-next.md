# Next work for the TatsunaKyo revision

The in-game menu stays in English and Russian. Additional menu translations are out of scope for now. Resolution readout and background behavior are in revision 3; the control/pause fixes are in revision 4, live cheats in revision 5 and experimental analytical FSR FG in revision 6. NVIDIA FG/MFG remains the implementation work below.

## Frame Generation

- Classical **FSR Frame Generation** is implemented in revision 6 for SDR and the temporal upscalers. Physical-GPU gameplay, presentation pacing and HUD quality still need testing; see [the FG guide](frame-generation.md).
- **NVIDIA Frame Generation and Multi Frame Generation**, with available frame multipliers determined by the runtime and GPU.
- A separate **FG preset A/B** choice, distinct from the E–L super-resolution presets. Put FG choices in both the launcher and the R3+L3 menu once connected to the renderer.
- AMD ML Frame Generation can wait while it depends on a DirectX 12 provider.

The Vulkan renderer now calls FSR-Vulkan's analytical FSR 3.1.6 FI/OF APIs. It copies output-size scene color, R32 depth and pixel motion vectors into owned per-frame images, records a separate interpolation target and retires resources after GPU completion. The headless integration test exercises the actual shader and generated output with synchronization validation. The first version includes the game HUD in interpolation; separating it and adding HDR remain follow-up work.

For NVIDIA, the official Streamline 2.14.1 SDK supports Vulkan hooks and fixed MFG. It requires presentation/acquisition hooks, device requirements, extra queues, resource tags with actual layouts and lifetimes, frame constants, and Streamline Reflex markers using the same frame index. Availability and multiplier choices must come from runtime support checks. Disable FG in background FPS modes.

The SDK's `DLSSGOptions` has no public A/B render-preset field. NVIDIA's public NVAPI driver-settings header does define separate FG preset A/B overrides. That path needs testing for a game-specific profile, preservation of existing user settings, and whether a change needs feature recreation or restart. Do not label the UI-recomposition option as a verified A/B selector without that check.

References: [FSR-Vulkan](https://github.com/FireBurn/FSR-Vulkan), [Streamline DLSS-G guide](https://github.com/NVIDIA-RTX/Streamline/blob/v2.14.1/docs/ProgrammingGuideDLSS_G.md), [manual Vulkan hooks](https://github.com/NVIDIA-RTX/Streamline/blob/v2.14.1/docs/ProgrammingGuideManualHooking.md), [NVAPI settings](https://github.com/NVIDIA/nvapi/blob/main/NvApiDriverSettings.h).

## Gameplay cheats

Implemented in revision 5; see [the live-cheat guide](cheats.md). The supplied CUSA03173 1.09 executable's instruction signatures match all ten hooks. The runtime uses its own code allocation and the game's local-player method, with whole-feature signature guards. Stamina and normal item/ammunition use follow the engine's no-consumption branches. The equipped-ammunition path keeps its decrement at zero when enabled; generic inventory writes are untouched.

Tests execute the generated hooks, check every multiplier, preserve CPU state, leave NPC behavior and disabled features unchanged, and save/reload the actual launcher and in-game controls. Player death, loading screens, scene changes and save reloads still require a gameplay test on Windows. The build does not claim those tests have been performed.
