# Frame Generation and Multi Frame Generation

I added analytical FSR 3.1.6 Frame Generation and an experimental NVIDIA DLSS FG/MFG backend using Streamline 2.14.1 and its production DLSS-G 310.9.1 runtime. I kept FG independent of the upscaler choice and off by default. Select it on Play or **Frames** in the launcher, or in **Frames** in the Insert / L3+R3 menu. A temporal upscaler is needed: DLSS, XeSS, FSR 3.1, FSR 4 or native-resolution TAA. FSR FG is not restricted to AMD cards or FSR upscaling.

## SDR, HDR and scene inputs

HDR support was a requirement for me. Both paths accept SDR and HDR10. FSR captures PQ HDR10 color into linear half-float at 80 nits per unit, runs AMD's real optical-flow and frame-interpolation passes, and encodes the generated frame back to PQ. Highlights are preserved above SDR white. NVIDIA receives the actual SDR or HDR10 swapchain image, copied depth and motion vectors, jitter and camera transforms; HDR is not silently replaced with SDR. I also avoid allocating the full-resolution FSR color and interpolation buffers on NVIDIA's path, keeping only depth/motion copies and a one-pixel descriptor placeholder. Runtime errors appear in the in-game menu and `user/last_run.log`.

## Hardware and current choices

NVIDIA requires a supported RTX GPU, driver and Hardware-accelerated GPU scheduling which you can enable from the Graphics tab in Windows settings. Its API reports the supported number of generated frames; the request is clamped to that capability. The launcher offers 2x through 6x, and unsupported in-game entries are disabled once the device reports its limits. This is fixed-rate MFG. NVIDIA Dynamic MFG, on the other hand, by its own current public integration requires D3D12 and does not support Vulkan ([Streamline 2.14.1 guide](https://github.com/NVIDIA-RTX/Streamline/blob/v2.14.1/docs/ProgrammingGuideDLSS_G.md)). Intel XeSS FG likewise requires D3D12 and as such is not supported; XeSS Super Resolution does support Vulkan and is, in fact, included by taking advantage of SDK 3.0.2 ([Intel guide](https://github.com/intel/xess/blob/v3.0.2/doc/xess_fg_developer_guide_english.md)). AMD's ML FG is not implemented on this path. Missing runtimes or unsupported hardware keep normal real-frame presentation.

## Latency controls

I made Reflex a separate Off, On and On + Boost setting so you can use it with FG off and any upscaler. NVIDIA FG automatically enables low-latency Reflex; Boost remains optional. Simulation, render submission and presentation markers are attached to actual host submissions, and Reflex sleep runs on the submitting thread after releasing the submission lock. It does not sleep on the GPU completion thread. For capped NVIDIA FG in Unlocked mode, I translate the effective real-frame cap into an output interval for Reflex, as described below.

The separate [latency guide](latency.md) covers Reflex, AMD Anti-Lag 2 and the PC-latency readout.

## Real-frame and output limits

I kept the normal FPS limit tied to real game frames. Selecting 75 allows up to 150 output frames with 2x FG, subject to GPU throughput and the monitor. For a separate output limit, **Limit total FPS with Frame Generation** has an optional checkbox, drag control and editable integer field from 30 to 1000. It derives a real-frame ceiling from the negotiated multiplier without raising the game's own ceiling: 75 real FPS plus a 120 total cap at 2x gives 60 real FPS. Integer division can place the total slightly below an indivisible value. Generated frames do not advance physics or game logic. I recommend keeping the real-frame limit at 120 or below because the original game logic can misbehave at extreme rates. The output cap can be set as high as 1000, but the practical rate depends on the GPU, monitor and scene.

For capped NVIDIA FG, I now send the effective output interval to Reflex before the next simulation starts, and let it coordinate the rendered and generated frames. The normal cap still counts real frames: 60 real with x2 means 120 output; 75 real with a 130 output cap means 65 real. VideoOut keeps its existing limiter for FG off, FSR, background modes and any transition where the driver has not accepted the current cap. I also closed a submission race that could assign the same NVIDIA token to two consecutive flips. My latest Revision 35 retest no longer shows the earlier 120-versus-146 choppiness on my 154 Hz / G-SYNC setup, but camera movement and cemetery traversal still show spikes. I am tracking both in [current gameplay evidence](known-issues.md#latest-gameplay-evidence).


## Focus, lifetime and history

Background Pause, 30 FPS and 60 FPS modes disable generation while unfocused. Keep running preserves FG and the optional total cap. History resets after a pause, resolution change, scene reset or SDR/HDR transition. Revision 10 also forwards camera discontinuities and DLSS/XeSS feature recreation to FG, with previous camera values seeded from the current frame. NVIDIA input-completion fences are waited before buffers are reused or released, and generation is drained before focus, fullscreen and swapchain changes.

## Overlay, frame timing and the HUD

The game HUD remains in the interpolation input, so moving text and UI can show artifacts. The port's own FSR overlay/menu is composed after interpolation. On the NVIDIA path those elements are in the final tagged backbuffer. Revision 8 measures NVIDIA output using `numFramesActuallyPresented`, consumed exactly once after each presentation. The menu also shows real FPS separately. The OSD only reports generated output when the counter confirms an active multiplier. Optional FG/provider and PC-latency fields fit on the same line. PC latency comes from completed Reflex reports (simulation start to GPU completion), with N/A for unavailable/stale samples; it excludes the display and input device.

The optional [frametime graph](display-and-overlay.md#reading-the-graph) records real-frame presentation intervals, including with FG active. NVIDIA exposes a generated-output count rather than individual display timestamps, so I keep the graph labeled Real. For generated display cadence, NVIDIA recommends FrameView's displayed-image timing.

My earlier Hunter's Dream capture showed extreme object vectors while the real scene and DLSS output looked normal. I preserved depth before UI passes could reuse it, added ordered world-batch identity and kept each scene's inputs alive through presentation. The later cemetery recurrence needed another correction: Revision 34 checks every pose binding behind shared meshes and avoids positional history for unidentified instance slots. My cemetery test on Windows 11 / RTX 5070 Ti now confirms that the flashing is resolved. Those protections remain in place while I work on smoother FG delivery.

**FG presets A/B remain pending.** I need a supported model-selection path and evidence that it changes the FG model before offering the choice. This is separate from Streamline's UI recomposition option, which needs genuine HUDless color and matching UI color/alpha buffers that this revision does not yet supply. DLSS super-resolution presets E/F/J/K/M/L remain available as before.

## Testing and further work

I test gameplay on my Windows 11 / RTX 5070 Ti PC. I also check the FSR pipeline separately: the actual capture shader and FI/OF passes ran on Lavapipe with Khronos Vulkan validation 1.4.341. Tests cover SDR, depth/motion readbacks, generated pixels, history, resize and ownership. HDR tests check 500/1000/2000-nit decoding, generated highlights above SDR white, PQ re-encoding and HDR-to-SDR reset. The run completed with zero validation errors and warnings. Those headless checks cover the pipeline; desktop presentation and broader hardware results are tracked in [Testing](testing.md) and [current reports](known-issues.md).

I should mention that I initially compared my work to the [AwesomeObserver fork](https://github.com/AwesomeObserver/bloodborne_pc). I quicky decided to do things on my own though, because it's FG implementation is x2 and SDR-only, whereas I find it to be mandatory to support the HDR/MFG/Reflex combination. As such, Revision 10 uses this fork's own integration. Its HUD and timing work still offers useful references for the next steps in [the roadmap](tatsunakyo-next.md), and I invite interested development to take a look.

With the renderer's dependencies installed, build the FSR fixture using `ninja -C out/gpu frame-generation-test`. It needs a Vulkan device and a current `VK_LAYER_KHRONOS_validation`; exit 77 means a prerequisite is unavailable. The Windows package includes `bin/frame-generation-test.exe`. The fixture exercises capture/interpolation separately from the gameplay tests.

The XeSS adapter negotiates required extensions and features before device creation, uses scene depth and pixel motion vectors, and recreates history on resolution changes. Input color is converted through the original sampled view to RGBA16F, preserving sRGB decoding, channel swizzle and HDR highlights. Its API contract and conversion shader pass their regression checks. Intel hardware coverage is tracked on the shared testing page. The optional runtime is unmodified and includes Intel's license.

Revision by TatsunaKyo. Intel XeSS, AMD FidelityFX, [FSR-Vulkan](https://github.com/FireBurn/FSR-Vulkan), NVIDIA Streamline and their MIT/runtime licenses retain their credits. The original port's GPL license applies to the integration.
