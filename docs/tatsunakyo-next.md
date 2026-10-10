# Next work for the TatsunaKyo revision

The in-game menu stays in English and Russian; extra translations are out of scope. The current feature list is in the [README](../README.md), and gameplay coverage and open bugs are in [Testing and known issues](testing.md).

Revision 10 implements shared camera-cut history resets, safe object-history invalidation and several renderer optimizations. Details and the cache workload comparison are in [Quality and performance](quality-and-performance.md).

## Frame Generation

Analytical **FSR 3.1.6 FG** and fixed **NVIDIA FG/MFG** are included for SDR/HDR10. NVIDIA uses Streamline 2.14.1 production runtimes, actual camera/resource tags and frame-token Reflex markers. SDK input-completion fences protect buffer ownership. The normal FPS cap counts real frames, and the optional total cap accounts for the negotiated multiplier. Reflex also works independently of FG.

The remaining FG work is:

- Separate the game's HUD from interpolation using genuine HUDless color and matching UI color/alpha. This can improve text and counter stability.
- Investigate **FG presets A/B** through NVIDIA's public driver-setting interface. `DLSSGOptions` does not expose an A/B model field. A UI-recomposition toggle is not an equivalent selector. Driver profile changes must preserve existing settings and have a confirmed effect before adding an end-user choice.
- **NVIDIA Dynamic MFG** and **Intel XeSS FG** currently require D3D12 in their public integrations. They are not available through this Vulkan path. Intel XeSS Super Resolution is already included.
- **AMD ML Frame Generation** remains follow-up work; the shipped FSR FG path is analytical.

References: [FSR-Vulkan](https://github.com/FireBurn/FSR-Vulkan), [Streamline DLSS-G guide](https://github.com/NVIDIA-RTX/Streamline/blob/v2.14.1/docs/ProgrammingGuideDLSS_G.md), [manual Vulkan hooks](https://github.com/NVIDIA-RTX/Streamline/blob/v2.14.1/docs/ProgrammingGuideManualHooking.md), [NVAPI settings](https://github.com/NVIDIA/nvapi/blob/main/NvApiDriverSettings.h), [Intel XeSS](https://github.com/intel/xess).

## Gameplay and renderer follow-up

Investigate the reported shooting crash with multiple cheats enabled, confirm continuous-running stamina in the affected states, and compare the new temporal resets during respawn/teleport/loading. Wider GPU and driver coverage will help identify compatibility issues beyond the main Windows 11 / RTX test PC.

Further renderer work can target transparent/particle motion coverage and earlier scaled reconstruction, while preserving native UI, HDR and exact object-history identity. A settings search and a repeatable benchmark capture would also make the growing launcher easier to use and regressions easier to compare.

Maintained by TatsunaKyo. Original authors and vendor licenses remain credited.
