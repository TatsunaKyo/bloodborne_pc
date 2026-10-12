![Bloodborne: The Crowned Workshop — TatsunaKyo](docs/assets/crowned-workshop-header.png)

<h1 align="center">Bloodborne: The Crowned Workshop</h1>

<p align="center">Experience Bloodborne natively on Windows, enhanced with modern rendering technologies, customizable gameplay and a redesigned launcher.</p>

<p align="center">
  <a href="https://github.com/TatsunaKyo/bloodborne_pc/releases/latest"><img src="docs/assets/readme/revision-stable.svg" alt="Revision 21 Stable" height="28"></a>
  <a href="docs/compatibility.md"><img src="docs/assets/readme/windows.svg" alt="Windows 10 / 11" height="28"></a>
  <a href="docs/compatibility.md"><img src="docs/assets/readme/vulkan.svg" alt="Vulkan 1.3" height="28"></a>
  <a href="LICENSE"><img src="docs/assets/readme/license.svg" alt="GPL-2.0+" height="28"></a>
</p>

<table width="100%">
  <tr>
    <td width="50%"><a href="https://github.com/TatsunaKyo/bloodborne_pc/releases/latest"><strong>↓ Download latest&nbsp;↗</strong></a><br>Windows package and checksum</td>
    <td width="50%"><a href="docs/launcher-and-menu.md#installation"><strong>▤ Installation guide&nbsp;↗</strong></a><br>Requirements and setup</td>
  </tr>
</table>

<p align="center"><a href="docs/compatibility.md">Compatibility</a> · <a href="docs/known-issues.md">Current reports</a> · <a href="#roadmap">Roadmap</a> · <a href="docs/index.md">All guides</a> · <a href="docs/releases/index.md">Release notes</a></p>

My revision of [Supermedo's Windows port](https://github.com/Supermedo/bloodborne_pc), built on bbport and the shadPS4 renderer. The aim is to make Bloodborne more comfortable to play on a modern Windows PC, with more graphics choices, better window controls and settings you can change during play. This project would NOT be possible without the original work and the people involved.

The Crowned Workshop is my own place to work on the port. The workshop, lantern and crowned TK emblem are part of that identity; the credit for the game and the original port stays with their creators.

> [!CAUTION]
> NO game files are included. You NEED your own decrypted **Bloodborne CUSA03173, version 1.09** dump, including `eboot.bin` and its original data. Most game patches and the added cheats depend on 1.09.

## Getting started

1. Download the full Windows ZIP from Releases and extract it into a new folder.
2. Open **Bloodborne.exe** and choose your game folder under **Game & files**.
3. Choose your resolution and graphics settings, then press **PLAY**.
4. Press **Insert** or **L3+R3** in-game to change the port's settings.

**Play Bloodborne.exe** starts with your saved options. Saves and shader caches normally live in `user/` beside the launcher; you can choose another saves folder. Keep your existing saves, mods and preferences when updating. Each package includes its SHA256 checksum and **Start-Verified-Launcher.cmd**. [Installation and settings](docs/launcher-and-menu.md)

## What this fork adds

### High-fidelity upscaling support: DLSS, FSR and XeSS

![DLSS, FSR and XeSS: input scene, reconstruction and display output](docs/assets/features/upscaling.png)

I wanted more control over image quality and more choices for people playing on different GPUs. The original port already had DLSS, FSR and TAA; I added **XeSS Super Resolution** and a separate **DLSS model-preset selector**, with the same settings available in the launcher and while playing. **DLSS model changes apply live on the next scene frame**; live quality/resolution changes use [the in-game menu’s Live resolution setting](#live-editing-during-play). The following shows all the upscaling options provided:

| Upscaler | Available option |
|---|---|
| DLSS 3.7, 4 & 4.5 | Quality/render scale plus a separate model preset; requires a RTX GPU. |
| FSR 3.1 | The existing reconstruction path, also used as a fallback if another provider fails. |
| FSR 4 / 4.1.1 | Additional reconstruction paths, available with their shader assets and the required device features. |
| XeSS 3.0.2 | The added Intel Vulkan integration, with seven dedicated quality modes for supported Intel and other GPUs. |
| TAA / native AA | Temporal AA at the scene's native resolution. |

For DLSS, I exposed the following presets exactly as separate choices:

| Preset | Dropdown label |
|---|---|
| Default | Driver default |
| E | E (CNN / legacy) |
| F | F (CNN / legacy) |
| J | J (Transformer 1st gen) |
| K | K (Transformer 1st gen) |
| M | M (Transformer 2nd gen) |
| L | L (Transformer 2nd gen) |

> [!TIP]
> Be warned that XeSS uses different upscaling ratios when compared to DLSS and FSR — you can read more at [Upscalers, presets and XeSS resolution examples](docs/upscaling.md)

### HDR-ready Frame Generation and Multi Frame Generation

![Real game frames and extra display frames, with SDR and HDR10 support](docs/assets/features/frame-generation.png)

Support was added for **FSR Frame Generation (x2)** and **NVIDIA DLSS FG / MFG (x2–x6 modes for supported GPUs)** to improve display smoothness while keeping the game's real-frame limit separate. FG can work with a different upscaler and both paths support **SDR and HDR10**; I wanted HDR users to have the same FG choices. You can activate and adjust FG **live from the in-game menu**, as well as before launch in the launcher. I kept the normal FPS limit tied to real game frames, with or without FG, and added an optional second limit for the complete FG output. This lets you control the game rate and the generated display rate separately. I go more in-depth with the technicalities of the implementation in the following page: [FG setup, hardware requirements and how the integration works](docs/frame-generation.md)

### NVIDIA Reflex and AMD Anti-Lag 2

![Independent latency controls for supported NVIDIA and AMD GPUs](docs/assets/features/latency.png)

I added independent latency controls because choosing an upscaler or turning Frame Generation off should not remove the option to reduce the render queue. Both interfaces keep these controls in **Frames**, alongside FG and the frame limits. I made **Reflex** a separate Off / On / On + Boost choice, so you can use it without FG. Be warned that NVIDIA FG enables Reflex automatically. I also integrated **AMD Anti-Lag 2** through the supported Radeon Vulkan driver interface.

| Control | Choices | Requirements |
|---|---|---|
| NVIDIA Reflex | Off, On, On + Boost | A supported NVIDIA GPU and driver reporting Reflex availability. |
| AMD Anti-Lag 2 | Off, On | A supported Radeon GPU and driver exposing `VK_AMD_anti_lag`. |

> [!IMPORTANT]
> Intel Xe Low Latency (XeLL) was/is planned but XeLL currently does not support Vulkan. You can read more here: [Latency controls, supported hardware and measurements](docs/latency.md)

### Frame limits and background control

![Separate real and output FPS caps, exact number controls and background Pause/30/60 modes](docs/assets/features/fps-limits.png)

I wanted more granular control and to choose the frame rate without fighting a slider that jumps hundreds of frames at the slightest movement. Both interfaces let you **type an exact number** and make small adjustments by dragging. The launcher also supports arrow-key steps and finer dragging with Shift. The real-frame cap can change while playing with Unlocked timing, and your choice is kept when you return to the launcher.

The normal cap controls **real game frames**. The optional **FG output cap** includes the generated frames and works alongside it. A 75 FPS real cap therefore does not prevent x2 FG from displaying up to 150 FPS:

| Real cap | FG | Optional output cap | What the limits allow |
|---|---|---|---|
| 75 FPS | Off | Off | Up to 75 real FPS. |
| 75 FPS | x2 | Off | Up to 75 real and 150 output FPS. |
| 75 FPS | x2 | 120 FPS | Up to 60 real and 120 output FPS. |
| 75 FPS | x2 | 130 FPS | Up to 65 real and 130 output FPS. |

The optional output field accepts **30–1000 FPS**; the negotiated FG multiplier and your system determine what can be reached. I keep the real-frame slider between 30 and 120 because extreme real rates can affect Bloodborne's movement and physics. Generated frames do not advance that logic.

I also added a choice for when you Alt-Tab or leave the game in the background. There is no reason to keep rendering at full speed if you would rather save the power:

| Background mode | What happens while the window is unfocused |
|---|---|
| Keep running | Keeps your normal frame policy and FG. |
| **Pause game and rendering** | Pauses game work and rendering, while the window remains able to receive focus again. |
| **30 FPS** | Limits real background frames to 30, or your lower foreground cap. |
| **60 FPS** | Limits real background frames to 60, or your lower foreground cap. |

FG is suspended during the background pause or limit, and your foreground settings return when you come back. Frame limits are in **Frames** and background behavior is in **Window**, with the same categories in both interfaces. **The caps and background policy can change live.**

[Frame-limit behavior and timing details](docs/display-and-overlay.md#fps-limits) · [Focus, pause and presentation](docs/display-and-overlay.md#window-and-background)

### A compact overlay you can customize

![Keep the basic readout or choose preset, resolution, FG, latency and a small real-frame graph](docs/assets/features/overlay.png)

I wanted the overlay to be useful without covering more of the game than necessary. You can keep the original basic readout, hide it completely, or choose which extra fields you want:

- **DLSS preset letter**, without the longer CNN/Transformer descriptions.
- **Input and output resolution**, so you can see the scene size and reconstructed output.
- **Active FG provider and multiplier**, based on the running mode.
- **Reflex PC latency**, when the driver supplies a valid measurement.
- A small **frametime graph**, with the latest and peak real-frame interval, to make uneven delivery visible.

The optional text stays on one line. The graph adds one shallow row only when enabled, and starts off. Play keeps **Show performance overlay**, with **Customize overlay…** taking you directly to **Overlay** in the launcher; the in-game tab has the same name.

[Overlay fields and how to read the frametime graph](docs/display-and-overlay.md#performance-overlay)

### Borderless fullscreen

![Borderless desktop presentation and optional background pause or frame limits](docs/assets/features/window.png)

I added **Borderless fullscreen** because I wanted to switch between the game and other windows comfortably. It uses the desktop resolution and refresh rate, alongside the original Windowed and Fullscreen choices. You can select it before launch or change window mode while playing.

Borderless has its own **V-sync** choice. Off requests Immediate presentation for lower queueing; On requests Mailbox, with FIFO as a fallback. Windows, your driver and display still affect the final latency. The background Pause / 30 / 60 options above are useful here too, and all these controls live in **Window** in both interfaces.

[Window modes, V-sync and background settings](docs/display-and-overlay.md#window-and-background)

### Temporal stability and renderer optimizations

![Refresh temporal history after a scene change while retaining normal movement history](docs/assets/features/temporal.png)

I've worked on the motion history used by the upscalers and FG, on resetting old history after camera cuts or teleports, and on unnecessary renderer overhead. The aim is to keep moving objects more stable, avoid carrying one scene into another and give ready frames less CPU work to wait behind. Ordinary movement keeps its temporal accumulation so the image can continue to recover detail.

I have made these optimization changes, but I can't guarantee they will increase FPS on different configurations yet. Testing from other users is very welcome. The guides explain the individual changes and comparisons, including the FG inputs and the remaining pacing work.

[Image quality and renderer work](docs/quality-and-performance.md) · [Performance comparisons](docs/performance.md)

### Optional cheats

![Combat and movement multipliers plus optional stamina, consumable and fall-damage controls](docs/assets/features/cheats.png)

I added runtime choices alongside the original startup cheats, so you can adjust them from the launcher or while playing:

| Added choice | Available settings |
|---|---|
| Player damage | Off, x2, x4, x8, x16. |
| Incoming enemy damage reduction | Off, x2, x4, x8, x16; x2 halves received damage without changing the defense stat. |
| Blood Echoes gained | Off, x2, x4, x8, x16. |
| Movement speed | Off, x1.5, x2, x4, x8, x16. |
| Infinite Stamina | Optional toggle. |
| Consumables / ammunition kept on use | Optional toggle; you still need to own the item. |
| No Fall Damage | Optional toggle for normal falls; scripted deaths still apply. |

They start off and share the **Cheats** category in both interfaces. The [current reports](docs/known-issues.md) cover the remaining Echoes multiplier check. The guide explains what each cheat changes and how the runtime verifies its hooks. Startup patches retain their restart requirement.

[Cheat behavior and current limitations](docs/cheats.md)

### The Crowned Workshop launcher

![Play quick choices lead to seven organized settings pages with shared preferences](docs/assets/features/launcher.png)

I redesigned the launcher around my workshop, lantern and crowned TK emblem, and organized the settings so that the visual identity also makes it easier to use and reflects all the changes made with the project. The sidebar separates the seven shared **Settings** pages from the launcher tools, and bordered sections separate related controls within a page.

**Play** keeps the quick choices together, grouped into image, frames and window/overlay. The DLSS model selector appears only when DLSS is selected, XeSS has its own quality selector, and NVIDIA FG shows its multiplier on a separate row. Each complete setting has one home in the detailed pages; Play is a shortcut to those same preferences. **Game & files**, mods, online setup and logs remain launcher tools.

[Launcher tour, category table and screenshots](docs/launcher-and-menu.md#the-launcher)

### A compact and cohesive in-game menu

![Seven matching settings categories, available in English or Russian with Insert or L3+R3](docs/assets/features/in-game.png)

I translated the port's settings menu into **English**, retained Russian, and replaced the long page with **seven tabs**: Image, Frames, Window, Overlay, Cheats, Effects and Advanced. Press **Insert** or **L3+R3** to open it. Close and restart controls stay within reach, with a layout that adapts to the available space.

Those seven categories now match the launcher. If you find Reflex under Frames before launching, you find it under Frames during play too. Sharpening stays in Image, background behavior in Window, and model detail/game effects in Effects. Both interfaces use the same saved preferences, and settings that need a restart tell you so.

#### LIVE editing during play

I designed the added runtime controls to be useful **LIVE, without closing and restarting the game**. Press **Insert** or **L3+R3** to change DLSS model presets, supported FG/latency modes, unlocked frame caps, window/background behavior, runtime cheats or your overlay. Both interfaces keep the same preferences.

For live upscaler quality/output changes, enable **Image → Live resolution changes** before launching. Startup game patches and a few renderer options still require a restart; [the live-settings table](docs/live-settings.md) makes those exceptions clear.

[Shared categories, live settings and restart requirements](docs/launcher-and-menu.md#in-game-settings)

### Optional developer diagnostics

![Optional developer profiling with session logs and crash information](docs/assets/features/diagnostics.png)

I added an opt-in profiler so a crash or performance report can include more than a description of what happened. It keeps a separate session folder with logs, settings, timings and Windows crash details when available. Enable **Advanced → Diagnostics** before reproducing a problem; it starts off for normal play because profiling can add overhead.

[Diagnostics and useful bug reports](docs/performance.md#comparing-a-change-during-play)

The original mod/patch loading, keyboard/controller support, shortcuts, shader-cache tools, game effects and beta online co-op remain available, with their original credits.

## Requirements and test setup

- **Windows 10 1903 or later / Windows 11**, 64-bit, with a current graphics driver.
- **Vulkan 1.3** support. Specific DLSS/FSR 4/XeSS/FG features have additional GPU and driver requirements.
- Around **6 GB of free memory commit** (RAM plus page file), or **10 GB for 1440p/4K** output.
- Your own decrypted **CUSA03173 1.09** game files.

I test the revisions on my **Windows 11 PC with a GeForce RTX 5070 Ti**. This is the main gameplay test configuration for the fork. Automated tests also cover settings, controls, hook behavior, renderer contracts and package contents. Coverage and open problems are collected in [test methods](docs/testing.md) and [current reports](docs/known-issues.md), rather than repeated throughout the documentation. AMD/Intel hardware and other Windows configurations depend on community feedback.

## Roadmap

I am keeping the existing gameplay work active while making the fork easier to maintain:

- **Release reliability:** updater compatibility, verified complete packages, CI and useful report forms.
- **Save Manager:** automatic backups, snapshots, restore with rollback and profiles.
- **PC input:** full remapping, native mouse camera and controller/UI consistency.
- **Ultrawide and HUD:** aspect-aware FOV, interface placement and cinematic handling.
- **Frame pacing and image quality:** real/displayed cadence, shader-cache resilience and HUDless FG.
- **Support and compatibility:** a locally reviewed/redacted report archive and reviewed hardware results.
- **Further cheats and vendor features:** the scoped gameplay/training proposals and supported backend extensions.

[Detailed gameplay roadmap](docs/tatsunakyo-next.md) · [Infrastructure phases](docs/infrastructure-plan.md)

## Help and development

For a bug report, include your GPU, driver, settings, reproduction steps and `user/last_run.log`. For crashes or performance issues, enable the optional diagnostics before reproducing the problem. [Current reports](docs/known-issues.md) lists the remaining checks; [testing](docs/testing.md) explains the recorded results and environments; [the roadmap](docs/tatsunakyo-next.md) covers planned features and priorities.

For black screens, try **Advanced → Clear shader cache**. Rebuilding it can cause initial stutter. Report fork-specific issues here; the [upstream Discord](https://discord.gg/yTMG8c4Bqm) belongs to the original project.

[Windows build instructions](packaging/windows/README.md) · [Publishing a release](docs/releasing.md)

## Credits


This revision is maintained by [TatsunaKyo](https://github.com/TatsunaKyo). The Windows port and original launcher are by [Supermedo](https://github.com/Supermedo). The upstream history, copyright notices and licenses are retained.

Built on [bbport](https://github.com/deadinside28/bloodborne_pc), the native Linux port of Bloodborne by deadinside28, and on the [shadPS4](https://github.com/shadps4-emu/shadPS4) renderer. The original README is in [docs/original-readme](docs/original-readme/README.md).

Online play uses the network and PSN code of [shadp2p](https://github.com/Wozzardman/shadp2p) by Wozzardman (the shadPS4 Bloodborne co-op project), the shadNet server of the [shadPS4](https://shadps4.net) team, and [The Hunter's Dream](https://thehuntersdream.com) server by droogie and its team.

Also used: [NVIDIA Streamline](https://github.com/NVIDIA-RTX/Streamline) (DLSS Frame Generation and Reflex), [Intel XeSS](https://github.com/intel/xess) (Super Resolution), [FSR-Vulkan](https://github.com/FireBurn/FSR-Vulkan) and the AMD FidelityFX SDK (FSR), FSR 4 assets from [FireBurn/Q2RTX](https://github.com/FireBurn/Q2RTX), the DLSS bridge adapted from [IFreemz/shadPS4-Bloodborne-DLSS-FSR](https://github.com/IFreemz/shadPS4-Bloodborne-DLSS-FSR), the [NVIDIA DLSS SDK](https://github.com/NVIDIA/DLSS) (`nvngx_dlss.dll` under NVIDIA's license), [LibAtrac9](https://github.com/Thealexbarney/LibAtrac9), [SDL3](https://github.com/libsdl-org/SDL), [FFmpeg](https://ffmpeg.org), [Dear ImGui](https://github.com/ocornut/imgui), [sirit](https://github.com/shadps4-emu/sirit), [magic_enum](https://github.com/Neargye/magic_enum), [miniz](https://github.com/richgel999/miniz), [xbyak](https://github.com/herumi/xbyak), [wepoll](https://github.com/piscisaureus/wepoll), [cpp-httplib](https://github.com/yhirose/cpp-httplib), [Protocol Buffers](https://protobuf.dev), [OpenSSL](https://www.openssl.org), [miniupnpc](https://miniupnp.tuxfamily.org), [JSON for Modern C++](https://github.com/nlohmann/json), [Vulkan Memory Allocator](https://github.com/GPUOpen-LibrariesAndSDKs/VulkanMemoryAllocator), [MSYS2](https://www.msys2.org) / [LLVM](https://llvm.org), [PyInstaller](https://pyinstaller.org) and [Pillow](https://python-pillow.org). Game patches by Kyo, Lance McDonald, auser1337, illusion, emoose and the Bloodborne community.

NVIDIA, GeForce RTX and DLSS are trademarks of NVIDIA Corporation.

## License

GNU GPL v2 or later ([LICENSE](LICENSE)). Third-party components keep their own licenses (see `licenses\` in the download).
