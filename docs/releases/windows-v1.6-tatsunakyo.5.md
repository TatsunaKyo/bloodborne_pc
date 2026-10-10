# Bloodborne Windows v1.6 — TatsunaKyo revision 5

I added the live cheats I wanted for this fork, with choices in both the launcher and in-game menu. Player damage, enemy damage reduction and Blood Echoes support x2, x4, x8 and x16. Movement also offers x1.5. Infinite stamina and keeping consumables after use are separate switches. I left everything off by default so you can choose which options, if any, you want to use.

For damage reduction, I divide the damage received while preserving the defense stat. Blood Echoes multiply positive awards, not the balance already in your save. Consumables include ammunition; buying, selling, dropping and transfers keep the game's normal behavior, and enabling the option does not fill your inventory. Movement and stamina changes apply to the local player.

I added version 1.09 and instruction checks before installing each group of hooks. A mismatch or conflicting patch disables the complete affected feature. The tests execute the actual generated hooks, preserve CPU state, exercise every multiplier and click the new menu controls in English and Russian. I rebuilt the Windows renderer and launcher from the revision's sources.

I kept the previous revision's in-game control fix, cooperative background pause, 75 FPS limit, conditional DLSS preset dropdown and Vulkan image-view reuse. My gameplay checks are documented in [Testing and known issues](../testing.md), including the later fixes to these initial cheats. Back up your save before trying the higher movement values. Frame Generation was still being integrated at this revision and is not included in this build.

Extract the complete archive to a new folder. Start its `Bloodborne.exe`, point the launcher at your own game folder and keep the ZIP's `bin` and `_internal` folders together. The game executable and game assets are not included.

Revision by TatsunaKyo. Credits for Supermedo's port, shadPS4, FSR-Vulkan, NVIDIA NGX, Dear ImGui and the existing community patches are preserved. Their licenses remain with the package.
