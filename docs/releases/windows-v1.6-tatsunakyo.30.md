# Bloodborne: The Crowned Workshop — Revision 30

Revision 29 did not eliminate the flashing assets. Turning NVIDIA FG off removes most of the problem, so I checked the frame inputs and their synchronization rather than treating the earlier rollback as a complete fix.

I corrected a submission dependency: the frame-ready semaphore was waited at color attachment output even though presentation reads the frame through earlier transfer and compute work. Every submitted wait now covers those consumers, and the stage array covers all four supported dependencies. The regression executes the production submission function, reproduces the incomplete wait in Revision 29 and checks the corrected path with zero to four waits.

I also went back to the numeric GPU capture from the Hunter's Dream. In three frames, parts of the trees have motion vectors of hundreds or thousands of pixels, while the ordinary motion is around 10–40 pixels. The full-precision depth check alone still accepts those vectors. I added a continuity check for model batches whose world transforms have a verified identity: wind motion remains active, but a large displacement inconsistent with camera motion uses camera reprojection. Actor and weapon motion keeps its original path. This is a safeguard for corrupted world history; it does not establish which draw originally produced the incorrect positions.

The shader cache version increases to 10 so the new confidence marker reaches compiled game shaders. The production motion-kernel tests cover ordinary wind, matching camera motion, bad world displacement, legitimate large actor movement and eight anonymized numerical samples from the capture. The existing FG resource fences, independent FPS limits, frame-pacing work and Revision 29 focus correction remain included.

The launcher and native components are rebuilt. I still need the gameplay comparison at the Tomb of Oedon and Hunter's Dream on my Windows 11 / RTX 5070 Ti PC before calling the flashing resolved. The fixes address reproduced faults; automated tests cannot substitute for that comparison.

Extract the ordinary game ZIP into a new folder and keep your existing game, saves, mods and settings locations. The Developer ZIP is optional for playing. Upload both ZIPs and their matching `.zip.sha256` files before publishing the prepared release.
