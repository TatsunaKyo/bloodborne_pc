# Cheats

The TatsunaKyo revision adds player damage, enemy damage reduction, Blood Echoes and movement multipliers, infinite stamina, consumables kept after use and No Fall Damage. All seven start off. Choose them in the launcher's Cheats page or change them while playing from Insert / L3+R3. The shared menu preferences survive the launcher rewriting its graphics settings.

| Choice | Values | Behavior |
| --- | --- | --- |
| Player damage | Off, x2, x4, x8, x16 | Multiplies the final damage of player hits against other actors. |
| Reduce enemy damage | Off, x2, x4, x8, x16 | Divides damage received from other actors by the selected factor. Defense stats, self damage, fall damage and ordinary HP setters are unchanged. A positive hit still does at least 1 damage. |
| Blood Echoes gained | Off, x2, x4, x8, x16 | Multiplies positive awards, rather than the current balance. Negative costs are unchanged and the game's 999,999,999 ceiling is respected. |
| No fall damage | Off, On | Skips the normal fall-damage path for the player. Death volumes and scripted deaths still apply. |
| Movement speed | Off, x1.5, x2, x4, x8, x16 | Scales the local player's movement factor at the point where it is read. NPC motion and the stored movement factor are unchanged. |
| Infinite stamina | Off, On | Uses the game's no-consumption branches for player actions, running, guard damage and direct stamina updates. Regeneration, maximum stamina and NPC stamina are unchanged. |
| Consumables are not reduced on use | Off, On | Uses the item and ammunition use paths. You must own the item. Buying, selling, dropping, transfers and inventory limits keep their normal behavior. |

These hooks require a matching Bloodborne 1.09 executable. At startup the loader checks the app version, the game's player-identification binding and every affected instruction before modifying code. A mismatched instruction disables its entire feature, including the other hooks belonging to it. Unsupported controls are disabled in the in-game menu and the reason is logged. This also avoids combining a half-installed cheat with another patch that changed the same instructions.

Revision 6 used a virtual slot inferred from a script wrapper. That slot belongs to a different object type: on a real character it can run an unrelated update. This caused ineffective cheats and could crash after loading a save. Revision 7 replaces that call with the comparison made by the game's actual player check: the actor must equal `WorldChrMan::mainPlayer` at offset `+0x60`. The global pointer is verified against the instruction's RIP-relative target. An absent world or player during loading leaves the original behavior intact. No game virtual function is called.

The generated trampolines preserve general registers, flags, x87/MXCSR state, every YMM lane and the System V red zone. When a feature is off, its trampoline checks one atomic mask and executes the original instruction without calling the host. Runtime multipliers and original startup cheats are now in the same Cheats section; startup patches are marked as requiring a restart.

The regression test executes the real generated trampolines against a synthetic game image and checks every multiplier, player/NPC selection, healing, self damage, environment damage, negative Echoes deltas, overflow, state preservation and conflicting patches. It also executes the actual Windows-compiled runtime object with Windows x64 host-call wrappers, including enabled player-only hooks with no world or no player. The former virtual slot contains trap instructions so an accidental call fails the test. Hook signatures and the RIP-relative player lookup were checked against the privately supplied 1.09 image. ImGui tests click each control and reload its saved setting. Gameplay testing and open regression checks are collected in [Testing and known issues](testing.md), including the main Windows 11 / RTX setup.

On an x86-64 Linux host, compile with `gcc -O2 -mavx -I src tests/test_cheats.c tests/test_cheats_fixture.S -o /tmp/bb-cheats-test` and run `/tmp/bb-cheats-test`. No game executable is needed. An optional path to a privately prepared 1.09 memory image checks instruction signatures as well; do not distribute that image. To test the compiled Windows object, add `-no-pie -DTEST_WINDOWS_OBJECT` and pass the private image path followed by the path to `runtime_cheats.c.obj`. The small COFF fixture loader resolves only the test's explicit Windows ABI imports; it is not a Windows gameplay environment.

Revision 8 adds the missing ordinary stamina setter and animation/attack guards, plus both normal Echoes reward stores. Tests using the privately supplied image execute the complete original stamina setters and reward/balance writes, including player vs NPC behavior, regeneration and negative costs. The test reads those bytes only from the optional local input; they are not redistributed. No Fall Damage uses the player's verified built-in fall-damage guard, without changing gravity or defense stats.

Revision 9 adds the remaining continuous movement, direct character/script and state synchronization guards. Running bypasses the attack setter, which is why the earlier fix did not cover it. The optional private-image test executes 50 consecutive drain updates, the original inline script update and the complete character setter, with the cheat on and off for both player and NPCs. The same tests pass against the Windows-compiled runtime object. The sustained-running gameplay check is tracked on the shared testing page.

For a crash after firing with damage/reduction and no-consume enabled together, turn on General → Diagnostics → Developer profiling and crash diagnostics in the launcher. Each run keeps its own log/settings/exit code folder, and fatal Windows faults try to write a minidump with registers and active cheat values. This is off by default. The reported shooting crash is still under investigation.

Revision by TatsunaKyo. The original port, shadPS4, Dear ImGui and the existing community patches retain their own credits and licenses.
