Bloodborne for Windows — TatsunaKyo revision

This is my Revision 12, based on Supermedo's Windows v1.6 port. I wanted an English in-game menu, easier window management and more control over upscaling, FG and the overlay. The full feature guide is in README.md; release notes and the development roadmap are in docs.

Releases: https://github.com/TatsunaKyo/bloodborne_pc/releases

Always remember that NO game files are included. You need your own decrypted Bloodborne CUSA03173 1.09 dump, with eboot.bin, sce_module, sce_sys and dvdroot_ps4. The community patches and added runtime cheats require matching 1.09 instructions. Other game versions use the original 30 FPS behavior.

Requirements

- Windows 10 1903 or later, or Windows 11, 64-bit.
- A graphics card with Vulkan 1.3 and a current driver. Individual upscalers and FG providers have additional requirements.
- About 6 GB of free memory commit (RAM plus page file), or 10 GB for 1440p/4K output.
- Python and the required libraries are bundled in the package.

Starting and updating

Open Bloodborne.exe, choose your game folder under Game & effects, set your options and press PLAY. Play checks the game version, save directory, graphics card and FSR 4 assets.

After setting things up once, Play Bloodborne.exe starts directly with your saved settings. If no game folder is chosen, it opens the launcher. Bloodborne.exe --play does the same. The normal log is user\last_run.log.

Advanced has Desktop shortcut and Check for updates; Add to Steam is on Play. I pointed the updater at this fork so it accepts matching TatsunaKyo Windows revision packages. It preserves saves, settings and mods. When updating manually, close the game and launcher, keep your saves/mods/INI files and replace all program files, including bin, scripts, run.py and _internal. Replacing only Bloodborne.exe does not update the native renderer.

Advanced → Launcher language offers English, Russian, Arabic, Spanish, Portuguese, French, German, Italian, Polish, Turkish, Chinese, Japanese and Korean. It defaults to the Windows language. The in-game menu independently offers English and Russian; I made English its default.

Windows and background behavior

I added Windowed, Borderless fullscreen and Fullscreen (driver default) to Play, Display & FPS and the in-game menu. Borderless uses the desktop resolution and refresh rate, so Alt-Tab does not require a display-mode switch. V-sync in borderless off requests Immediate presentation, with possible tearing. On requests Mailbox, with FIFO as a compatibility fallback. Windows and the driver determine the actual presentation path and latency.

When in background offers Keep running, Pause game and rendering, Limit to 30 FPS and Limit to 60 FPS. I replaced my earlier process-suspension approach with cooperative pause: game work and rendering stop while window events remain responsive, and game timers exclude the paused time. Background limits apply to real frames, respect a lower foreground cap and restore the foreground policy on return. Keep running is the default. FG is suspended during pause or a background limit.

Upscaling and presets

Graphics → Upscaler and the in-game menu offer DLSS, FSR 3.1, FSR 4, XeSS Super Resolution 3.0.2 and TAA/native AA. DLSS needs a supported GeForce RTX GPU and driver. FSR 4 needs fsr4_shaders assets and the required device features; the assets are included, or available through Graphics → Download FSR 4 assets. XeSS uses Intel's Vulkan API; I added it as another option for supported Intel and other GPUs. Failed or unsupported providers report the reason and fall back to FSR 3.1.

I exposed DLSS render presets separately from the quality/render-scale setting: Default, E/F (CNN / legacy), J/K (Transformer 1st gen), M/L (Transformer 2nd gen). On Play, the preset row appears only with DLSS selected. Graphics keeps it visible but disabled with another upscaler. The saved preset is retained, and changing it in-game recreates DLSS without restarting the game.

In Revision 12 I gave XeSS its own quality menu, visible only when XeSS is selected on Play, Graphics and in-game. Its seven modes are Native AA (×1.0), Ultra Quality Plus (×1.3), Ultra Quality (×1.5), Quality (×1.7), Balanced (×2.0), Performance (×2.3) and Ultra Performance (×3.0). Each ratio divides the output dimensions to get the input size. The README table compares them with the DLSS/FSR choices. Your XeSS quality is saved separately, and older settings migrate without changing the input resolution. Live mode applies changes on the next frame; startup-patched sessions save them for a restart.

Frame Generation, Reflex and FPS caps

I added analytical FSR 3.1.6 FG x2 and NVIDIA DLSS FG/MFG through Streamline 2.14.1. Select FG on Play, Graphics or in-game. A temporal upscaler must be active; FSR FG can also be used with DLSS or XeSS. Both FG paths support SDR and HDR10. NVIDIA's supported multiplier is checked at runtime, and unsupported choices keep real-frame presentation with an explanation.

Reflex has separate Off, On and On + Boost choices. I kept it usable without FG and independently of the upscaler. NVIDIA FG enables low-latency Reflex automatically; Boost remains optional. NVIDIA FG also needs supported hardware/drivers and Hardware-accelerated GPU scheduling.

The normal FPS cap counts real frames. I added 75 FPS and editable number fields so you can set an exact value without relying on the drag control. FG can add output frames above that limit: 75 real FPS at x2 can produce up to 150 output FPS. Limit total FPS with Frame Generation is separate and optional, with a 30–1000 integer setting. For example, a 130 total cap at x2 derives a 65 real-frame ceiling. Generated frames do not advance game logic or physics. I recommend keeping real-frame limits at 120 or below because the original game logic can misbehave at extreme rates. The practical output rate depends on the GPU, monitor and scene.

The game HUD can still show interpolation artifacts. Dynamic NVIDIA MFG, XeSS FG, AMD ML FG and FG model presets A/B remain follow-up work; their API/backend constraints are explained in docs\frame-generation.md and docs\tatsunakyo-next.md.

Overlay

Show performance overlay turns the top-right OSD on or off in Play, Graphics, Display & FPS and the in-game menu. The settings menu stays accessible with the OSD hidden. I kept the original basic overlay available and made all extra fields optional.

Customize overlay… on Play opens Display & FPS. You can add the DLSS preset letter, input/output resolution, confirmed FG provider/multiplier and Reflex PC latency. I kept these on the same compact line. Full CNN/Transformer descriptions remain in the preset dropdowns.

DLSS (M) means an accepted M preset hint; DLSS (K>M) shows a pending change. Default is shown as Default, and - means no accepted feature yet. Driver/profile overrides can supersede the hint. Resolution uses the actual scene/output sizes, such as 854x480>1920x1080. PC latency comes from a completed Reflex report, excludes the display/input device and shows N/A when unavailable. NVIDIA output FPS uses the SDK's actual presentation count; real FPS is shown separately in the menu.

Preset and overlay preferences are shared in bbport.menu.ini. Saving launcher preferences preserves recent in-game changes, and older show_fps settings migrate automatically.

Cheats

The original startup patches remain in Cheats: Never die, stealth, silent footsteps, Rally never fades, targeted enemy control and gameplay tweaks for Rally, camera distance/rotation, easier running and ragdoll physics. They apply when the game starts.

I added player damage, incoming enemy damage reduction, Blood Echoes and movement multipliers, infinite stamina, consumables/ammunition kept and No Fall Damage to the same page. These can change during play and default off. Revision 9 extends stamina guards to continuous running and direct/script updates. The loader verifies matching 1.09 hooks and rejects conflicting features. See docs\cheats.md for behavior and docs\testing.md for open gameplay checks.

Back up your save before using invasive changes or extreme movement values. The proposed integrated Save Manager and the additional cheats in the roadmap are not features of this package.

Input and data

Insert or L3+R3 opens the port's settings menu. Keyboard fallback: WASD move, arrows camera, Space Cross, Left Shift Circle, E Square, Q Triangle, 1/3 L1/R1, R/F L2/R2, Z/C L3/R3, I/K/J/L d-pad, Enter Options, Tab left touchpad and Backspace right touchpad. Gameplay mouse look and full remapping remain on the roadmap.

- Saves and shader caches: user\ beside Bloodborne.exe, unless you select another directory in the launcher.
- Shared settings: bbport.ini and bbport.menu.ini beside Bloodborne.exe.
- Launcher options: %APPDATA%\bbport-launcher.
- Prepared game image and patches: out\.

Mods and community patches

Put each mod in its own folder under mods\, using dvdroot_ps4\… or the game directories directly. Enable and order them on Mods & patches. The port creates a temporary view instead of changing your game files. Without Windows Developer Mode it uses directory junctions and file hard links; with the game on another drive, the temporary view is made next to the game folder. Third-party shadPS4/GoldHEN XML patches for 1.09 go in patches\.

Online play (upstream beta)

Register at https://shadnet.shadps4.net, then open Online co-op, enable Play online and enter the account name, not the email, and password. Press Test connection, then PLAY and choose online at the title screen. Messages, bloodstains and ghosts come from The Hunter's Dream; bells and summons use shadNet. Everyone needs 1.09 and the same server. Summoning between players is not confirmed yet.

Tests and problems

I test gameplay on my Windows 11 / RTX 5070 Ti PC. Automated checks cover controls, hooks, resource contracts, renderer fixtures and package contents; their logs state the actual test environment. See docs\testing.md for coverage. In Revision 10, I added shared history resets for abrupt camera transitions and reduced repeated renderer work, including staggered index verification. Those changes do not close every pacing or compatibility issue.

The firing crash with combined cheats, uneven frame pacing, inherited empty character-creation preview and some AMD world-loading crashes remain open. For a black screen at startup, try Advanced → Clear shader cache; rebuilding it can cause initial stutter.

For a bug report, include your GPU/driver, settings, reproduction steps and user\last_run.log. I added General → Diagnostics → Developer profiling and crash diagnostics to capture more detail when needed. It is off by default and keeps separate session folders under the save directory's diagnostics folder, with logs, timings, settings, exit code and a crash dump when available. Keep the affected session folder if the firing crash happens again.

Credits

Revision maintained by TatsunaKyo: https://github.com/TatsunaKyo/bloodborne_pc
Original Windows port: Supermedo, https://github.com/Supermedo/bloodborne_pc
Native bbport: deadinside28, https://github.com/deadinside28/bloodborne_pc
Renderer: shadPS4, https://github.com/shadps4-emu/shadPS4
Online: shadp2p by Wozzardman (https://github.com/Wozzardman/shadp2p), shadNet by the shadPS4 team and The Hunter's Dream by droogie (https://thehuntersdream.com).

The full project and community-patch credits are in README.md. Original copyrights and licenses remain intact; third-party runtime licenses are included with the package.

Revision 11: I changed the real-frame limiter so a late frame does not trigger a burst of queued frames. The VideoOut and FSR FG waits now use the existing Windows high-resolution timer. The real-frame and generated-output caps remain separate. I want to improve the uneven pacing reported with FG; please compare the same scene and settings with Revision 10.

Revision 15 brings the full Crowned Workshop design into the launcher and completes queued vertex/index copies before ConstRam overwrites their source. The updated development plan is in docs/tatsunakyo-next.md. I am keeping the flashing report open for the affected-scene comparison.
