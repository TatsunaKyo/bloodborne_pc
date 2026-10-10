# Development roadmap — TatsunaKyo revision

Audit date: **10 October 2026**. Code baseline: [Revision 10, `f84ca08107e77ac7441124835cbb1a38cd386aed`](https://github.com/TatsunaKyo/bloodborne_pc/commit/f84ca08107e77ac7441124835cbb1a38cd386aed).

I finished, rebuilt and delivered Revision 10, with its source published. It includes the shared camera-history resets and renderer changes described in [Quality and performance](quality-and-performance.md). Here I have checked each proposed feature against that code and set the order for the next work. The proposed additions are not in the existing ZIP. I am keeping the in-game menu in English and Russian for now; I have postponed further translations while I work on stability and quality of life.

My first priority is more reliable play: fix the shooting crash, protect saves and improve frame delivery. I want those foundations in place before adding another wave of cheats. I continue testing gameplay on my Windows 11 / RTX 5070 Ti PC, with AMD and Intel results recorded separately. See [Testing and known issues](testing.md).

## What exists and what needs work

“Partial” means that useful code exists, but the requested behavior is incomplete. An existing setting or an automated fixture does not close a reported gameplay bug.

| Area | Revision 10 status | Next work | Priority |
|---|---|---|---|
| Shooting with several cheats enabled | Open crash report. Damage/reduction and item/ammunition hooks exist; diagnostics are opt-in. | Check the combined firing path, object lifetimes and hook context. Cover ordinary shots, Blood Bullets, empty ammunition and repeated firing. | P0 stability |
| Character creation preview | Inherited upstream issue; no dedicated preview fix found. Relaxed readbacks already address a different FaceGen problem. | Follow the preview's render targets, readbacks and UI composition separately from the gameplay camera. | P0 compatibility |
| AMD world-loading crashes | Partial compatibility work, including a BC6H storage-usage fallback. World-load stability remains open. | Separate object-motion device loss, unsupported formats, memory exhaustion and stuck draws. Preserve evidence for each GPU/driver. | P0 compatibility |
| Save Manager | Save mounting, configurable user directory and launcher save detection exist. No integrated backup/restore manager was found. | Verified pre-launch snapshots and restore first; named profiles and coordinated live snapshots afterwards. | P0 save protection |
| Frame pacing | Real-frame cap, separate optional FG output cap, Reflex and a default one-frame GPU queue exist. Uneven delivery is still reported. | Fix overdue-deadline behavior, review Windows waits and NVIDIA scheduling, then compare actual displayed cadence and latency. | P0 pacing |
| Continuous-running stamina | Revision 9 added continuous-drain guards; the automated hook fixture covers repeated updates. | Confirm sustained running in the reported gameplay states and keep the issue open until it passes. | P0 existing cheat |
| Full key/controller remapping | Keyboard fallback and SDL3 gamepads exist; bindings are fixed in `runtime_pad.c`. | Add persistent bindings, conflict detection, device selection and sensible defaults. | P1 input |
| Mouse camera and sensitivity | Mouse input in the port menu exists; gameplay camera mouse look does not. | Relative mouse input first. Direct camera integration is a separate step from emulating the right stick. | P1 input |
| Xbox/PlayStation controllers and prompts | SDL maps supported pads, axes, vibration and touch input. Game prompts still use the game's PlayStation interface. | Keep controller support; add appropriate prompt assets and device switching rather than treating this as a new controller backend. | P1 input |
| Ultrawide resolutions | Community XML already contains 21:9 and 32:9 patches. Scene/output resizing and native UI composition exist. | Integrate aspect-aware presets, FOV, HUD anchors, lock-on bars, menus and cinematic handling together. | P1 display |
| Adjustable FOV/HUD | Camera-distance and text-scale patches provide limited starting points. They do not supply an adjustable FOV or HUD editor. | Bound FOV changes; provide HUD scale/safe area before free placement. Test projection and temporal history together. | P1 display |
| Shader compilation and stutter | Disk cache, warm-up, profile compatibility checks and temporary-file writes exist. | Validate damaged entries and recover from rejected pipelines; then assess safe background compilation/preloading. | P1 renderer |
| Temporal resets | Shared camera-cut, loading-gap and feature-recreation resets are implemented in Revision 10. | Validate transitions in gameplay; improve particle/transparency motion coverage separately. | Existing + P1 quality |
| Game HUD excluded from FG | Native UI rendering exists, but FG still receives the final game HUD. | Capture a matching HUDless scene and UI contribution; preserve HDR and resource ownership. | P1 FG quality |
| FSR FG, NVIDIA FG/MFG, Reflex, XeSS SR | Included. FSR FG is analytical 3.1.6; NVIDIA uses Streamline 2.14.1. SDR/HDR10 are supported. | Keep these paths working through pacing and HUD changes. Reflex remains usable without FG. | Preserve |
| Dynamic MFG, XeSS FG, AMD ML FG, FG presets A/B | Follow-up work, with API/backend constraints. | Keep the separate feasibility work below; do not expose ineffective settings. | P3 backend/vendor work |

The seven added runtime cheats remain player damage, incoming-damage reduction, Echoes gained, movement speed, infinite stamina, consumables/ammunition kept and no fall damage. Original startup cheats remain available too. Their existence is not a reason to ignore the firing crash or the outstanding stamina check.

## P0: frame pacing and latency

The first scheduling issue I found is in `VideoOutDriver::PresentThread`, in `gpu/shadps4/core/libraries/videoout/driver.cpp`. In Revision 10, after a delayed flip, the deadline advances with `max(next_flip + period, now - period)`. That can leave it in the past and let queued requests through in a short burst.

A model of that exact recurrence at 90 FPS, after a 50 ms stall and with 1 ms of present-call work per request, gives submission times of **50, 51, 52 and 61.111 ms**. The first two gaps are 1 ms, while the nominal period is 11.111 ms. That helped me identify a catch-up case worth fixing in the scheduler. I still need to check the result on the Windows gameplay setup, since there may be other causes of uneven delivery as well.

I have put the first correction in a separate Revision 11 build. The next deadline is one full interval after the later of the previous deadline and the actual submission. The same queued-frame fixture now gives **50, 61.111, 72.222 and 83.333 ms**. Tests cover queued requests, changing caps, long stalls, uncapped mode, pause/refocus and stopping while paused. I kept the guest's vblank notifications and simulation timing separate from generated presents. I still want gameplay comparisons before closing the wider pacing issue.

Other concrete checks:

- **FSR FG:** I reused `compat_sleep_ns`, the runtime's high-resolution waitable timer, for the VideoOut waits and FSR FG half-frame gap in Revision 11. The interpolation completion wait and protection of the source resources remain in place. Reviewing the whole display timeline, including GPU and WSI work, is a separate follow-up.
- **NVIDIA FG/MFG:** Streamline owns generated-frame pacing. Keep the game's real-frame cap and optional total-output cap distinct. Review where the game is delayed relative to `slReflexSleep`; do not insert another sleep between SDK-generated frames or pass a real-frame FPS value as an output cap.
- **Queue overlap:** current NVIDIA options block the presenting client queue. The public guide allows experiments with `eBlockNoClientQueues`, but requires input-completion fence protection. Those fences already exist here and must remain correct through resize, disabling FG and resource reuse. This is an experiment, not a safe default switch based on GPU utilization alone.
- **FG off:** review swapchain recreation when NVIDIA generation is disabled, as required by the SDK to avoid residual presentation overhead. A settings toggle and a complete SDK/swapchain transition are different operations.
- **Measurement:** distinguish real-frame completion, CPU present calls and actual display changes. NVIDIA recommends display-change timing for FG pacing. Vulkan presentation-timing extensions are optional, and support must be queried; `VK_GOOGLE_display_timing` also treats VRR as fixed refresh. Preserve a compatible fallback.

Test 60, 75, 90 and 120 real-FPS settings, several optional output caps, FG off/FSR/NVIDIA x2 and supported MFG modes, SDR/HDR10, borderless, VRR and focus changes. Compare tail frametimes and latency, not just average FPS. More queued frames or a forced 120 output cap can make delivery look smoother while increasing delay or reducing the real-frame rate.

An aggregate 20% CPU load or 85% GPU utilization does not identify spare render capacity: a busy game thread, resource wait, submission dependency or presentation delay can leave the remaining hardware idle. Code inspection can remove redundant work, as Revision 10 does; proving which wait dominates a particular scene requires timing evidence. Keep those diagnostics optional.

## P0: crashes and save protection

### Shooting and AMD compatibility

The shared damage/reduction hook reads the attack context and updates both applied damage and bookkeeping. Item use, ammunition use and equipped-ammunition use take separate paths. The firing regression should exercise these together, including projectile ownership, player/NPC classification, loading/unloading and repeated shots. A generic “multiply every damage value” hook would broaden the risk. Extend the existing ABI/state-preservation fixture, then check the affected combinations on the Windows gameplay setup.

For AMD, the native port's [issue 39](https://github.com/deadinside28/bloodborne_pc/issues/39) is more relevant than an old emulator-only crash report. It distinguishes object-motion device loss, texture pressure, pipeline-cache failures and driver faults. Some proposed fixes already exist in this baseline: `image.cpp` retries unsupported speculative storage usage, cache writes use temporary files, and GPU assertion failures stop the port. In particular, the report's theory that release assertions disappear does **not** match our always-active `ASSERT_MSG` and `gpu/shim/common/assert.cpp`.

Remaining code concerns include unsupported format combinations after the retry, tiled GPU-written images that the texture collector cannot safely download/evict, and recovery from bad serialized pipeline entries. Do not free dirty tiled images just to lower the memory counter. [Issue 56](https://github.com/deadinside28/bloodborne_pc/issues/56) records a separate RADV/Linux stuck-draw case; it provides a shader-investigation reference, not confirmation of the same cause on Windows AMD.

### Save Manager rollout

`runtime_savedata.c` mounts game files and stores companion metadata and SaveDataMemory. It does not provide automatic verified backups. The launcher detects `SPRJ*` directories and accepts another user directory; mod profiles are not save profiles. The startup sound fix also modifies a byte in `userdata0010`, so a pre-launch snapshot must happen before that runtime work.

1. **Closed-game backups and restore:** snapshot the actual user/title save paths, companion `.sce_sys` directories and applicable `<title>.memory` data. Respect custom directories and regional title IDs. Keep archives outside the live save tree. Copy into a staging location, record a manifest with relative paths, sizes and SHA-256 hashes, verify it, then publish the completed snapshot.
2. **Safe restore:** refuse while the game or a save writer is active. Verify and stage the chosen backup, preserve the current save as a rollback snapshot and use a recoverable replacement procedure with a journal. Multiple directory renames are not one atomic transaction. Handle interruption, locked files and low disk space without deleting the last good copy.
3. **Automatic protection:** keep pre-launch snapshots and separate post-exit snapshots, with retention rules that never replace the last known usable save with a crash-session copy. Hash verification detects damaged backup bytes; it cannot prove that the game originally wrote a semantically valid save.
4. **Profiles and live changes:** switch named save profiles before launch. Snapshots before enabling invasive cheats during play need coordination with all game save writes. Pausing rendering or observing stable timestamps alone does not establish a consistent multi-file snapshot. Defer that live integration until the runtime can acknowledge a safe save boundary.

I want the first version to preserve the existing save format byte for byte. Save editors are useful format references, but I am keeping balance editing, region conversion and automatic repair outside the backup manager's initial scope.

## Cheats: inventory, behavior and feasibility

These additions are planned. None of the requested fourteen features is implemented as a new selectable runtime cheat in Revision 10. Adjustable Rally has an existing no-decay starting point. One-hit kill and Insight also have community references, but those are not installed features in this fork.

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
| One-Hit Kill | Player damage hook and a community one-hit-kill reference. No boss/scripted-target eligibility filter here. | Ordinary hostile targets only. Preserve player, allies, mandatory interactions and boss transitions; do not reuse x16 damage as a guarantee. | Medium–high; after firing fix |
| Freeze Enemy AI | Enemy Control and stealth already exist; neither freezes AI. | Suspend eligible enemy decisions/movement while preserving world/event updates and a reliable unfreeze path. Handle projectiles, animation and boss scripts explicitly. | High; training tools |
| Infinite Buff Duration | No runtime effect-lifetime hook; effect and animation definitions offer references. | Preserve selected temporary player weapon buffs, with normal removal on expiry conditions such as weapon change/death. Do not freeze every status effect. | Medium–high; after effect lifecycle work |
| Easier firearm parry / Adjustable Parry Window | No runtime parry-window control; Bloodborne animation definitions identify parry-possible states. | One shared leveled control: Off, x2, x4, x8, x16 for the eligible vulnerability window. A narrower x0.5 option can serve difficulty customization. Keep non-parryable attacks excluded. | High; one coherent training feature |
| Increased dodge invulnerability | No runtime dodge-window hook; Bloodborne animation definitions identify invincibility states. | Bounded levels during genuine dodges, restoring normal state afterwards. Use game time, not output/FG frames. Permanent invulnerability is a separate behavior. | High; training tools |

I would combine easier firearm parries and Adjustable Parry Window into one leveled control. I want it to widen the timing window while keeping non-parryable attacks excluded. Higher factors must stay within the eligible attack animation, so a factor may saturate at that bound. I need to verify how vulnerability enters and exits before selecting the hook. Enlarging the visceral follow-up window would be a separate setting.

New runtime features must follow the existing installation contract in `src/runtime_cheats.c` and `gpu/bbcheats.h`: verify the 1.09 image and instructions, reject conflicts, install the complete hook group before game threads start, preserve both game and host ABI state, and provide a cheap disabled path. Validate player/enemy identity and object lifetime at the actual hook context. A matching offset does not prove those preconditions.

Economy, death and progression cheats need save round trips and duplicate-award checks as well as trampoline tests. Mutually exclusive Echoes death/recovery policies should be explicit. Settings belong in the existing Cheats pages in both interfaces, with live/restart behavior stated accurately. All new cheats default off; values that persist in saves must be documented.

## P1: input, ultrawide and image quality

For input, start with a configurable action map rather than another hard-coded keyboard layout. Cover held/released actions, controller reconnects, diagonals, mouse buttons, wheel and menu capture. Relative mouse input needs sensitivity, inversion and clean release on Alt-Tab. The native port's [PR 108](https://github.com/deadinside28/bloodborne_pc/pull/108) is a useful implementation reference, but its mouse movement is converted to the right stick and its reported test platform is CachyOS. It does not establish direct camera control or Windows gameplay coverage. Controller glyphs require assets and correct game/UI device detection as well as input mapping.

For ultrawide, the existing XML has 2560x1080, 3440x1440 and 5120x2160 patches, plus 3840x1080 and 5120x1440. Normal resolution generation currently uses a 16:9 template and changes scene/UI dimensions; adding those sizes to a dropdown would not satisfy the full request. Coordinate camera projection, viewport, HUD anchors, lock-on indicators, menus and cinematic aspect policy. Test 21:9 and 32:9 with HDR, upscaling, FG and resize. Keep a usable safe area before adding unrestricted HUD placement.

For temporal quality, retain Revision 10's resets and improve motion coverage for transparent objects/particles without resetting accumulation on every normal camera movement. HUD separation is a particularly useful FG improvement. AwesomeObserver's native fork contains owned scene snapshots and HUD coverage/composition work worth adapting. Its documented FG path falls back to real frames for HDR, supports fixed x2 and lacks our MFG/Reflex combination. Preserve this fork's HDR decoding/encoding, Streamline tags, matching output extents and completion-fence ownership. A scene/backbuffer difference mask also needs testing on translucent UI; it is not automatically the game's original alpha.

Shader cache recovery should build on the existing cache rather than introduce a second one. Validate blob sizes/versions and recover from rejected entries without deleting saves or clearing every healthy cache after any exit code. AwesomeObserver also has a damaged-pipeline recovery reference. Background compilation must use captured shader state safely and keep required draws visible; skipping draws to hide compilation stalls would create another rendering bug.

## Vendor/backend follow-up

- **NVIDIA Dynamic MFG:** Streamline 2.14.1 documents D3D12-only support. Its Auto mode retains a fixed multiplier with conditional disablement; it is not Dynamic MFG. Recheck vendor support before planning an additional backend.
- **Intel XeSS FG:** the public FG integration requires D3D12. XeSS Super Resolution already works through the current Vulkan adapter.
- **AMD ML FG:** analytical FSR 3.1.6 FG remains the shipped implementation. Review an actual supported ML API and its hardware/backend requirements before offering another mode.
- **NVIDIA FG presets A/B:** investigate public driver profile settings independently of SR presets. `DLSSGOptions` has no A/B model field. Preserve existing profiles and prove that selection changes the FG model before exposing a control.

Adding D3D12 or a cross-API presentation bridge is a separate architectural project with synchronization, memory-sharing, HDR and compatibility costs. It should not be slipped into a pacing patch.

## Release order and small candidates

| Milestone | Scope | Completion criteria |
|---|---|---|
| P0 stability and pacing revision | Shooting regression, missed-deadline scheduling, Windows wait review, damaged-cache handling and actionable AMD/preview investigation. | Rebuilt launcher and native components; hook/scheduler/cache tests; Windows gameplay firing, stamina, pacing, HDR and focus checks. Keep unconfirmed hardware bugs open. |
| P0 Save Manager | Closed-game snapshots, verified restore/rollback, custom paths and retention. | Interrupted-copy/restore, disk-full, locked-file, title/profile isolation and byte-identical save tests; successful game load after restore. |
| P1 PC experience | Remapping/mouse, staged ultrawide/HUD, FG HUD separation and targeted shader/motion improvements. | Each feature lands independently with Windows input/display and SDR/HDR regression coverage. |
| P2 cheats and training | Start with wear, regeneration, status, Insight and Rally; follow with economy/HP; then parry, dodge, buffs and AI tools. | Verified 1.09 hooks, reversible state, save round trips where relevant, and gameplay checks for the affected mechanic and combinations. |
| P3 backend extensions | Dynamic MFG, XeSS FG and ML FG feasibility; driver-based FG A/B. | A supported public API, real hardware results and no regression to existing Vulkan/HDR behavior. |

**Revision 10 stays closed.** I have added the complete inventory and restored omitted upstream issues to the testing page. The delivered launcher/components keep their existing checksums.

Revision 11 starts with the overdue-deadline correction and reuse of the existing Windows timer, with regression checks and a Windows rebuild. Targeted malformed-cache rejection and the firing crash are the next items. I am deferring queue-parallelism changes, live save snapshots and the new cheat wave until their dependencies are resolved. HUDless composition has a useful reference, but I need to handle its HDR and resource lifetimes as a separate feature.

## Implementation references

These are the references I used to plan the work, with their original authors credited. I will adapt and check any code I use against this port's own runtime and rendering pipeline.

- [AwesomeObserver native fork at `405f9fe`](https://github.com/AwesomeObserver/bloodborne_pc/tree/405f9fe6a13aaa9e5265dfd7d72c99188706d101): HUD coverage, owned FG inputs, Windows timer use and cache recovery. Its native integration is closer to this port than emulator-specific loader code, but its FG/HDR interfaces differ.
- [Official shadPS4 Bloodborne 1.09 cheats](https://github.com/shadps4-emu/ps4_cheats/blob/main/CHEATS/CUSA03173_01.09.json), credited to Shiningami + bloo: Insight and one-hit-kill behavior references. Fixed code caves, relocated addresses, balance-forcing logic and assumed object layouts must not be copied directly into this runtime.
- [Bloodborne Paramdex definitions](https://github.com/soulsmods/Paramdex/tree/master/BB/Defs) and [DSAnimStudio's Bloodborne animation template](https://github.com/Meowmaritus/DSAnimStudio/blob/master/DSAnimStudioNETCore/Res/TAE.Template.BB.xml): weapon wear, effects, regain, drop tables and parry/invulnerability states. A named field is evidence to investigate, not proof of its live offset or safe mutation.
- [Bloodborne save editor](https://github.com/Noxde/Bloodborne-save-editor) and [er-save-watcher](https://github.com/tvhdev/er-save-watcher): save-layout and checkpoint ideas. Start with whole-file preservation and runtime-specific save boundaries rather than transplanting an emulator path or continuous restore loop.
- [Streamline 2.14.1 DLSS-G guide](https://github.com/NVIDIA-RTX/Streamline/blob/v2.14.1/docs/ProgrammingGuideDLSS_G.md), [manual Vulkan hooks](https://github.com/NVIDIA-RTX/Streamline/blob/v2.14.1/docs/ProgrammingGuideManualHooking.md), [NVAPI settings](https://github.com/NVIDIA/nvapi/blob/main/NvApiDriverSettings.h), [Intel XeSS](https://github.com/intel/xess) and [FSR-Vulkan](https://github.com/FireBurn/FSR-Vulkan): provider contracts and backend limits.
- [Windows high-resolution timers](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-createwaitabletimerexw) and [Vulkan display timing](https://docs.vulkan.org/refpages/latest/refpages/source/VK_GOOGLE_display_timing.html): timing facilities, with platform/extension constraints.

Maintained by TatsunaKyo. Original port, community patch and vendor credits remain intact. Any reused code must retain its license and attribution.
