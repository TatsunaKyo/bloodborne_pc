# Bloodborne: The Crowned Workshop — Revision 29

I rolled back the motion-history change from Revision 28 after flashing geometry returned during gameplay at the Tomb of Oedon. The camera-motion shader and the vertex/fragment motion emitter now use the same code as Revision 27. I also changed the shader-cache version, so shaders compiled by Revision 28 are discarded automatically. The existing depth checks, FG input ownership and frame-pacing work stay in place.

I fixed background limiting when the game starts out of focus. The window thread now checks the actual foreground window after processing events, including when an activation event is missing or arrives late. Returning to the game restores the configured limits in one polling cycle: for example, 65 real FPS and 130 total FPS with x2 FG. Pause, 30 FPS and 60 FPS background modes use the same corrected focus state.

The regression test runs the production event pump and reproduces the failure with the unchanged Revision 28 code. It checks 25 scenarios, including missing and stale events, minimized windows, restoration of both caps, the FG/Reflex policy and the pause gate. The camera-motion test runs the production shader body and checks that an obsolete negative history marker cannot generate the off-screen vectors introduced by Revision 28.

The launcher and native components are rebuilt. I will verify the visual result on my Windows 11 / RTX 5070 Ti PC; the automated tests cover the rollback and focus logic but cannot reproduce the boss area here. This hotfix adds no new rendering experiments.

Extract the ordinary game ZIP into a new folder and keep your existing game, saves, mods and settings locations. The Developer ZIP remains optional for playing. Upload both ZIPs and both matching `.zip.sha256` files before publishing the prepared release.
