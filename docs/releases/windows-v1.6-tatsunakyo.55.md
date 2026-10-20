# Bloodborne: The Crowned Workshop — TatsunaKyo R55

R55 integrates Supermedo Windows 1.9.2 and adapts reviewed renderer improvements while preserving this fork's DLSS/FG, XeSS, FSR, Anti-Lag, overlay, Save Manager and startup timing features.

- Cache motion-vector targets by size to avoid repeated image recreation and GPU drains when rendering passes change dimensions.
- Prioritize a pipeline needed by the current draw within the existing bounded compiler queue. Keep complete draws and failure fallback.
- Retain valid texture hashes across GPU refreshes, invalidate them on CPU writes/downloads, and keep digests identical across worker modes.
- Reduce retained device-local staging and size depth/color copy intermediates to the actual backing images.
- Integrate upstream VRAM recovery, FSR bridge allocation retirement, fault reporting, input combinations, three binding slots, mouse improvements, prompts, FOV and background mute.
- Keep the verified TatsunaKyo update channel, including the new Other Versions chooser. Migrate old Readbacks Off settings to Relaxed to preserve geometry updates.

Extract the complete ZIP into a new folder and select your own version 1.09 game files. Keep saves, settings, mods and shader caches. Start `Bloodborne.exe`. RTX Encore remains an explicit experimental option; native RTX 40/50 users retain the stock library routes.

One ZIP and its matching SHA256 contain the runtime, required DLLs/licenses, source patch and compact build recovery. The archive is checked for source/patch identity and dependencies, and its own compiled launcher is used for startup replay.

The production resource test reproduces 3,000 allocations/2,999 drains in R54 versus three allocations/zero drains across 1,000 three-size frames in R55. This verifies the removed resource churn; it is not a game benchmark. Windows/NVIDIA Bloodborne gameplay was not run locally. The cemetery hitch, displayed-frame jitter and remaining reconstruction artifacts are not declared resolved by this release.

See `docs/investigations/2026-10-20-upstream-integration.md` and `source/verification/summary.json` for integration decisions, evidence and validation limits.
