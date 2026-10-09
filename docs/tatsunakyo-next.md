# Next work for the TatsunaKyo revision

The in-game menu stays in English and Russian. Additional menu translations are
out of scope for now. Resolution readout and background behavior are in revision 3;
the items below are still work to do, not features enabled by that package.

## Frame Generation

- Classical **FSR Frame Generation**, for compatible AMD, NVIDIA and Intel GPUs.
- **NVIDIA Frame Generation and Multi Frame Generation**, with available frame
  multipliers determined by the runtime and GPU.
- A separate **FG preset A/B** choice, distinct from the E–L super-resolution
  presets. Put FG choices in both the launcher and the R3+L3 menu once connected
  to the renderer.
- AMD ML Frame Generation can wait while it depends on a DirectX 12 provider.

The current renderer uses Vulkan. Its FSR-Vulkan dependency contains analytical
FSR 3.1.6 FI/OF APIs, but the game does not yet call them. The integration needs
output-size scene color, R32 depth and motion vectors kept alive for each real
frame, a separate interpolation target, history resets, and correctly paced
generated/real presentation. The existing upscaler feeds cameras and motion, but
its input images can be reused before asynchronous presentation completes.

For NVIDIA, the official Streamline 2.14.1 SDK supports Vulkan hooks and fixed
MFG. It requires presentation/acquisition hooks, device requirements, extra queues,
resource tags with actual layouts and lifetimes, frame constants, and Streamline
Reflex markers using the same frame index. Availability and multiplier choices
must come from runtime support checks. Disable FG in background FPS modes.

The SDK's `DLSSGOptions` has no public A/B render-preset field. NVIDIA's public
NVAPI driver-settings header does define separate FG preset A/B overrides. That
path needs testing for a game-specific profile, preservation of existing user
settings, and whether a change needs feature recreation or restart. Do not label
the UI-recomposition option as a verified A/B selector without that check.

References: [FSR-Vulkan](https://github.com/FireBurn/FSR-Vulkan),
[Streamline DLSS-G guide](https://github.com/NVIDIA-RTX/Streamline/blob/v2.14.1/docs/ProgrammingGuideDLSS_G.md),
[manual Vulkan hooks](https://github.com/NVIDIA-RTX/Streamline/blob/v2.14.1/docs/ProgrammingGuideManualHooking.md),
[NVAPI settings](https://github.com/NVIDIA/nvapi/blob/main/NvApiDriverSettings.h).

## Gameplay cheats

| Choice | Values | Intended behavior |
|---|---|---|
| Player damage | Off, x2, x4, x8, x16 | Multiply damage dealt by the player |
| Damage reduction | Off, x2, x4, x8, x16 | Divide incoming enemy damage; keep defense stats unchanged |
| Blood Echoes earned | Off, x2, x4, x8, x16 | Multiply newly earned echoes, not the stored balance |
| Movement speed | Off, x1.5, x2, x4, x8, x16 | Scale player movement |
| Infinite stamina | Off, On | Keep player stamina from being consumed |
| Consumables | Off, On | Preserve quantity when an item is used |

These require the decrypted CUSA03173 1.09 executable to verify the instructions,
player identification and call sites. It is not present in the build workspace.
Existing PS4 trainer hooks cannot be copied directly: some use PS4 heap pointers
or caves outside the port's ELF load segments. Item patches that force the count
to 20 also do not implement the requested behavior.

Check the original instructions before installing each hook, use port-owned code
storage, distinguish the player from enemies and separate item use from selling,
discarding or buying. Keep all new cheats disabled by default. Test each multiplier,
scene transitions, player death and reloads, and the unmodified game path before
claiming support.
