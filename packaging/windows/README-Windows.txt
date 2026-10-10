Bloodborne (bbport) for Windows - TatsunaKyo revision
==================================================

Revision 8, based on Supermedo's Windows v1.6 port.
Releases: https://github.com/TatsunaKyo/bloodborne_pc/releases

No game files are included. You need your own decrypted dump of Bloodborne CUSA03173
(the folder with eboot.bin, sce_module, sce_sys, dvdroot_ps4). Game version 1.09 is needed for
the community patches (60/90/unlocked FPS, resolution, effects); other versions run at 30 FPS.

Requirements
- Windows 10 (1903 or later) or Windows 11, 64-bit.
- A Vulkan 1.3 graphics card with a current driver.
- About 6 GB of free memory commit (RAM + page file), 10 GB for 1440p/4K output.
  Nothing else: Python and the libraries are inside this folder.

Starting
- Bloodborne.exe opens the launcher. On "Game & effects" pick your game folder, adjust the
  settings, press PLAY. The "Play" page checks the game version, saves, graphics card and
  FSR 4 assets.
- Play Bloodborne.exe starts the game straight away with the settings saved in the launcher,
  without opening it. Set things up once in Bloodborne.exe, then use Play Bloodborne.exe (or a
  shortcut to it, or "Add to Steam" on the Play page). If no game folder is chosen
  yet it opens the launcher. Bloodborne.exe --play does the same. The log goes to
  user\last_run.log.
- Advanced -> "Desktop shortcut" puts Bloodborne on the desktop.
- Updates: when a new version is out, the launcher shows it at the bottom left; "Update"
  downloads and installs it and opens the launcher again (saves, settings and mods are kept).
  Advanced -> "Check for updates" checks by hand. This revision checks only TatsunaKyo's
  fork and accepts its Windows revision package; it does not install upstream releases.
- Advanced -> "Launcher language": English, Russian, Arabic, Spanish, Portuguese, French,
  German, Italian, Polish, Turkish, Chinese, Japanese, Korean (default: the Windows language).
- Play -> "Window mode": Windowed, Borderless fullscreen, Fullscreen (driver default).
  Display & FPS has the same selector, "V-sync in borderless" and "In-game menu language".
  Borderless uses the desktop resolution/refresh rate. V-sync off requests Immediate
  presentation (possible tearing); V-sync on requests Mailbox, with FIFO as fallback.
- Play / Graphics -> "DLSS render preset" ("DLSS preset" on Play): Default (driver),
  E/F (CNN / legacy), J/K (Transformer 1st gen), M/L (Transformer 2nd gen).
  The launcher selector stays visible and is enabled only with DLSS selected. It preserves the saved preset when another upscaler is chosen and is separate from the quality/render-scale preset. The R3+L3 / Insert menu has the same
  choice; changing it recreates DLSS on the next frame, without a game restart.
- "Show performance overlay" in Play, Graphics, Display & FPS and the in-game menu
  hides/shows the top-right OSD. The settings menu remains accessible when it is hidden.
  "Show DLSS preset in overlay" adds the preset letter to the same original line:
  DLSS (M), or DLSS (K>M) while a change from K to M is pending. It defaults to off,
  keeping the basic overlay. Full model descriptions remain in the dropdowns.
  Default is shown as Default; - means no accepted DLSS feature yet. The readout
  reports the accepted NGX feature's hint. Driver/profile overrides can supersede it.
  Preset and OSD preferences are shared in bbport.menu.ini; the launcher preserves
  recent in-game changes. Old bbport.ini show_fps settings are migrated automatically.
- Display & FPS -> "Show input/output resolution in overlay" adds the current scene
  and output sizes, such as 854x480>1920x1080, on the same OSD line. It starts off.
  The in-game menu has the same checkbox; it is separate from the DLSS preset readout.
- Display & FPS -> "When in background": Keep running, Pause game and rendering,
  Limit to 30 FPS, or Limit to 60 FPS. The in-game menu has the same choice.
  Pause stops game submissions and rendering while the window stays responsive;
  game timers exclude the paused time. The FPS choices keep a lower foreground cap
  and restore the foreground limit when you return. Keep running is the default.
- In the game, Insert (or L3+R3 on a gamepad) opens the port's menu (upscaler, resolution,
  effects, window mode, menu language). The launcher and in-game menu share these preferences
  in bbport.menu.ini. Keyboard: WASD move, arrows camera, Space Cross, Left Shift Circle, E Square,
  Q Triangle, 1/3 L1/R1, R/F L2/R2, Z/C L3/R3, I/K/J/L d-pad, Enter Options, Tab touchpad.

Data
- Saves and shader caches: user\ next to Bloodborne.exe (the launcher can pick another folder).
- Settings: bbport.ini next to Bloodborne.exe; launcher options in %APPDATA%\bbport-launcher.
- Generated files (prepared game image, patches): out\.

Online play (beta)
- Register a shadNet account at https://shadnet.shadps4.net. In the launcher open
  "Online co-op", tick "Play online", enter the account name (not the email) and password,
  press "Test connection", then PLAY and choose online at the title screen.
- Messages, bloodstains and ghosts come from The Hunter's Dream (https://thehuntersdream.com);
  bells and summons go through the shadNet server. Everyone needs game version 1.09 and the
  same co-op server. Summoning between players is not confirmed yet.

Cheats
- The "Cheats" page has cheats (never die, enemies do not see or hear you, Rally never fades,
  control the targeted enemy) and gameplay tweaks (no Rally, camera further away, no camera
  auto-rotation, run with less stick tilt, ragdoll physics). They are game patches for 1.09,
  applied when the game starts.
- The same Cheats page includes player damage, enemy damage reduction, Blood Echoes and movement multipliers, infinite stamina, consumables kept after use and No Fall Damage. These can also change during play from the in-game menu. Revision 8 covers the missing stamina and ordinary Echoes paths. They default to off and require verified game version 1.09 hooks. See docs\cheats.md.
- Experimental FSR Frame Generation (2x) supports SDR and HDR10. NVIDIA DLSS FG/MFG and independent Reflex are available through Streamline 2.14.1, with the supported multiplier checked at runtime. The normal FPS cap counts real frames; an optional total cap has its own drag control and numeric entry. FG is available on Play, Graphics and the in-game menu. NVIDIA gameplay/HDR on a physical RTX remains untested on the build host. The game HUD may show interpolation artifacts. AMD ML FG and FG model presets A/B are not included; see docs\frame-generation.md.

Problems
- Black screen at start: Advanced -> "Clear shader cache", then start again (the first minutes
  stutter while the cache is rebuilt).
- Send user\last_run.log with any bug report. For the shooting crash, enable General -> Diagnostics -> Developer profiling and crash diagnostics before playing. It is off by default and retains separate session folders under the saves folder\diagnostics, including logs, timings, settings, exit code and a crash dump when available. The shooting crash is not yet declared fixed.
- XeSS Super Resolution 3.0.2 is included for supported Intel and other GPUs, with fallback to FSR 3.1 on failure. XeSS FG and NVIDIA Dynamic MFG currently need D3D12 and are not available in this Vulkan port.
- Optional overlay fields show confirmed FG/provider/multiplier and Reflex PC latency. PC latency excludes the display and input device; N/A means no completed driver report is available.

Upscaling
- DLSS: NVIDIA GeForce RTX 20 series or newer with a current driver (Graphics -> Upscaler ->
  DLSS, or the in-game menu). On other GPUs the option is greyed out.
- FSR 3.1 works on every GPU. FSR 4 needs its assets in fsr4_shaders\ (included in this
  package, or Graphics -> "Download FSR 4 assets"); GPUs without the required shader features
  fall back to FSR 3.1 by themselves.

Mods and patches
- Put each mod in its own folder under mods\ (dvdroot_ps4\..., or chr\, parts\, ... directly);
  enable and order them on "Mods & patches". The game files are never changed. Without Windows
  Developer Mode the port links folders with junctions and files with hard links; when the game
  is on another drive, the temporary mod view is made next to the game folder.
- Third-party patches: shadPS4/GoldHEN XML files for 1.09 in patches\.

Credits
- This revision: https://github.com/TatsunaKyo/bloodborne_pc
- Online play: shadp2p by Wozzardman (https://github.com/Wozzardman/shadp2p), shadNet by the
  shadPS4 team, The Hunter's Dream by droogie.
- bbport (the Linux port this is built on): https://github.com/deadinside28/bloodborne_pc
- Windows port: https://github.com/Supermedo/bloodborne_pc
- The full list of projects and patch authors is in README.md (Credits and licenses).
