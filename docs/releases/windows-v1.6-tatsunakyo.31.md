The gameplay comparison still shows duplicated and flashing assets with NVIDIA FG enabled. The input overwrite fixed here was reproduced, but it did not resolve the full report. Revision 32 adds a capture at the actual NVIDIA handoff to continue the investigation.

# Bloodborne: The Crowned Workshop — Revision 31

Revision 30 still flashes with NVIDIA FG. I followed the inputs before they reach Streamline and reproduced a different problem: retaining an image kept its handle alive, but the next scene could still overwrite its contents. In the control test, frame A keeps depth at 0.5 and recording frame B changes A's retained depth to 0.7. The old regression allowed that reuse, so it missed this case.

I now preserve depth and motion together at scene reconstruction. Each completed display buffer carries its own camera and owned input pair; a later buffered scene cannot replace them before an earlier flip is prepared. The handoff is consumed once, so another flip without a new scene keeps the real frame instead of replaying old motion. Native AA follows the same rule.

The input pool reuses storage only after its producer and consumers have retired it. It is bounded to eight pairs and keeps the real frame if every slot is still owned. Motion copies use the required transfer-source usage; partial allocation failures retain any images already referenced by recorded commands. This does not add a normal-path GPU idle wait or change the FPS limiters.

The regression runs the production copy, pool and display-selection methods. It reproduces the Revision 30 overwrite and checks 18 combinations of depth format, dimensions and SDR/HDR display format, including a delayed consumer, camera/color association, repeated flips, invalid scenes and pool pressure. I also corrected the existing depth-copy oracle and extended the Vulkan fixture to check both motion channels and depth after a later scene in SDR/HDR.

The launcher and native components are rebuilt. Actor/weapon motion, HDR, the earlier synchronization and SDK ownership fences, frame pacing, independent real/output FPS limits and the focus correction remain included. Shader cache version stays at 10 because this revision changes input ownership and selection, not the emitted game shaders.

I still need the same gameplay comparison at the Tomb of Oedon and Hunter's Dream on my Windows 11 / RTX 5070 Ti PC. I have reproduced and corrected the input overwrite; the scene's flashing report remains open until that comparison confirms the result.

Extract the ordinary game ZIP into a new folder and keep your existing game, saves, mods and settings locations. The Developer ZIP is optional for playing. Upload both ZIPs and their matching `.zip.sha256` files before publishing the prepared release.
