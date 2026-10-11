# Testing and known issues

I test this fork on my **Windows 11 PC with an NVIDIA GeForce RTX 5070 Ti** and use those gameplay results to correct each revision. The broken controls, continuous stamina drain, incorrect FG FPS readout and firing crash were problems I encountered during those tests. I keep them here so I can check the same cases again after a fix.

That is my main test configuration. I do not currently own an Intel GPU, and AMD/Intel gameplay coverage, other monitor/driver combinations and a complete play-through need separate results. I check newly rebuilt changes against the reported cases before marking those particular issues resolved.

## Automated coverage

- Launcher preferences, shared in-game settings, update-channel selection and controls extracted from the compiled Windows launcher.
- Actual Tk geometry for the Play page, including English/Russian, three window sizes and 100/125/150/175/200% scaling for the current launcher, including the longer project identity, workshop artwork/live title, keyboard navigation and minimum window size.
- ImGui mouse, keyboard/controller activation, settings round trips and compact overlay layout.
- Native and Windows-compiled cheat hooks, player/NPC selection, disabled paths, register preservation, missing player/world, and original 1.09 instruction signatures from a private local image. Private game bytes are not distributed.
- Camera history through smooth motion, abrupt cuts, loading gaps, invalid inputs and recovery. Object-history allocations are preserved even if a cut is detected after a draw has reserved positions.
- Revision 13 checks submitted camera snapshots, immediate index-content invalidation and reused allocations with unchanged bounds; unchanged meshes keep their cached range scans.
- GPU fixtures for motion, color conversion and the analytical FSR FI/OF pipeline, including SDR/HDR10 and synchronization validation. Packaged logs state which revision produced each run.
- Windows compilation/linking, runtime hashes, DLL import/export closure and reconstruction of the source tree from the included patch.
- Pacing checks use the production helper at 30/60/65/75/90/120 FPS, with queued frames, 50 ms and five-second stalls, slow rendering, uncapped mode, changing caps and timer waits. Revision 14 adds 10,000-frame jitter checks per cap, reproducing the repeated timer delays from my Windows logs without cumulative FPS loss. Background tests cover pause/refocus and stopping while paused.
- Revision 13 checks shared live real-FPS controls, fixed-timing restrictions, independent FG-output limits, preference migration and unsupported Anti-Lag controls. The production AMD adapter is exercised with captured Vulkan calls, including matching input/present IDs and presentation progress during an input wait.

I check settings, hooks, resource handling and package integrity with automated tests, alongside gameplay on my Windows PC. The logs retain the environment and results of those checks. My own setup only covers one Windows/RTX configuration, so reports from other PCs are welcome, including when an optimization makes little difference or causes a regression.

- ConstRam overwrite ordering: production command branch exercised with direct, recorder and worker copies, both draw-pipeline states and 512 source replacements per path.

## Open issues and checks for the current build

- **Crash while firing with damage/reduction and no-consume enabled:** still under investigation. Enable Advanced → Diagnostics → Developer profiling and crash diagnostics for a session log and crash dump when available.
- **Uneven frame pacing, including NVIDIA FG/MFG:** still reported. The Revision 13 logs showed about 73.4 FPS at a 75 limit and 59 real FPS with an x2 FG output cap of 120. Revision 14 corrects the timer drift responsible for this consistent shortfall; other hitches remain a separate check. Revision 11 corrects the burst of queued submissions after a stall and reuses the Windows high-resolution timer. I am keeping the wider issue open while comparing the two builds. FSR/NVIDIA display timing also needs attention. I want to compare displayed intervals and latency alongside real/rendered FPS. See [the development roadmap](tatsunakyo-next.md#p1--frame-pacing-cache-and-temporal-quality).
- **Character creation preview:** the upstream Windows port documents an empty preview, with the character appearing correctly after creation. No dedicated fix was found in Revision 10. Existing FaceGen readbacks are not evidence that the preview issue is resolved.
- **World loading on some AMD GPUs:** an inherited upstream issue remains open. Native-port reports distinguish object-motion device loss, texture memory pressure and other failure paths. Some compatibility measures already exist in this code, but there is no basis to mark all AMD loading crashes fixed. See [the compatibility work](tatsunakyo-next.md#amd-loading-and-character-creation).
- **Infinite stamina during continuous running:** revision 9 added continuous movement and direct/script guards after attack stamina was working. The hook tests execute 50 consecutive drain updates; the remaining check is sustained running through the affected gameplay states on the current build.
- **FG HUD artifacts:** the game's HUD remains in interpolation input. Moving text can distort. Proper HUDless color and UI-alpha separation is follow-up work.
- **Temporal transitions:** revision 10's new camera resets pass the production-history tests. Compare respawn, teleport, loading and fast normal camera movement in gameplay before considering the visual change confirmed on the main test PC.
- **Flashing assets:** still present in my Revision 14 gameplay tests. Revision 15 completes deferred vertex/index reads before ConstRam replaces their guest source. The regression compiles the actual command branch: the previous behavior corrupts 2,048 of 3,072 snapshots, while the corrected branch preserves them. The previous camera/index/vector and repeated-instance safeguards remain. The scene report stays open pending this build's gameplay comparison with FG on/off and the same effects/settings.
- **AMD Anti-Lag 2:** the integration and its capability/input/presentation/lifetime checks are included in Revision 13. I need Radeon gameplay results for the driver path; an RTX run cannot cover it. It does not provide an AMD latency number for the overlay.
- **XeSS quality choices:** The launcher checks cover the conditional quality rows and 84 real popup selections and actual ImGui selection/save checks for all seven modes. The SDK-contract fixture verifies seven quality modes at four output sizes with SDR/HDR initialization. Startup/live scene sizing, preference migration and frozen-resolution behavior pass. I would especially appreciate gameplay comparisons of the seven modes on Intel hardware; I do not own an Intel GPU.
- **Hardware coverage:** broader NVIDIA, AMD and Intel results are welcome, including HDR, Alt-Tab and frame pacing. Unsupported SDK/hardware choices should fall back or display an explanation.

The integrated Save Manager and proposed new cheats are also planned, alongside Dynamic NVIDIA MFG, XeSS FG, AMD ML FG and FG presets A/B. [The roadmap](tatsunakyo-next.md) distinguishes existing code, partial implementations and new work. These proposed additions are not selectable features in this package.

Maintained by TatsunaKyo. Upstream and vendor credits are preserved.
