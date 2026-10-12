<!-- crowned-workshop-navigation -->
> Historical document. [The Crowned Workshop current guides](../index.md) · [Current reports](../known-issues.md). This page retains its original context and credits.

# Bloodborne Windows v1.6 — TatsunaKyo Revision 12

I added a dedicated XeSS quality menu after finishing the Revision 11 frame-pacing build. This package includes that pacing work too; the earlier builds remain available for comparison.

## What I changed

Selecting XeSS now shows **XeSS quality** on Play, in Graphics and in the in-game menu. The shared DLSS/FSR quality row disappears while XeSS is selected. Switching back restores it with your previous choice, and the DLSS model selector on Play still appears only for DLSS.

| XeSS quality | Output/input ratio per axis | Input at 1920 × 1080 output |
|---|---|---|
| Native AA | ×1.0 | 1920 × 1080 |
| Ultra Quality Plus | ×1.3 | 1476 × 830 |
| Ultra Quality | ×1.5 | 1280 × 720 |
| Quality | ×1.7 | 1130 × 636 |
| Balanced | ×2.0 | 960 × 540 |
| Performance | ×2.3 | 834 × 470 |
| Ultra Performance | ×3.0 | 640 × 360 |

I connected all seven choices to the native renderer and Intel's matching SDK quality modes. The startup resolution patches use the same choice as live rendering. A live quality change resets temporal history; a startup-patched session keeps its current input size and saves the new choice for a restart.

XeSS quality is saved separately in `bbport.menu.ini`. I migrate an older shared setting by its render ratio, preserving its input resolution. The old shared Quality setting, for example, becomes XeSS Ultra Quality. Launcher saves also preserve recent in-game edits to settings you have not changed in the launcher.

The README now compares the quality ratios of DLSS/FSR and XeSS. I want the different names and input sizes to be clear before you pick a mode.

## Checks

I rebuilt both `Bloodborne.exe` and the native renderer in `bin/bb-probe.exe`. The compiled launcher passes **108 layout checks** and **84 actual XeSS popup selections**: all seven entries on Play and Graphics, in English/Russian at 100/150/200% scaling. These checks open the dropdown, select the entries and save them. They also cover conditional labels/help text, switching providers and concurrent in-game preference changes.

The actual ImGui menu selects and saves all seven XeSS modes in both languages. The native SDK-contract checks cover all seven modes at four output sizes in SDR/HDR, plus the existing execution, resource barriers, fallback and context-lifetime checks. Preference migration, environment overrides, even-pixel scene sizing, startup patches and the frozen-resolution restart behavior pass too.

My gameplay setup is Windows 11 with an RTX 5070 Ti. I would particularly appreciate results from Intel GPU owners for the added quality modes. The included logs identify the build-host checks and retained GPU tests from previous revisions, so those earlier results are not presented as new gameplay runs.

## Low-latency follow-up

**AMD Anti-Lag 2** is feasible on this Windows Vulkan renderer: AMD provides a Vulkan SDK integration with Adrenalin 24.9.1 or newer. It is independent of FSR upscaling. I have added the integration work to the roadmap, including supported-device checks and its interaction with the frame limiter and FG.

**Intel XeSS Low Latency (XeLL)** currently requires D3D12 and a flip-model DXGI swapchain. It cannot be connected directly to this Vulkan presentation path. I am keeping it with the separate backend work rather than offering an ineffective option. NVIDIA Reflex remains available independently of DLSS FG as before.

## Installation

Extract the complete Revision 12 ZIP into a separate folder. Keep your saves, mods and settings. `Start-Verified-Launcher.cmd` checks the new launcher hash before opening it. Updating only `Bloodborne.exe` would leave the native renderer and startup scripts on the old version, so use the whole package.

The firing crash with certain cheat combinations, continuous-running stamina, character preview, AMD world loading and the wider frame-pacing comparison remain on [the roadmap](../tatsunakyo-next.md). This XeSS update preserves the existing FG, HDR, overlay, window, cheat and diagnostics paths.

No game files are included. You need your own decrypted Bloodborne CUSA03173 1.09 dump.

Maintained by TatsunaKyo. Original port, shadPS4, community patch and vendor credits and licenses are preserved.
