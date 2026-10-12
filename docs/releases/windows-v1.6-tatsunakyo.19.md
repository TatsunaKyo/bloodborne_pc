<!-- crowned-workshop-navigation -->
> Historical document. [The Crowned Workshop current guides](../index.md) · [Current reports](../known-issues.md). This page retains its original context and credits.

# Bloodborne: The Crowned Workshop — Revision 19 preview

I finally have a more specific lead for the Hunter's Dream flashing. On my Windows 11 / RTX 5070 Ti, it appears with NVIDIA FG enabled and disappears when I turn FG off. My Revision 18 capture contains eight matching frames before and after DLSS. Those images look normal, but some trees receive object-motion vectors exceeding 2,400 input pixels.

I corrected the foliage history matching. This shader draws lists of trees that share the same mesh; culling can change the list without changing the vertex/index buffers. I now include the ordered world transforms in that history key, so one tree batch cannot silently reuse another batch's positions. Stable batches still keep their wind motion, and character/weapon motion remains available.

I also preserve scene depth at the point where reconstruction reads it. The game's later interface passes can reuse that depth buffer before FG's presentation snapshot is made. The copy stays on the GPU, and its lifetime follows the frame owners when resolution changes.

I rebuilt **Bloodborne.exe** and the native Windows components. The regression reproduces the old mesh-only match and checks 120 replaced/reordered batch cases. A second check executes the production depth-copy methods with recorded Vulkan commands for D32, D32+stencil and R32, including a later UI overwrite, reuse, resizing and failed allocation. Address/undefined-behavior checks pass; this recording harness does not execute NVIDIA FG itself.

This is a preview for the same-view gameplay comparison. I still need to confirm the visible result on my PC before closing the flashing report. Please keep the existing HDR, preset and FPS settings for that comparison. The F8 capture and all earlier launcher, menu, upscaling, FG, overlay and cheat features remain available; the shooting, running-stamina and Echoes reports stay open.

The full package includes its SHA256 checksum, source changes, build scripts and verification records. Extract it into a separate folder and select your existing game/saves folders in the launcher.

Maintained by TatsunaKyo, based on Super Medo's native Windows port and bbport/shadPS4. Original and vendor credits/licenses remain included.
