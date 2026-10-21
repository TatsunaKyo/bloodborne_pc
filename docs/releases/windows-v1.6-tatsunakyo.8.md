> Historical/upstream record: statements and test results below describe their original revision or environment. [Current guides](../index.md) · [Current reports](../known-issues.md) · [Published releases](../releases/index.md)

<!-- crowned-workshop-navigation -->
> Historical document. [The Crowned Workshop current guides](../index.md) · [Current reports](../known-issues.md). This page retains its original context and credits.

# Bloodborne Windows v1.6 — TatsunaKyo revision 8

I added an editable number field alongside both FPS drag controls because setting an exact value with the slider was frustrating. In the launcher, dragging changes one FPS per pixel, with finer movement while holding Shift. In-game, the total FG cap accepts typed numbers and commits them with Enter or when leaving the field. The normal cap counts real game frames; the optional FG cap counts the total. For example, 75 real FPS with a total cap of 130 at 2x derives a ceiling of 65 real FPS. Generated frames do not advance game logic or physics.

I moved Frame Generation and the NVIDIA multiplier onto Play as well. I also made the entire DLSS preset row disappear when another upscaler is selected; it comes back with your saved preset when selecting DLSS again. The Graphics page uses the same settings. The preset labels remain E/F (CNN / legacy), J/K (Transformer 1st gen), and M/L (Transformer 2nd gen).

I corrected the SDR format check: FG was rejecting the desktop's UNORM images with an sRGB color space. Those formats are now accepted. FSR also decodes and re-encodes sRGB around interpolation, while HDR10 keeps its existing PQ/linear/PQ path. NVIDIA keeps its native SDR/HDR10 backbuffer. I changed its FPS readout to use the SDK's actual presentation count after presenting, with real FPS shown separately in the menu. FG is shown as active only after the SDK confirms generation.

I added optional overlay fields for the active FG provider/multiplier and PC latency from completed NVIDIA Reflex reports. They start off and stay on the same row as the existing information. Unavailable latency is shown as N/A. PC latency measures CPU simulation start to GPU completion; it does not include the monitor or input device, and is not inferred from frame time. Reflex remains usable with FG off.

I added XeSS Super Resolution using Intel's XeSS 3.0.2 Vulkan API and unmodified runtime, to give supported Intel GPUs another option. It uses scene color, depth, motion vectors, jitter and history resets, with half-float color for SDR/HDR. Unsupported devices and SDK errors fall back to FSR 3.1 with a logged reason. XeSS Frame Generation and NVIDIA Dynamic MFG are not available here: their current public integrations require D3D12. Fixed NVIDIA FG/MFG and analytical FSR FG remain available. FG presets A/B and AMD ML FG are still pending.

Infinite Stamina now covers the ordinary absolute setter, animation/attack consumption and the other verified decrease guards. Blood Echoes multipliers now cover both normal reward paths, including the actual balance and lifetime total. Costs and purchases keep their original behavior. No Fall Damage is added for normal falls; death volumes and scripted deaths still apply. All cheats start off, can change during play, and require matching 1.09 instructions. A conflicting patch disables the affected feature rather than installing only part of it.

I added the opt-in **Developer profiling and crash diagnostics** option in General → Diagnostics to investigate the firing crash and other failures. It keeps a separate folder for each run under the saves folder's `diagnostics` directory, with timestamped output, CPU/GPU statistics, settings and the exit code. Fatal Windows faults also try to save a minidump and report registers, module/guest addresses and the active cheats. Normal runs are retained as well. I left it off by default because it can affect performance. The firing crash remains open; adding diagnostics does not fix it.

`Bloodborne.exe`, `bin/bb-probe.exe` and the supplied test components are rebuilt. Tests exercise actual Tcl variable traces and Dear ImGui controls, cap behavior, the NVIDIA counter/Reflex report handling, settings persistence, focus pause/resume, and the Windows-compiled cheat object. With the private 1.09 image, the tests also execute the original stamina setters and reward stores; no game code or assets are included in the package. Vulkan fixtures check real FSR interpolation, SDR/HDR conversion and the production XeSS color shader. The XeSS API adapter is checked separately with injected contract responses, without shipping a fake runtime.

Gameplay coverage on TatsunaKyo’s Windows 11 / RTX PC and the open shooting-crash issue are documented in [Testing and known issues](../testing.md). The package includes verification logs and hashes of the actual executables.

Extract the complete ZIP and launch `Bloodborne.exe`. Keep your existing saves, mods and configuration. For the shooting crash, enable developer diagnostics before playing and keep the session folder if it happens again.

Revision by TatsunaKyo, based on Supermedo's Windows port. The original port, shadPS4, community patch authors, AMD/FSR-Vulkan, NVIDIA, Intel and Dear ImGui retain their credits and licenses.
