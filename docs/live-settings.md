# Change settings while playing

I wanted the added controls to be useful while the game is running. Open **Insert** or **L3+R3**, make the change and continue playing. The launcher and menu use the same saved preferences, so you can return to the launcher without losing your choices.

| Setting | Live behavior |
|---|---|
| DLSS model preset | Applies on the next scene frame; independent of the reconstruction quality/scale. |
| Upscaler, quality and output resolution | Can change live when the session was launched with **Image → Live resolution changes** enabled. Fixed scene sizing may require a restart. |
| FSR FG / NVIDIA FG and supported multiplier | The runtime changes the selected generation path; it waits for valid scene inputs before reporting FG active. |
| Real FPS cap | Applies live with **Unlocked** game timing. A fixed 30/60/etc. timing patch is a startup choice. |
| FG output cap | Applies live alongside the real cap. |
| Reflex / AMD Anti-Lag 2 | Can change live when the device/driver supports the integration. |
| Window mode, borderless V-sync and background policy | Can change during play; foreground settings return after refocus. |
| Overlay visibility, optional fields and frametime graph | Change immediately without closing the game. |
| Runtime cheat choices | Can be enabled/disabled live after the 1.09 hooks are verified. Gameplay reports are tracked separately. |
| Sharpening and reconstruction diagnostics | Change while the temporal reconstruction path is active. |
| English / Russian menu language | Changes immediately, independently of launcher/game language. |
| Save Manager | Backups and restoration are launcher tools that require a closed game. Automatic backup choices apply at the next launch. |

Some choices prepare the game before it starts: **object motion vectors, model detail, game-effect patches, original startup cheats, mods, game timing patches and the live-resolution policy itself**. HDR permission, renderer startup switches and developer profiling are also selected before launch. The menu labels the relevant restart cases; I keep those distinctions explicit rather than promising that every startup patch is a live toggle.

To compare image-quality modes during play, enable Live resolution changes before launching. Fixed scene sizing remains available because it can reduce processing overhead on less powerful hardware. DLSS's model letter and the overlay controls stay live in either mode.

Settings that affect generation or reconstruction may briefly rebuild resources or reset history. An active/pending indication in the menu or overlay distinguishes the requested setting from the mode already running.

[Settings tour](launcher-and-menu.md) · [Upscaling details](upscaling.md) · [Both FPS caps](display-and-overlay.md#fps-limits)
