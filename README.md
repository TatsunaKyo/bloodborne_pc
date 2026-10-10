# Bloodborne for Windows — TatsunaKyo revision

**Revision maintained by [TatsunaKyo](https://github.com/TatsunaKyo), based on the Windows v1.6 port by [Supermedo](https://github.com/Supermedo).**

This fork adds English in-game settings, borderless fullscreen, DLSS preset selection, optional overlay details, cheats and experimental Frame Generation. Revision 9 fixes the Play page's conditional dropdown layout, links directly to overlay customization, and covers the continuous stamina drain used while running. Exact FPS entry, FG controls, optional PC latency, XeSS upscaling and developer diagnostics remain available. See the [release notes](docs/releases/windows-v1.6-tatsunakyo.9.md) for changes and test limits, and the [release guide](docs/releasing.md) for packaging.

The original PlayStation 4 game runs directly on your PC: its own x86-64 code runs natively, and the graphics are translated to Vulkan. No emulator window, no setup scripts: unpack the zip, start `Bloodborne.exe`, pick your game folder and press **PLAY**.

**[Download this revision](https://github.com/TatsunaKyo/bloodborne_pc/releases)** · **[Original Windows port](https://github.com/Supermedo/bloodborne_pc)** · **[Upstream community Discord](https://discord.gg/yTMG8c4Bqm)**

> **No game files are included.** You need your own decrypted dump of Bloodborne (CUSA03173). Version 1.09 is needed for the community patches (60/90/unlocked FPS, resolution, effects); other versions run at 30 FPS. This project is not affiliated with Sony Interactive Entertainment or FromSoftware.

## Features

- **Online play (beta):** messages, bloodstains and wandering ghosts from other hunters through [The Hunter's Dream](https://thehuntersdream.com), and bells and summons through a shadNet server (shadPS4's public one by default).
- **Launcher with every setting in one window**, in 13 languages: English, Arabic, Russian, Spanish, Portuguese, French, German, Italian, Polish, Turkish, Chinese, Japanese, Korean.
- **Updates from the launcher:** when a new version is out it tells you, and **Update** installs it. This revision checks releases from TatsunaKyo's fork and accepts only its Windows revision packages. Your saves, settings and mods are kept.
- **NVIDIA DLSS** on GeForce RTX cards (RTX 20 series and newer).
- **AMD FSR 3.1 and FSR 4** upscaling, plus native-resolution TAA.
- **Experimental Frame Generation:** analytical FSR 3.1.6 in SDR/HDR10, NVIDIA DLSS FG/MFG through Streamline 2.14.1, independent Reflex, and an optional total FPS cap. NVIDIA desktop gameplay still needs hardware testing; see [the FG guide](docs/frame-generation.md).
- **Unlocked frame rate** with a frame cap (up to 120 by default), or 30/60/75/90 FPS.
- **Output resolutions** from 720p to 4K, presets from Native AA to Ultra Performance.
- **Cheats page:** never die, stealth, silent footsteps, Rally that never fades, enemy control, and gameplay tweaks (camera distance, no camera auto-rotation, easier running, ragdoll physics).
- **Game effects** on and off: chromatic aberration, depth of field, motion blur, SSAO, the game's own AA, dynamic light shadows, screen-space reflections, model detail.
- **Mods and third-party patches**, loaded without changing your game files.
- **Add to Steam** puts the game in your Steam library in one click.
- **`Play Bloodborne.exe`** starts the game straight away with your saved settings (good for a desktop shortcut).
- **Controller and keyboard**, an in-game settings menu (Insert or L3+R3), name entry on screen, a desktop shortcut, and a button to clear the shader cache.

## Requirements

- Windows 10 (1903 or later) or Windows 11, 64-bit
- A graphics card with Vulkan 1.3 and a current driver
- About 6 GB of free memory (RAM + page file), 10 GB for 1440p or 4K output
- DLSS: NVIDIA GeForce RTX 20 series or newer

Nothing else to install: everything the game needs is in the zip.

## How to play

1. Download the zip from [Releases](https://github.com/TatsunaKyo/bloodborne_pc/releases) and unpack it anywhere.
2. Start `Bloodborne.exe`.
3. On **Game & effects**, choose your game folder (the one with `eboot.bin`).
4. Press **PLAY**.

In the game, **Insert** (or **L3+R3** on a controller) opens the settings menu. The in-game menu defaults to English. Its **Menu language** selector switches between English and Russian immediately; the choice is saved in `bbport.menu.ini` as `menu_language=en` or `menu_language=ru`. This setting is independent of the launcher and game languages. The same menu's **Window mode** selector changes the window immediately. **Borderless fullscreen (low latency)** uses the current monitor's desktop resolution and refresh rate, with no display mode switch or automatic minimization on focus loss. On Windows, it requests non-disruptive Vulkan presentation through `VK_EXT_full_screen_exclusive` when the driver supports it. An opaque, desktop-sized swapchain allows Windows/driver independent flip; the actual presentation path and latency depend on the system and should be measured there. Borderless defaults to **Immediate** presentation (no V-sync wait or presentation queue; tearing is possible). **V-sync in borderless** selects Mailbox, with FIFO as the compatibility fallback. Without Immediate support the low latency mode also tries Mailbox before FIFO. The renderer's existing one-frame GPU queue limit is retained (`BB_FRAMES_AHEAD` overrides it). The launcher's **Play** page also has a **Window mode** selector for Windowed, Borderless fullscreen and Fullscreen (driver default). **Display & FPS** includes the same selector, **V-sync in borderless** and **In-game menu language**. These controls share `bbport.menu.ini` with the in-game menu; saving launcher settings preserves changes made during the game. **Launcher setting** in-game uses the launcher's saved window mode. Existing launcher preferences with only a fullscreen checkbox are migrated automatically. `BB_WINDOW_MODE=windowed|borderless|fullscreen|launcher` overrides the saved choice at startup.

**DLSS render preset** is available in the launcher's Play and Graphics pages and in the R3+L3 / Insert menu when DLSS is selected. Choose Default (driver), E/F (CNN / legacy), J/K (Transformer 1st gen) or M/L (Transformer 2nd gen). On Play, the entire preset row appears only with DLSS selected; in Graphics, the selector stays visible and is disabled for other upscalers. Switching to another upscaler preserves the saved preset. This is separate from the Quality/Balanced/Performance setting and does not change render resolution. In-game changes wait for submitted GPU work and recreate the DLSS feature on the next frame, without restarting the game. Removed and reserved NVIDIA preset values are excluded. `BB_DLSS_PRESET=default|e|f|j|k|l|m` overrides the saved hint at startup.

**Show performance overlay** in Play, Graphics, Display & FPS and near the top of the in-game menu controls the top-right OSD. Hiding it leaves the settings menu accessible. Play's **Customize overlay…** link opens Display & FPS, where you can choose preset, resolution, FG and PC latency details independently. **Show DLSS preset in overlay**, also available in Graphics and the in-game menu, adds only the preset letter on the original FPS/frame-time/upscaler line: `DLSS (M)`. The initial setting is off, preserving the original basic overlay. The descriptions such as Transformer generation and CNN / legacy remain in the preset dropdowns. With DLSS enabled and this option on, the OSD displays the preset requested by the currently created NGX feature; `DLSS (K>M)` means K is active and M is pending. Default is shown as `Default`, and `-` means no accepted DLSS feature yet. NVIDIA driver/profile overrides may choose a different internal model; this readout confirms the application's accepted feature configuration, rather than independently identifying NVIDIA's model. These preferences share `bbport.menu.ini`, so cached launcher writes do not undo changes made in-game. Existing `show_fps` settings in `bbport.ini` are migrated automatically.

**Show input/output resolution in overlay**, in Display & FPS and the in-game menu, adds the current scene render and output sizes to that same line, for example `854x480>1920x1080`. It starts disabled and is independent of the DLSS preset readout. The OSD fits the extra information in a compact width and scales its font down by at most 15%; it does not add another row. Output means the completed game frame, before the window's final scaling or letterboxing.

**When in background**, in Display & FPS and the in-game menu, offers Keep running, Pause game and rendering, Limit to 30 FPS, and Limit to 60 FPS. Keep running is the default. Pause stops game submissions and presentation at frame boundaries while the window continues handling activation and close events. Guest clocks exclude the pause. Background caps preserve a lower foreground cap and restore it when you return.

The choice is saved in `bbport.menu.ini` as `background_mode=run|pause|30|60`. The launcher also offers 75 FPS, using the variable frame-time patch with a native 75 FPS cap.

The [cheats](docs/cheats.md) are available from the launcher and the in-game menu: damage, enemy damage reduction, Blood Echoes and movement multipliers, infinite stamina and consumables kept after use. All are off by default and require verified 1.09 hooks; revision 7 corrects their player lookup and loading guard. Experimental [FSR/NVIDIA Frame Generation and independent Reflex](docs/frame-generation.md) are available in Graphics and the in-game menu. FG presets A/B and further gameplay validation remain on [the revision roadmap](docs/tatsunakyo-next.md).

Keyboard: WASD move, arrows camera, Space Cross, Left Shift Circle, E Square, Q Triangle, 1/3 L1/R1, R/F L2/R2, Z/C L3/R3, I/K/J/L d-pad, Enter Options, Tab touchpad.

## Playing online (beta)

1. Register a shadNet account at [shadnet.shadps4.net](https://shadnet.shadps4.net).
2. In the launcher, open **Online co-op**, tick **Play online** and enter your account name (not your email) and password.
3. Press **Test connection**: all three lines should say "reachable". Then press **PLAY** and choose online at the title screen. The Hunter's Dream welcome message means you are online.

Everyone you want to play with needs game version 1.09 and the same co-op server. A private shadNet server (from the [shadp2p](https://github.com/Wozzardman/shadp2p) project) works too: put its address in **Server address**.

## Known issues

- The character preview on the character creation screen stays empty. The character is created correctly and looks right in the game.
- Some AMD graphics cards still crash when the game world loads; fixes are in progress.
- Online play is new. Messages, bloodstains and ghosts work; summoning other players with the bells has not been confirmed yet. Please report how it goes on Discord.
- Above about 120 FPS the game's movement slows down (a limit of the game itself): keep the frame cap at 120 or lower.

## Problems and feedback

When reporting a problem with this revision, include `user\last_run.log` from the game folder, your graphics card, driver version and the steps that trigger it. The [upstream community Discord](https://discord.gg/yTMG8c4Bqm) is maintained by the original project; check whether the problem also occurs in the original Windows v1.6 build before reporting it upstream. If the game shows only a black screen, try **Advanced → Clear shader cache** first.

## Building from source

See [packaging/windows/README.md](packaging/windows/README.md): MSYS2 CLANG64, `bash build.sh`, then `bash packaging/windows/package.sh`. DLSS is built separately with `packaging/windows/build_dlss.sh`.

## Credits

This revision is maintained by [TatsunaKyo](https://github.com/TatsunaKyo). The Windows port and original launcher are by [Supermedo](https://github.com/Supermedo) Mohammed Albarghouthi. The upstream history, copyright notices and licenses are retained.

Built on [bbport](https://github.com/deadinside28/bloodborne_pc), the native Linux port of Bloodborne by deadinside28, and on the [shadPS4](https://github.com/shadps4-emu/shadPS4) renderer. The original README is in [docs/original-readme](docs/original-readme/README.md).

Online play uses the network and PSN code of [shadp2p](https://github.com/Wozzardman/shadp2p) by Wozzardman (the shadPS4 Bloodborne co-op project), the shadNet server of the [shadPS4](https://shadps4.net) team, and [The Hunter's Dream](https://thehuntersdream.com) server by droogie and its team.

Also used: [FSR-Vulkan](https://github.com/FireBurn/FSR-Vulkan) and the AMD FidelityFX SDK (FSR), FSR 4 assets from [FireBurn/Q2RTX](https://github.com/FireBurn/Q2RTX), the DLSS bridge adapted from [IFreemz/shadPS4-Bloodborne-DLSS-FSR](https://github.com/IFreemz/shadPS4-Bloodborne-DLSS-FSR), the [NVIDIA DLSS SDK](https://github.com/NVIDIA/DLSS) (`nvngx_dlss.dll` under NVIDIA's license), [LibAtrac9](https://github.com/Thealexbarney/LibAtrac9), [SDL3](https://github.com/libsdl-org/SDL), [FFmpeg](https://ffmpeg.org), [Dear ImGui](https://github.com/ocornut/imgui), [sirit](https://github.com/shadps4-emu/sirit), [magic_enum](https://github.com/Neargye/magic_enum), [miniz](https://github.com/richgel999/miniz), [xbyak](https://github.com/herumi/xbyak), [wepoll](https://github.com/piscisaureus/wepoll), [cpp-httplib](https://github.com/yhirose/cpp-httplib), [Protocol Buffers](https://protobuf.dev), [OpenSSL](https://www.openssl.org), [miniupnpc](https://miniupnp.tuxfamily.org), [JSON for Modern C++](https://github.com/nlohmann/json), [Vulkan Memory Allocator](https://github.com/GPUOpen-LibrariesAndSDKs/VulkanMemoryAllocator), [MSYS2](https://www.msys2.org) / [LLVM](https://llvm.org), [PyInstaller](https://pyinstaller.org) and [Pillow](https://python-pillow.org). Game patches by Kyo, Lance McDonald, auser1337, illusion, emoose and the Bloodborne community.

NVIDIA, GeForce RTX and DLSS are trademarks of NVIDIA Corporation. The icon is original artwork.

## License

GNU GPL v2 or later ([LICENSE](LICENSE)). Third-party components keep their own licenses (see `licenses\` in the download).
