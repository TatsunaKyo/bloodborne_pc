# Bloodborne for Windows v1.6 — TatsunaKyo revision 10

In this revision I worked on temporal stability and on reducing some unnecessary renderer work. I wanted the upscalers and Frame Generation to handle abrupt camera changes more cleanly, and to avoid repeating checks that did not need to happen on every frame.

## What's new in Revision 10

I added a shared history reset for teleports, sudden camera turns, abrupt FOV changes and returning from loading screens. DLSS, FSR, XeSS, TAA and FG now receive the same reset, so they can start from the new scene instead of carrying the previous one into it. Normal movement and gradual zoom still keep their history.

I also removed repeated camera checks, cached unchanged mip-bias calculations, and reduced redundant image barriers. Mesh verification is now spread across frames instead of arriving in one periodic burst. I've done this optimization work to reduce avoidable overhead, but I can't guarantee an FPS increase on other configurations yet. Testing and feedback from other users are very welcome.

I refreshed the project guide as well, so the README explains what I added and where to find each option.

## What this package includes

These are the features available in Revision 10, including the work from the earlier revisions:

- **Upscaling choices:** DLSS, FSR 3.1, FSR 4, XeSS Super Resolution 3.0.2 and native-resolution TAA. I added XeSS for supported Intel and other GPUs, and exposed DLSS presets E/F, J/K and M/L separately from Quality/Balanced/Performance. You can change the preset in the launcher or while playing.
- **Frame Generation and Reflex:** analytical FSR FG x2 and NVIDIA DLSS FG/MFG, with fixed x2–x6 choices depending on the GPU and driver. Both FG paths support SDR and HDR10. I kept Reflex available independently, so you can use it without FG. NVIDIA's integration uses Streamline 2.14.1 and the production DLSS-G 310.9.1 runtime.
- **Exact FPS control:** 75 FPS is available between 60 and 90, and both caps have editable number fields. The ordinary cap limits real game frames; the optional FG cap limits total output. For example, a 130 output cap at x2 gives a 65 real-frame ceiling.
- **A cleaner Play page:** FG is available directly on Play. The DLSS preset row appears only with DLSS selected, and the NVIDIA multiplier has its own row above Output. Customize overlay… takes you to the detailed overlay settings.
- **A smaller, optional overlay:** keep the original basic readout, disable it entirely, or add the DLSS preset letter, input/output resolution, active FG mode and Reflex PC latency. The extra information stays on the same line. NVIDIA FPS uses the SDK's actual presentation count, so selecting a multiplier alone does not inflate the readout.
- **Borderless and background options:** choose Windowed, Borderless fullscreen or Fullscreen, and decide whether the game keeps running, pauses game/rendering, or uses a 30/60 FPS background limit when you switch windows. Cooperative pause keeps window events responsive so you can return to the game.
- **English in-game settings:** Insert or L3+R3 opens the English/Russian menu. I corrected the checkbox handling and keep settings shared with the launcher.
- **Optional cheats and diagnostics:** damage, incoming-damage reduction, Echoes and movement multipliers, infinite stamina, consumables/ammunition kept and no fall damage sit alongside the original cheats. Revision 9 extended the stamina guards to continuous running. The developer diagnostics option is off by default and can keep session logs and crash details when needed.

## Testing and remaining work

I test the revisions on my Windows 11 PC with an RTX 5070 Ti. I rebuilt the launcher and native components, and the camera-history, controls, settings, hook and package checks passed. If you try this build on another GPU or configuration, please send your settings and results; that helps me improve compatibility and performance beyond my own PC.

Uneven frame pacing and the crash reported while firing with several cheats enabled remain on my list. The inherited character-creation preview and some AMD world-loading issues are also still open. The game HUD can show FG interpolation artifacts. Dynamic MFG, XeSS FG, AMD ML FG and FG model presets A/B are future work. Current checks and details are in [Testing and known issues](https://github.com/TatsunaKyo/bloodborne_pc/blob/windows/docs/testing.md).

## Installing

Download **Bloodborne-Windows-v1.6-TatsunaKyo-Revision-10.zip**, extract the complete package into a new folder and open **Bloodborne.exe**. Choose your own game folder and keep your existing saves, mods and preferences. Use the whole package, including bin and _internal, when updating.

**No game files are included. You need your own decrypted Bloodborne CUSA03173 1.09 dump.**

Source commit: `f84ca08107e77ac7441124835cbb1a38cd386aed`

ZIP SHA-256: `7f334a030bfb20a4a6a716d0913fef459c9ffc4f9654e8935e7e4eba3b3df06d`

Revision maintained by TatsunaKyo, based on Supermedo's Windows port, deadinside28's bbport and the shadPS4 renderer. Full project, patch and runtime credits remain in the [README](https://github.com/TatsunaKyo/bloodborne_pc#credits), and their licenses are included with the package.
