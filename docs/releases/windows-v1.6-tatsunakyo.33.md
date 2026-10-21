> Historical/upstream record: statements and test results below describe their original revision or environment. [Current guides](../index.md) · [Current reports](../known-issues.md) · [Published releases](../releases/index.md)

I have gone back through the existing flashing-assets report and the NVIDIA frame handoff. I reproduced two errors in Revision 32: a queued frame can keep a pointer to a Streamline token after the SDK has reassigned that token to a later frame, and a concurrent submission during Reflex sleep can pick up the previous simulation's token.

Streamline 2.14.1 keeps six token slots. I now keep each slot reserved from simulation through its queued flip and Present call. If all six are still in use, the next simulation waits for one to retire instead of overwriting an outstanding frame's identity. This waits on host ownership; it does not add a GPU idle or change the FPS limits. Reflex sleep keeps its own token alive and lets the previous Present progress. Starting the render and assigning its flip now happen together, after the correct simulation is ready.

The regression runs the production handoff methods against the SDK's six-slot allocation behaviour. The unchanged R32 control reproduces both errors. The corrected path checks delayed presentation, retirement, concurrent sleep/render, 120 frames across standalone Reflex and FG modes, cancelled or missing flips, allocation failure, frame-index wrap and background cancellation. The same regression runs on Windows and Linux.

The launcher and native components are rebuilt. I have kept the existing scene-input ownership, HDR, motion-vector safeguards, shader cache, frame pacing, independent real/output FPS limits and background handling. This revision changes NVIDIA frame tracking; it does not roll back the earlier renderer work.

These are two reproduced host-side errors, not confirmation that every flashing artifact has the same cause. The gameplay report remains open until the affected scenes are checked on my Windows 11 / RTX 5070 Ti PC. This is a corrective preview build, rather than another request to record a diagnostic session.

Extract the ordinary game ZIP into a new folder and keep your existing game, saves, mods and settings locations. The Developer ZIP is optional for playing. If publishing this preview, upload both ZIPs and their matching `.zip.sha256` files before publishing the prepared release.
