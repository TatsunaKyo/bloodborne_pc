# Testing and known issues

I test this fork on my **Windows 11 PC with an NVIDIA GeForce RTX 5070 Ti** and use those gameplay results to correct each revision. The broken controls, continuous stamina drain, incorrect FG FPS readout and firing crash were problems I encountered during those tests. I keep them here so I can check the same cases again after a fix.

That is my main test configuration. I do not currently own an Intel GPU, and AMD/Intel gameplay coverage, other monitor/driver combinations and a complete play-through need separate results. I check newly rebuilt changes against the reported cases before marking those particular issues resolved.

## Automated coverage

- Launcher preferences, shared in-game settings, update-channel selection and controls extracted from the compiled Windows launcher.
- Actual Tk geometry for the Play page, including English/Russian, three window sizes and 100/150/200% scaling.
- ImGui mouse, keyboard/controller activation, settings round trips and compact overlay layout.
- Native and Windows-compiled cheat hooks, player/NPC selection, disabled paths, register preservation, missing player/world, and original 1.09 instruction signatures from a private local image. Private game bytes are not distributed.
- Camera history through smooth motion, abrupt cuts, loading gaps, invalid inputs and recovery. Object-history allocations are preserved even if a cut is detected after a draw has reserved positions.
- Index-cache verification intervals, stale topology and the distribution of verification work across frames.
- GPU fixtures for motion, color conversion and the analytical FSR FI/OF pipeline, including SDR/HDR10 and synchronization validation. Packaged logs state which revision produced each run.
- Windows compilation/linking, runtime hashes, DLL import/export closure and reconstruction of the source tree from the included patch.

I use automated fixtures to check settings, hooks, resource contracts and package integrity, alongside gameplay on my Windows PC. The logs state where each check ran and what passed. When a fixture shows less renderer work, I report that workload result; I only call it a gameplay FPS gain when there is a gameplay measurement.

## Open issues and checks for the current build

- **Crash while firing with damage/reduction and no-consume enabled:** still under investigation. Enable General → Diagnostics → Developer profiling and crash diagnostics for a session log and crash dump when available.
- **Uneven frame pacing, including NVIDIA FG/MFG:** still reported. The scheduling audit identifies an overdue-deadline catch-up case and separate FSR/NVIDIA timing work; it does not establish a Windows display-pacing fix. Compare displayed intervals and latency alongside real/rendered FPS. See [the development roadmap](tatsunakyo-next.md#p0-frame-pacing-and-latency).
- **Character creation preview:** the upstream Windows port documents an empty preview, with the character appearing correctly after creation. No dedicated fix was found in Revision 10. Existing FaceGen readbacks are not evidence that the preview issue is resolved.
- **World loading on some AMD GPUs:** an inherited upstream issue remains open. Native-port reports distinguish object-motion device loss, texture memory pressure and other failure paths. Some compatibility measures already exist in this code, but there is no basis to mark all AMD loading crashes fixed. See [the compatibility work](tatsunakyo-next.md#shooting-and-amd-compatibility).
- **Infinite stamina during continuous running:** revision 9 added continuous movement and direct/script guards after attack stamina was working. The hook tests execute 50 consecutive drain updates; the remaining check is sustained running through the affected gameplay states on the current build.
- **FG HUD artifacts:** the game's HUD remains in interpolation input. Moving text can distort. Proper HUDless color and UI-alpha separation is follow-up work.
- **Temporal transitions:** revision 10's new camera resets pass the production-history tests. Compare respawn, teleport, loading and fast normal camera movement in gameplay before considering the visual change confirmed on the main test PC.
- **Hardware coverage:** broader NVIDIA, AMD and Intel results are welcome, including HDR, Alt-Tab and frame pacing. Unsupported SDK/hardware choices should fall back or display an explanation.

The integrated Save Manager and proposed new cheats are also planned, alongside Dynamic NVIDIA MFG, XeSS FG, AMD ML FG and FG presets A/B. [The roadmap](tatsunakyo-next.md) distinguishes existing code, partial implementations and new work. These proposed additions are not selectable features in this package.

Maintained by TatsunaKyo. Upstream and vendor credits are preserved.
