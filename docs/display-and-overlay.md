# Display, FPS and the performance overlay

These settings are shared between the launcher and the Insert / L3+R3 menu. **Customize overlay…** on Play opens **Overlay** at its controls; the main overlay checkbox stays on Play.

## FPS limits

I keep the ordinary cap tied to real game frames. Frame Generation adds display frames while the game continues to simulate at its real rate.

| Real-frame cap | FG mode | Optional output cap | Effective real-frame ceiling |
|---|---|---|---|
| 75 | Off | Off | 75 |
| 75 | x2 | Off | 75, up to 150 output FPS |
| 75 | x2 | 120 | 60, up to 120 output FPS |
| 75 | x2 | 130 | 65, up to 130 output FPS |

Find the two caps in **Frames** in both interfaces. You can type an exact value or drag in small steps. The launcher slider uses relative movement (one pixel per FPS, or four pixels per FPS with Shift) and arrow keys change the value by one. The in-game drag field also supports exact numeric entry beside it. Live changes require **Unlocked** game timing; sessions using a fixed timing patch retain that timing. Auto follows the startup/display policy, and No cap removes the real-frame ceiling. Your choice remains available when you return to the launcher.

The optional **Limit total FPS with Frame Generation** accepts 30–1000 and derives a ceiling from the negotiated multiplier. Integer division can place output slightly below an indivisible value. The GPU, scene and monitor determine the practical rate. I recommend a real-frame cap of 120 or below because the original game's movement, animation and physics timing can misbehave at extreme rates. Generated frames do not advance game logic.

## Performance overlay

The basic overlay shows FPS, average interval and the upscaler. NVIDIA FG output FPS uses the SDK's actual presentation count. The overlay can be turned off independently of the settings menu.

| Optional field | What it shows |
|---|---|
| DLSS preset | The accepted letter, such as `DLSS (M)`, or `K>M` while a change is pending. Driver overrides can still choose a different internal model. |
| Input/output resolution | Actual render and output sizes, for example `1920x1080>3840x2160`. |
| Frame Generation | The confirmed provider/multiplier, or a waiting state until generation is active. |
| PC latency | A completed Reflex simulation-to-GPU report, or `N/A`. [Latency details](latency.md) |
| Frametime graph | The last 240 real-frame presentation intervals, plus the latest time and the highest time still in the trace. |

I keep the optional text on one line. The graph adds a shallow row below it, stays inside the compact overlay, and starts off. Turn on **Show frametime graph in overlay** in the **Overlay** in the launcher or in-game menu.

### Reading the graph

Each point records the interval between successful new game-frame `QueuePresent` returns. The samples stay raw, so a hitch remains visible. The plot adapts its vertical scale to retain the peak; 240 intervals cover about four seconds at 60 real FPS. Failed presentations, an unfocused window and long pauses clear the trace before fresh samples are collected.

With NVIDIA FG, the top FPS number can be 120 while the graph reads about 16.7 ms at 60 real FPS. The label **Real** identifies that real-frame cadence. FSR's extra presents and reused/blank frames are excluded. The graph measures host presentation intervals; GPU render duration and display scanout timing require their own measurements. NVIDIA's [FG guide](https://github.com/NVIDIA-RTX/Streamline/blob/v2.14.1/docs/ProgrammingGuideDLSS_G.md#130-how-to-measure-performance) recommends FrameView's displayed-image intervals when assessing the pacing of generated output.

## Window and background

Choose **Windowed**, **Borderless fullscreen** or **Fullscreen (driver default)** from Play, **Window** in the launcher or the in-game **Window** tab. Borderless uses the monitor's desktop resolution/refresh rate and makes Alt-Tab easier without a display-mode switch.

With **V-sync in borderless** off, I request Immediate presentation for lower queueing; tearing is possible. On requests Mailbox, with FIFO as a fallback. Windows and driver settings affect the final presentation path, so compare these on your system.

| When in background | Behavior |
|---|---|
| Keep running | Retains the foreground policy and FG. |
| Pause game and rendering | Pauses game work, rendering and audio while window events remain responsive; game clocks exclude paused time. |
| Limit to 30 FPS | Uses up to 30 real FPS, respecting a lower foreground cap. |
| Limit to 60 FPS | Uses up to 60 real FPS, respecting a lower foreground cap. |

The foreground policy returns when the window regains focus. FG is suspended during background pause or a background limit. [FG details](frame-generation.md) covers resource ownership and history resets during those transitions.

Pause also stops the audio device and parks new audio output. I keep its queued samples so the music resumes where it stopped, and restart the audio clock when you return. Keep running and the 30/60 FPS modes keep playing audio.
