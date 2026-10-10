# Bloodborne Windows v1.6 — TatsunaKyo revision 5

This revision adds the live cheats requested for this fork. Player damage, enemy damage reduction and Blood Echoes support x2, x4, x8 and x16. Movement also offers x1.5. Infinite stamina and keeping consumables after use are separate switches. Everything is off by default and can be chosen in the launcher or changed from the in-game menu.

Damage reduction divides the damage received instead of changing the defense stat. Blood Echoes multiply positive awards, not the balance already in your save. Consumables include ammunition; buying, selling, dropping and transfers keep the game's normal behavior, and enabling the option does not fill your inventory. Movement and stamina changes apply to the local player.

The loader checks version 1.09 and the relevant instructions before installing each group of hooks. A mismatch or conflicting patch disables that feature instead of applying only part of it. The tests execute the actual generated hooks, preserve CPU state, exercise every multiplier and click the new menu controls in English and Russian. The Windows renderer and launcher are rebuilt from the revision's sources.

The previous revision's in-game control fix, cooperative background pause, 75 FPS limit, conditional DLSS preset dropdown and Vulkan image-view reuse are included. Gameplay coverage is documented in [Testing and known issues](../testing.md). Back up your save before trying the higher movement values. Frame Generation is still being integrated and is not included in this build.

Extract the complete archive to a new folder. Start its `Bloodborne.exe`, point the launcher at your own game folder and keep the ZIP's `bin` and `_internal` folders together. The game executable and game assets are not included.

Revision by TatsunaKyo. Credits for Supermedo's port, shadPS4, FSR-Vulkan, NVIDIA NGX, Dear ImGui and the existing community patches are preserved. Their licenses remain with the package.
