[Current guides](index.md) · [Current reports](known-issues.md) · [Infrastructure plan](infrastructure-plan.md)

# Where I am taking The Crowned Workshop

Updated **13 October 2026**, after the published Revision 23 and during Revision 24's first P1 change. I checked the renderer, presentation code, launcher, input runtime, save mounting and cheat hooks; the infrastructure revision preserves those gameplay implementations.

My Revision 19 Hunter's Dream test suggests the NVIDIA FG flashing is resolved. I am keeping its foliage-batch history and scene-depth preservation, together with Revision 20's pacing work and optional real-frame graph. The current report list retains the Echoes multiplier and FG pacing checks. I removed shooting and running-stamina from that list; the earlier investigations stay available as history and regression coverage.

## Current work and release order

| Revision / stage | What I am doing | Current state | What completes it |
|---|---|---|---|
| **21 — shared settings and feature introductions** | Match the seven launcher/menu categories, group the complete controls, keep Play shortcuts and improve feature introductions/infographics. | Compiled-launcher and real ImGui category/layout checks; preserve the Revision 19 visual correction and Revision 20 pacing/graph. | Complete; stable Revision 21 is published. Preserve this layout in future revisions. |
| **22 — updater, releases and documentation** | Correct legacy stable-tag recognition; derive release metadata and validate packages; add CI/report forms and current guide navigation. | Updater/package/publication regressions and actual GUI checks; [hosted regression CI passes](https://github.com/TatsunaKyo/bloodborne_pc/actions/runs/38229068006). Rendering and gameplay scope unchanged. | Complete source/build and regression verification. Enable repository Issues for community reports. |
| **23 — Support Report and Save Manager** | Reuse existing diagnostics in an inspected/redacted ZIP; protect progress with backups and restore/rollback. | Implemented with independent privacy/archive, save-integrity and actual-control tests. | Complete rebuilt package, published stable release and hosted Windows verification. More restored-save gameplay reports are welcome. |
| **Next — current gameplay reports** | Check genuine Echoes awards and compare FG pacing in the same scene. | These features already exist; the report list is limited to the remaining checks. | Save/reload award checks and matched real/displayed cadence measurements on my Windows setup. |
| **Next — Save Manager profiles** | Extend the shipped backup/restore tools with named profiles and clearer profile switching. | First version covers backups, snapshots, rollback, retention and custom save locations. Live snapshots remain deferred. | Save/title isolation and loaded-game comparisons from restored profiles. |
| **24 — shader-cache recovery** | Reject damaged records, recover from failed preload and finish accepted writes at shutdown. | Implemented with production IO/serializer/driver-boundary and warm-up regressions. | Windows execution, complete rebuilt package and gameplay comparison; see [cache recovery](shader-cache.md). |
| **P1 — frame delivery and image quality** | Tail frametimes, damaged shader-cache recovery, HUDless FG inputs and more reliable particle/transparent motion. | Scheduling/history fixes exist; remaining work is split into separate changes below. | Compare real and displayed cadence, HDR/SDR, FG off/on, resize and focus changes without adding extra latency. |
| **P1 — PC input and ultrawide** | Remapping and relative mouse input first; aspect-aware HUD/FOV and cinematic policy afterwards. | Existing pad/keyboard and community aspect patches are useful foundations. | Reconnect/release/menu-capture tests and real 21:9/32:9 gameplay checks. |
| **P2 — new cheats and training tools** | Durability, regeneration, status and Rally first; progression and timing changes after save protection. | Reviewed individually below; no new feature in this group is being presented as finished. | Verified 1.09 hooks, reversible disabled states and gameplay/save round trips for the affected mechanics. |
| **P3 — vendor/backend extensions** | Dynamic MFG, XeSS FG/XeLL, AMD ML FG and FG model presets. | Feasibility work; blocked or incomplete public integration paths. | Supported vendor API and target-hardware results while preserving Vulkan and HDR compatibility. |

I am keeping each revision small enough to compare with the previous one. Published packages retain their original checksums; [release notes](releases/index.md) and the [test history](history/testing-through-21.md) record the completed work. English and Russian remain the in-game menu languages; I have postponed the additional translations.

## Repository work alongside gameplay

Revision 22 addresses the verified updater/release-tooling problems and adds CI/reporting infrastructure. The main README now includes a roadmap and live-editing introduction, with current reports separated from hardware coverage and history. The [infrastructure plan](infrastructure-plan.md) keeps support archives, reviewed compatibility, the social preview and a possible documentation site in separate phases. Save Manager, native input, ultrawide/HUD and pacing remain on this gameplay roadmap.

## What is already available

| Feature | Implementation I checked | What still needs attention |
|---|---|---|
| DLSS, FSR and XeSS upscaling | `vk_temporal_upscaler.cpp`, `vk_xess.cpp`, provider adapters and scene sizing. XeSS has seven independent quality choices; Play shows its dropdown only for XeSS and DLSS's model dropdown only for DLSS. | More Intel/Radeon gameplay coverage and remaining visual artifacts. |
| FSR FG and NVIDIA FG/MFG | Analytical FSR 3.1.6 and Streamline 2.14.1; HDR10/SDR paths, input fences and supported fixed multipliers. | HUD separation and displayed-frame cadence. Dynamic MFG is a separate feature. |
| Reflex and AMD Anti-Lag 2 | NVIDIA input/simulation/render markers; `VK_AMD_anti_lag` capability checks with matching real-frame input/present IDs. Both are independent of the selected upscaler. | Radeon gameplay confirmation. AMD Anti-Lag does not supply a latency number for the overlay. |
| Real/FG frame limits | Shared real-FPS setting in both interfaces, editable numeric fields/sliders, independent optional output limit and background 30/60 modes. | Revision 14 corrects recurring timer drift; remaining hitches and latency need scene comparisons. |
| Borderless and background behavior | Windowed/borderless/exclusive modes and cooperative pause/refocus in VideoOut/runtime. | Keep HDR, VRR and focus transitions in every presentation regression. |
| Custom performance overlay | Optional preset letter, input/output sizes, FG mode/output FPS and supported latency telemetry; compact layout and whole-overlay switch. | Game HUD is still part of FG's input image. |
| Temporal history and geometry reads | Camera/cut/loading/resize resets, index-content checks, finite-vector guards, repeated-instance rejection, ConstRam waits, draw-thread copy publication, vertex-table validation and CPU DMA completion waits. Revision 19 adds foliage model-list identity and owned reconstruction-time depth. | My latest Revision 19 comparison suggests the flashing is resolved; preserve those fixes while improving pacing. |
| Seven live cheats | Damage, incoming-damage reduction, Echoes gained, movement, stamina, kept consumables/ammunition and no fall damage in `runtime_cheats.c`. | The current Echoes multiplier report; existing startup cheats also remain available. |
| Diagnostics | Opt-in session logs, performance counters and Windows crash capture, under Advanced → Diagnostics. | Add evidence where it can distinguish a failure; keep normal launches free of profiling overhead. |
| Workshop identity | Original workshop paintings, crowned TK emblem, editable banner and eleven README infographics. Revision 15 redesigned the launcher; Revision 16 adds the themed in-game tabs. | Both interfaces have layout/control coverage; keep checking actual game input and different monitor sizes. |

## P0 — rendering and compatibility

### Preserve the flashing correction

The foliage-history and owned scene-depth changes resolved the visible Hunter's Dream flashing in my Windows 11 / RTX 5070 Ti comparison. I am keeping them while working on pacing; any new FG change needs to retain their ordering and resource-lifetime checks. [The renderer guide](quality-and-performance.md) explains the implementation, and [the dated investigation](history/flashing-investigation.md) preserves the earlier comparisons.

### Existing cheat regression coverage

The damage/reduction hook reads an attack context shared by melee/projectiles, while item use, ammunition use and equipped-ammunition use have separate hooks. I will check those paths together, including object ownership, missing/dead player state, unloaded targets and repeated firing. Blood Bullets and empty ammunition belong in that regression too. These cases remain useful coverage before adding new damage or one-hit-kill options; they are not being reintroduced as current crash reports.

The stamina hook already handles several drains. Future stamina changes should retain sprint coverage for stop/start, low stamina and combat transitions. The earlier report is no longer part of the current list. Echoes multiplication needs checks of genuine positive awards, recovered Echoes, spending and load/respawn; I do not want repeated multiplication of an existing balance.

### AMD loading and character creation

`image.cpp` already retries speculative unsupported storage usage, and the assertion path remains active in release builds. [Native-port issue 39](https://github.com/deadinside28/bloodborne_pc/issues/39) distinguishes object-motion device loss, memory pressure and driver failure; those should remain separate investigations. Dirty tiled GPU images must not be discarded merely to lower the VRAM counter.

The character-creation preview has no dedicated fix in this baseline. I will trace its targets/readbacks/UI independently of gameplay camera motion. Existing FaceGen readback handling does not establish that the preview works.

## P0 — Save Manager

The [first implementation](save-manager.md) now copies and verifies the complete saves tree before launching, including metadata and save memory. Manual snapshots, restoration with rollback, automatic retention and custom save locations are integrated into Game & files. The native runtime acquires the saves lease before its startup audio correction; archive/restore failures and terminated transactions have their own regression coverage.

Named profiles are the next extension. Live snapshots before invasive cheats still need an acknowledged boundary from the actual save writer; a background pause or stable timestamp is insufficient. Region conversion, balance editing and automatic save repair remain separate work.

## P1 — frame pacing, cache and temporal quality

The current scheduler fixes both the burst after a long stall and the cumulative timer delay that put a 75 cap near 73.4 FPS in my logs. Production tests cover queued frames, stalls, timer jitter, changing caps, uncapped mode and pause/refocus. Remaining work is the complete display timeline: GPU completion, WSI, Streamline's generated cadence and FSR interpolation/presentation waits.

I will preserve real-frame/FG-output cap separation and Reflex's timing. Streamline queue parallelism is a separate experiment requiring the existing input-completion fences; simply releasing queues or inserting another sleep can change latency or resource ownership. Disabling NVIDIA FG also needs the SDK's proper swapchain transition. A smoother 120-FPS output alone does not settle those cases.

Revision 24 starts with [shader-cache recovery](shader-cache.md). I bounded record lengths before allocation, added checksums while retaining old records, made failed preload recoverable and kept accepted writes through shutdown. A missing or incompatible GPU profile starts a fresh cache. Required draws still compile normally when a record cannot be reused. Display scheduling, HUD separation and particle motion remain separate next steps.

The game HUD currently reaches FG. I want owned HUDless color plus the matching UI contribution, with correct HDR encoding and resource lifetimes. [AwesomeObserver's native implementation](https://github.com/AwesomeObserver/bloodborne_pc/tree/405f9fe6a13aaa9e5265dfd7d72c99188706d101) provides a useful starting point, but its HDR behavior and fixed multiplier differ from this fork. Particles/transparency and disocclusion checks follow separately; I do not want constant history resets that remove the benefit of temporal accumulation.

## P1 — input and ultrawide

SDL3 controller axes/buttons/vibration/touch and a fixed keyboard fallback already exist in `runtime_pad.c`. Full remapping, configurable sensitivity and native gameplay mouse camera control do not. I will start with a persistent action map, release/reconnect behavior and relative mouse capture that cleanly releases on Alt-Tab and menu entry. [Upstream PR 108](https://github.com/deadinside28/bloodborne_pc/pull/108) is a reference for stick-emulated mouse look; direct camera integration remains a distinct task. Controller-specific glyphs need appropriate assets and device detection.

The community XML already contains 21:9 and 32:9 patches. That is useful, but the port's normal resolution template is still 16:9. The integrated feature needs camera projection/FOV, HUD safe area/anchors, lock-on indicators, menus and a cinematic aspect policy, with upscalers/FG/HDR tested together. I will start with HUD scaling and safe areas before unrestricted placement.

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
| NVIDIA FG model presets A/B | These are separate from SR presets E/F/J/K/M/L; `DLSSGOptions` does not provide an A/B model field. | Investigate supported driver-profile control, restore existing profiles and prove that the chosen model changes. |

I will keep HDR support as a requirement for any future FG path. A D3D12 backend or cross-API presentation bridge would be a separate architectural project with explicit synchronization, memory sharing and compatibility work.

## References and credit

I will retain the original licenses and author credits for any code I adapt. shadPS4 cheat addresses/code caves cannot be copied straight into this native runtime.

- [shadPS4 Bloodborne 1.09 cheats](https://github.com/shadps4-emu/ps4_cheats/blob/main/CHEATS/CUSA03173_01.09.json), credited to Shiningami + bloo: Insight and one-hit behavior references.
- [Bloodborne Paramdex](https://github.com/soulsmods/Paramdex/tree/master/BB/Defs) and [DSAnimStudio Bloodborne TAE definitions](https://github.com/Meowmaritus/DSAnimStudio/blob/master/DSAnimStudioNETCore/Res/TAE.Template.BB.xml): wear, effects, Rally, drops, parry and invulnerability states; field names still need verification in the live runtime.
- [Bloodborne save editor](https://github.com/Noxde/Bloodborne-save-editor) and [er-save-watcher](https://github.com/tvhdev/er-save-watcher): format and snapshot references, while keeping original save bytes intact here.
- [Streamline 2.14.1 DLSS-G guide](https://github.com/NVIDIA-RTX/Streamline/blob/v2.14.1/docs/ProgrammingGuideDLSS_G.md), [Intel XeSS SDK](https://github.com/intel/xess), [XeLL guide](https://github.com/intel/xess/blob/main/doc/xell_developer_guide_english.md), [NVAPI settings](https://github.com/NVIDIA/nvapi/blob/main/NvApiDriverSettings.h) and [FSR-Vulkan](https://github.com/FireBurn/FSR-Vulkan): provider and backend contracts.

Development and revision direction: TatsunaKyo. Gameplay baseline: my Windows 11 / RTX 5070 Ti PC. Other hardware reports are welcome; automated checks and their build environments remain recorded with each package.
