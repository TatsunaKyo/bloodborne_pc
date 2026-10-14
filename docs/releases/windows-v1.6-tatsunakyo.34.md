# Revision 34 preview — object motion history

Revision 33 still showed extra coffins flashing in the cemetery on my Windows 11 / RTX 5070 Ti PC with NVIDIA FG. I have kept that report open and gone back to the motion guides used by interpolation.

I found that objects sharing a mesh could also share its previous vertex positions even when they used different pose bindings. The renderer now includes those bindings in the history identity. It checks every bound pose instead of stopping at the first character palette, while allowing the pose itself to animate. Moving the same constants through the host ring keeps that identity intact.

Instance batches need an extra check: an instance index is an array slot, and culling can put another object into that slot on the next frame. I now use camera reprojection for batches without a verified object mapping. The existing ordered world-transform checks still retain wind animation where that mapping is known. Single-object actor and weapon history remains enabled.

The regression runs the production binding reader and history code against the unchanged R33 control. R33 reproduces three incorrect matches: another object's pose, a changed later palette and an unidentified instance slot. The corrected path rejects those matches and retains actor/weapon animation, verified world instances and host-ring relocation. These checks run on Windows and Linux.

I have rebuilt the launcher and native components. HDR, frame pacing, Reflex, the separate real/output FPS limits, background handling and the earlier depth/motion ownership corrections remain included. Shader cache version stays at 10 because the shader bodies have not changed.

This preview addresses those incorrect guide matches. I still need to check the affected cemetery in play before calling the flashing report resolved. Extract the game ZIP into a new folder and keep your game, saves, mods and settings locations. The Developer ZIP is optional for playing.
