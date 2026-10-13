# Bloodborne: The Crowned Workshop — Revision 26

I went back through the presentation and integration code after Revision 25. I found a few things worth fixing before adding more features: the window/HDR recovery lock order, an unsynchronized GPU drain, invalid numeric settings reaching image tuning, and downloaded updates being started without the package checks used for publication.

## Window, HDR and presentation recovery

NVIDIA input ownership is retired before the client queue is locked for the swapchain's GPU drain. This keeps recovery in the same lock order as ordinary presentation and stops concurrent submissions during that drain. HDR changes also avoid waiting for the whole device twice. Recreated swapchains reset their acquisition slot, including when the driver returns fewer images. I kept the depth preservation, foliage history and NVIDIA input fences that resolved the earlier flashing.

The production recovery fixture reproduces both problems in Revision 25 and checks the corrected paths against competing queue work. Ordinary frame pacing retains Revision 25's narrower presentation lock; neither FPS cap nor the FG scheduling mode has been changed.

## Verified launcher updates

The launcher now checks the downloaded SHA-256 and the same build/binary/runtime identity used by release preparation before extracting or starting the new launcher. It rejects unsafe Windows paths, duplicates, malformed metadata and incomplete packages. Separate temporary folders prevent two launchers from deleting each other's downloads. A rejected candidate leaves the existing launcher open. Installation also stops if waiting for the previous launcher times out or fails.

The README revision badge now follows the launcher version, with a CI check to catch stale numbers. Its link opens the current build's notes; Download latest still opens the latest published release.

## Review and documentation

I added twelve existing CPU/provider fixtures to portable CI and kept the actual launcher/menu layout checks. Nonfinite sharpening/reactive values from an edited INI are bounded before reaching the renderer. I refreshed the current guides and report page while keeping my introduction, banner, feature art and upstream credits.

My gameplay setup remains Windows 11 with an RTX 5070 Ti. I welcome comparisons from other configurations, especially FG/HDR, Radeon Anti-Lag 2 and Intel XeSS. The [review](../code-review-2026-10-13.md) explains the corrections and what still needs work; [current reports](../known-issues.md) keeps the gameplay evidence separate.

## Installation

Extract the complete ZIP into a new folder and select your existing game and saves locations in Game & files. Keep your Bloodborne 1.09 files, saves, settings and mods. Upload the complete ZIP and its matching `.zip.sha256` when publishing this revision.
