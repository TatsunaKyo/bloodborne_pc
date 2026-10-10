# Live cheats

The TatsunaKyo revision adds player damage, enemy damage reduction, Blood Echoes and movement multipliers, infinite stamina, and consumables that stay in the inventory after use. All six are off by default. Choose them in the launcher's Cheats page or change them while playing from Insert / L3+R3. The shared menu preferences survive the launcher rewriting its graphics settings.

| Choice | Values | Behavior |
| --- | --- | --- |
| Player damage | Off, x2, x4, x8, x16 | Multiplies the final damage of player hits against other actors. |
| Reduce enemy damage | Off, x2, x4, x8, x16 | Divides damage received from other actors by the selected factor. Defense stats, self damage, fall damage and ordinary HP setters are unchanged. A positive hit still does at least 1 damage. |
| Blood Echoes gained | Off, x2, x4, x8, x16 | Multiplies positive awards, rather than the current balance. Negative costs are unchanged and the game's 999,999,999 ceiling is respected. |
| Movement speed | Off, x1.5, x2, x4, x8, x16 | Scales the local player's movement factor at the point where it is read. NPC motion and the stored movement factor are unchanged. |
| Infinite stamina | Off, On | Uses the game's no-consumption branches for player actions and guard damage. Regeneration, maximum stamina and NPC stamina are unchanged. |
| Consumables are not reduced on use | Off, On | Uses the item and ammunition use paths. You must own the item. Buying, selling, dropping, transfers and inventory limits keep their normal behavior. |

These hooks require a matching Bloodborne 1.09 executable. At startup the loader checks the app version, the game's player-identification binding and every affected instruction before modifying code. A mismatched instruction disables its entire feature, including the other hooks belonging to it. Unsupported controls are disabled in the in-game menu and the reason is logged. This also avoids combining a half-installed cheat with another patch that changed the same instructions.

The generated trampolines preserve general registers, flags, x87/MXCSR state, every YMM lane and the System V red zone. When a feature is off, its trampoline checks one atomic mask and executes the original instruction without calling the host or the game's player-identification method. Enabled features identify the local player through the game's own virtual method.

The regression test executes the real generated trampolines against a synthetic game image and checks every multiplier, player/NPC selection, healing, self damage, environment damage, negative Echoes deltas, overflow, state preservation and conflicting patches. The menu tests click each new control and reload its saved setting. Instruction signatures were also checked against the supplied 1.09 image. These checks do not replace a gameplay test on Windows; please back up your save before testing extreme values, particularly movement speed.

On an x86-64 Linux host, run `gcc -std=c11 -O2 -Wall -Wextra -Werror tests/test_cheats.c tests/test_cheats_fixture.S -lm -o /tmp/bb-cheats-test && /tmp/bb-cheats-test`. No game executable is needed. An optional path to a privately prepared 1.09 memory image checks instruction signatures as well; do not distribute that image.

Revision by TatsunaKyo. The original port, shadPS4, Dear ImGui and the existing community patches retain their own credits and licenses.
