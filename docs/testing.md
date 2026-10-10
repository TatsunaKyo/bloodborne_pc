# Testing and known issues

Gameplay testing for this fork is carried out by TatsunaKyo on **Windows 11 with an NVIDIA GeForce RTX 5070 Ti**. Revisions are tested and corrected through that setup. The earlier reports of broken controls, continuous stamina drain, an incorrect FG FPS readout and a crash while firing came from those gameplay tests. They are useful regression reports, not evidence that the project has never been played.

That establishes coverage on one Windows/RTX configuration. It does not establish AMD or Intel gameplay coverage, every monitor/driver combination, or a complete play-through. Newly rebuilt changes should be checked against the same gameplay cases before marking those particular issues resolved.

## Automated coverage

- Launcher preferences, shared in-game settings, update-channel selection and controls extracted from the compiled Windows launcher.
- Actual Tk geometry for the Play page, including English/Russian, three window sizes and 100/150/200% scaling.
- ImGui mouse, keyboard/controller activation, settings round trips and compact overlay layout.
- Native and Windows-compiled cheat hooks, player/NPC selection, disabled paths, register preservation, missing player/world, and original 1.09 instruction signatures from a private local image. Private game bytes are not distributed.
- Camera history through smooth motion, abrupt cuts, loading gaps, invalid inputs and recovery. Object-history allocations are preserved even if a cut is detected after a draw has reserved positions.
- Index-cache verification intervals, stale topology and the distribution of verification work across frames.
- GPU fixtures for motion, color conversion and the analytical FSR FI/OF pipeline, including SDR/HDR10 and synchronization validation. Packaged logs state which revision produced each run.
- Windows compilation/linking, runtime hashes, DLL import/export closure and reconstruction of the source tree from the included patch.

Automated fixtures and gameplay reports answer different questions. Test logs record the actual execution environment and results; gameplay coverage is attributed to TatsunaKyo's Windows PC. A synthetic workload reduction is not presented as a measured gameplay FPS increase.

## Open issues and checks for the current build

- **Crash while firing with damage/reduction and no-consume enabled:** still under investigation. Enable General → Diagnostics → Developer profiling and crash diagnostics for a session log and crash dump when available.
- **Infinite stamina during continuous running:** revision 9 added continuous movement and direct/script guards after attack stamina was working. The hook tests execute 50 consecutive drain updates; the remaining check is sustained running through the affected gameplay states on the current build.
- **FG HUD artifacts:** the game's HUD remains in interpolation input. Moving text can distort. Proper HUDless color and UI-alpha separation is follow-up work.
- **Temporal transitions:** revision 10's new camera resets pass the production-history tests. Compare respawn, teleport, loading and fast normal camera movement in gameplay before considering the visual change confirmed on the main test PC.
- **Hardware coverage:** broader NVIDIA, AMD and Intel results are welcome, including HDR, Alt-Tab and frame pacing. Unsupported SDK/hardware choices should fall back or display an explanation.

Dynamic NVIDIA MFG, XeSS FG, AMD ML FG and FG presets A/B are tracked separately in [the roadmap](tatsunakyo-next.md). They are not selectable features in this package.

Maintained by TatsunaKyo. Upstream and vendor credits are preserved.
