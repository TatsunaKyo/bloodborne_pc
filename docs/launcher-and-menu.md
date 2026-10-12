# Launcher and in-game settings

## Installation

Extract the full Windows package into a new folder and open **Bloodborne.exe**. Select your decrypted Bloodborne CUSA03173 1.09 folder under Game & effects, then choose the resolution and graphics settings on Play. No game files are included.

Saves and shader caches normally live in `user/` beside the launcher. You can select an existing saves folder; keep it and your mods/preferences when updating. **Play Bloodborne.exe** launches with saved settings. The included **Start-Verified-Launcher.cmd** checks the launcher's packaged hash before starting it.

## The launcher

I redesigned it around my workshop, lantern and crowned TK emblem, with slate panels and warm brass accents. The sidebar includes my name, the current version and Super Medo's original port credit.

Play keeps the quick controls together. DLSS's model selector appears when DLSS is selected; XeSS has its own quality selector, and NVIDIA FG has a separate multiplier row. The detailed pages keep the larger settings groups out of the quick panel. **Customize overlay…** opens Display & FPS at the overlay controls.

![The Crowned Workshop launcher](assets/crowned-workshop-launcher.png)

My setup screenshot:

<img width="1949" height="1335" alt="The Crowned Workshop launcher setup" src="https://github.com/user-attachments/assets/865171f3-30a2-41a2-b0d1-0d1e473fe416" />

## In-game settings

Press **Insert** or **L3+R3** to open the menu. I added English and retained Russian; switching the menu language is immediate and independent of the launcher/game language. The launcher retains its original 13 languages.

| Tab | Settings |
|---|---|
| Image | Upscaling, quality, model presets and image tuning. |
| Frames | Real-frame cap, FG and latency controls. |
| Window | Window mode and background behavior. |
| Overlay | Overlay visibility, optional fields and the frametime graph. |
| Cheats | Runtime cheat choices. |
| Effects | Game effect switches. |
| Advanced | Reconstruction diagnostics and less frequently used controls. |

The seven tabs keep the close/restart controls in place. Wide windows use two columns for effects, and the workshop palette carries into the game.

![The Crowned Workshop in-game menu](assets/crowned-workshop-menu.png)

## Live settings and saved preferences

The launcher and menu share `bbport.menu.ini`. Saving from the launcher preserves choices changed during play. The in-game menu saves when closed; settings that need a restart show that explicitly. DLSS presets, overlay choices and unlocked real-frame limits can change during the session. Startup patches retain their restart requirement.

I corrected the ignored-checkbox handling and check real clicks, keyboard/controller navigation and both menu languages. The launcher layout is checked at 100–200% scaling. [Testing](testing.md) records the current checks.

More detail: [Upscaling](upscaling.md) · [Frame Generation](frame-generation.md) · [Display and overlay](display-and-overlay.md) · [Cheats](cheats.md) · [Diagnostics](performance.md)
