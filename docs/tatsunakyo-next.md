# Next work for the TatsunaKyo revision

The in-game menu stays in English and Russian. Additional translations are out of scope. Revision 7 fixes the cheat player lookup, adds FSR HDR10, and introduces experimental NVIDIA FG/MFG, independent Reflex and an optional output cap. The implementation and its test limits are described in [the FG guide](frame-generation.md).

## Frame Generation

- Classical **FSR Frame Generation** is implemented for SDR/HDR10 and the temporal upscalers. Physical-GPU gameplay, desktop pacing and HUD quality still need testing.
- **NVIDIA Frame Generation and Multi Frame Generation** now have a compiled Vulkan backend and runtime multiplier checks. Actual RTX gameplay/HDR and latency measurements are still needed.
- A separate **FG preset A/B** choice, distinct from the E–L super-resolution presets. Put FG choices in both the launcher and the R3+L3 menu once connected to the renderer.
- AMD ML Frame Generation can wait while it depends on a DirectX 12 provider.

The Vulkan renderer calls FSR-Vulkan's analytical FSR 3.1.6 FI/OF APIs. Its real capture and interpolation passes pass SDR/HDR headless GPU tests with synchronization validation. The game HUD is still in interpolation; separate HUDless and UI-alpha buffers remain follow-up work. NVIDIA capture keeps only stable depth/motion and uses the actual swapchain color, avoiding unused FSR color/interpolation allocations.

The NVIDIA backend uses official Streamline 2.14.1 production binaries, Vulkan creation/acquisition/presentation hooks, actual camera/resource tags and shared frame-token Reflex markers. Buffer ownership is tied to the SDK input-completion fence. Background pause and 30/60 caps disable generation. These paths still need physical RTX testing; they are not described as validated gameplay.

The SDK's `DLSSGOptions` has no public A/B render-preset field. NVIDIA's public NVAPI driver-settings header does define separate FG preset A/B overrides. That path needs testing for a game-specific profile, preservation of existing user settings, and whether a change needs feature recreation or restart. Do not label the UI-recomposition option as a verified A/B selector without that check.

References: [FSR-Vulkan](https://github.com/FireBurn/FSR-Vulkan), [Streamline DLSS-G guide](https://github.com/NVIDIA-RTX/Streamline/blob/v2.14.1/docs/ProgrammingGuideDLSS_G.md), [manual Vulkan hooks](https://github.com/NVIDIA-RTX/Streamline/blob/v2.14.1/docs/ProgrammingGuideManualHooking.md), [NVAPI settings](https://github.com/NVIDIA/nvapi/blob/main/NvApiDriverSettings.h).

## Gameplay cheats

The revision 5 hooks had an incorrect player virtual call, corrected in revision 7; see [the cheat guide](cheats.md). The runtime now compares against the actual main player without a game virtual call, and skips player-only changes during loading. Signatures and the RIP-relative lookup match the supplied CUSA03173 1.09 image. Tests execute both the native trampolines and the actual Windows-compiled object, including missing-world/player cases. Whole-feature guards remain in place. Stamina and item/ammunition use take the game's no-consumption branches; generic inventory writes are untouched.

Tests execute the generated hooks, check every multiplier, preserve CPU state, leave NPC behavior and disabled features unchanged, and save/reload the actual launcher and in-game controls. Player death, loading screens, scene changes and save reloads still require a gameplay test on Windows. The build does not claim those tests have been performed.
