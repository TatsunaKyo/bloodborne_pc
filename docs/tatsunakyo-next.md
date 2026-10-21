# Current work and roadmap

R55 integrates Supermedo Windows 1.9.2 and the reviewed renderer changes since published R40. [Exact integration decisions](investigations/2026-10-20-upstream-integration.md) · [Current reports](known-issues.md) · [Source maintenance](maintenance.md)

## Included already

Save Manager and Support Report are shipped. Input supports three binding slots, combinations, direct mouse camera, reloadable bindings and selectable prompts. FOV defaults to 43°; ultrawide HUD placement and background mute are available. Native Supermedo SDR FG choices coexist with the Workshop HDR-capable routes. These are included features, with further compatibility and usability work still possible.

## Rendering priorities

The repeatable cemetery hitch, 119–121 output/camera unevenness and remaining character/foreground artifacts remain open. Test the affected route with FG both off and on, separate host streaming/retirement from shader compilation and physical display cadence, and retain the exact source/runtime comparison. Controlled resource improvements are not proof of a scene fix.

Keep the existing provider controls, source/startup consistency, saves, stock NVIDIA path and strict fallback behavior while integrating upstream/fork changes. Broader hardware coverage, HUDless FG/UI recomposition, ultrawide cinematic handling and save profiles remain useful next work.

## P2 — proposed cheats

I checked all fourteen proposals against the runtime hooks and existing patches. The table below describes planned additions, rather than features already shipped. Difficulty estimates can change once the exact 1.09 hook and object lifetime are verified.

| Proposed cheat | Existing basis | Intended behavior and main dependency | Estimated work / order |
|---|---|---|---|
| Infinite Weapon Durability | Bloodborne weapon parameters describe durability; no runtime preservation hook here. | Skip normal wear for equipped player weapons. Preserve repair, upgrade, transfer and weapon-specific effects. | Medium; first cheat group after P0 |
| Keep Blood Echoes on Death | Echo award hooks exist, but no death transaction handling. | Preserve the balance through death/respawn without also leaving a collectible copy. Test quit/reload and enemy-held Echoes. | Medium–high; after Save Manager |
| Automatic Echo Recovery | No bloodstain/recovery hook. | Resolve the game's genuine recovery transaction once, including enemy-held Echoes; prevent duplicates and repeated multiplication of recovered funds. | High; after death handling |
| Adjustable HP Regeneration | Never Die exists, but is a different behavior. HP change fields exist in Bloodborne effect definitions. | Configurable HP per second through the normal player health update, with maximum-health bounds. Stop at death/loading; do not resurrect. | Medium; first cheat group |
| Selective Status Immunity | No runtime status controls; Bloodborne effect definitions contain relevant immunity/resistance fields. | Separate slow poison, rapid poison and Frenzy controls. Verify the game's actual mapping and buildup/effect handling; names inherited from other Souls games are insufficient. | Medium; first cheat group |
| Insight Multiplier / no consumption | No corresponding runtime hook; the community cheat database has an Insight balance reference. | Multiply positive gains separately from preserving costs. Preserve normal caps, shops and progression checks. Avoid setting an arbitrary huge balance. | Medium; first cheat group |
| 100% Item Drop Rate | Bloodborne `ItemLotParam` describes weighted outcomes and acquisition flags. No integration here. | Remove the eligible no-drop outcome and retain the table's intended selection and quest/unique-item restrictions. Do not award every alternative in a weighted table. | Medium–high; later economy work |
| Adjustable Rally | No Rally Decay and Disable Rally already exist as startup patches; regain fields exist in Bloodborne definitions. | Separate window duration and recovered-health percentage, preserving the recoverable-health ceiling. Resolve conflicts with the two startup patches. | Medium; extend existing feature |
| Enemy HP Multiplier | No enemy-health scaling hook. Player damage is not equivalent. | Normal/x0.5/x2/x4/x8, applying once at enemy initialization with correct current/max HP. Define boss handling and avoid repeated scaling on updates/reloads. | Medium–high; later gameplay work |
| One-Hit Kill | Player damage hook and a community one-hit-kill reference. No boss/scripted-target eligibility filter here. | Ordinary hostile targets only. Preserve player, allies, mandatory interactions and boss transitions; do not reuse x16 damage as a guarantee. | Medium–high; after damage-hook review |
| Freeze Enemy AI | Enemy Control and stealth already exist; neither freezes AI. | Suspend eligible enemy decisions/movement while preserving world/event updates and a reliable unfreeze path. Handle projectiles, animation and boss scripts explicitly. | High; training tools |
| Infinite Buff Duration | No runtime effect-lifetime hook; effect and animation definitions offer references. | Preserve selected temporary player weapon buffs, with normal removal on expiry conditions such as weapon change/death. Do not freeze every status effect. | Medium–high; after effect lifecycle work |
| Easier firearm parry / Adjustable Parry Window | No runtime parry-window control; Bloodborne animation definitions identify parry-possible states. | One shared leveled control: Off, x2, x4, x8, x16 for the eligible vulnerability window. A narrower x0.5 option can serve difficulty customization. Keep non-parryable attacks excluded. | High; one coherent training feature |
| Increased dodge invulnerability | No runtime dodge-window hook; Bloodborne animation definitions identify invincibility states. | Bounded levels during genuine dodges, restoring normal state afterwards. Use game time, not output/FG frames. Permanent invulnerability is a separate behavior. | High; training tools |


Easier firearm parries and Adjustable Parry Window will share one leveled control: Off/x2/x4/x8/x16, with an optional narrower x0.5 setting for custom difficulty. It must remain bounded by the eligible attack animation and preserve non-parryable attacks. The visceral follow-up window is a different mechanic. Dodge invulnerability must follow game time and genuine dodge states, never generated frames.

All additions belong in the existing Cheats pages. I will follow the current signature/ABI/hook-group contract, keep a cheap disabled path and reject overlapping patches. Progression/economy changes need duplicate-award and save round-trip tests. Keep-Echoes and automatic-recovery policies must not leave duplicate collectible balances behind. Save protection comes before those changes.

## P3 — vendor extensions

| Request | Current feasibility | Decision |
|---|---|---|
| NVIDIA Dynamic MFG | The shipped Streamline 2.14.1 guide exposes the dynamic path for D3D12. Fixed Vulkan MFG and Auto mode are not that dynamic path. | Recheck vendor Vulkan support before any new backend work; do not rename Auto as Dynamic. |
| XeSS Frame Generation / XeLL | Intel's current public FG/low-latency integration uses D3D12; XeSS SR already has our Vulkan adapter. Standalone XeLL on non-Intel hardware is restricted by Intel's integration contract. | Keep SR and its independent quality menu; plan FG/XeLL with an actual supported backend. |
| AMD ML Frame Generation | The shipped path is analytical FSR 3.1.6. An ML upscaler is not an ML FG integration. | Require the relevant public API/hardware/backend path before exposing a mode. |
| NVIDIA FG model presets A/B/C | R37 adds a dedicated NVAPI application profile, restoration and process-feedback readout. The model choice needs a restart. | Confirm A/B/C on supported NVIDIA runtimes. C needs the newer beta runtime; a saved setting alone is not active-model evidence. |

I will keep HDR support as a requirement for any future FG path. A D3D12 backend or cross-API presentation bridge would be a separate architectural project with explicit synchronization, memory sharing and compatibility work.

## References and credit

I will retain the original licenses and author credits for any code I adapt. shadPS4 cheat addresses/code caves cannot be copied straight into this native runtime.

- [shadPS4 Bloodborne 1.09 cheats](https://github.com/shadps4-emu/ps4_cheats/blob/main/CHEATS/CUSA03173_01.09.json), credited to Shiningami + bloo: Insight and one-hit behavior references.
- [Bloodborne Paramdex](https://github.com/soulsmods/Paramdex/tree/master/BB/Defs) and [DSAnimStudio Bloodborne TAE definitions](https://github.com/Meowmaritus/DSAnimStudio/blob/master/DSAnimStudioNETCore/Res/TAE.Template.BB.xml): wear, effects, Rally, drops, parry and invulnerability states; field names still need verification in the live runtime.
- [Bloodborne save editor](https://github.com/Noxde/Bloodborne-save-editor) and [er-save-watcher](https://github.com/tvhdev/er-save-watcher): format and snapshot references, while keeping original save bytes intact here.
- [Streamline 2.14.1 DLSS-G guide](https://github.com/NVIDIA-RTX/Streamline/blob/v2.14.1/docs/ProgrammingGuideDLSS_G.md), [Intel XeSS SDK](https://github.com/intel/xess), [XeLL guide](https://github.com/intel/xess/blob/main/doc/xell_developer_guide_english.md), [NVAPI settings](https://github.com/NVIDIA/nvapi/blob/main/NvApiDriverSettings.h) and [FSR-Vulkan](https://github.com/FireBurn/FSR-Vulkan): provider and backend contracts.

Development and revision direction: TatsunaKyo. Gameplay baseline: my Windows 11 / RTX 5070 Ti PC. Other hardware reports are welcome; automated checks and their build environments remain recorded with each package.
