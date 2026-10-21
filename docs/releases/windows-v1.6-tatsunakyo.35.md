> Historical/upstream record: statements and test results below describe their original revision or environment. [Current guides](../index.md) · [Current reports](../known-issues.md) · [Published releases](../releases/index.md)

# Revision 35 — smoother NVIDIA FG delivery

Revision 34 finally stopped the flashing coffins in my cemetery test on Windows 11 / RTX 5070 Ti. Movement with NVIDIA FG still felt choppy, even at 60 real + 60 generated FPS, so I have focused this revision on frame delivery. The motion-history correction from R34 stays intact.

I found a race between submitting a frame and starting the next simulation: if the submission thread was interrupted at that boundary, another flip could reuse its NVIDIA frame token. I now reserve the next simulation before releasing the submission lock. Reflex still sleeps outside that lock, allowing the GPU and the previous presentation to progress.

For capped NVIDIA FG in Unlocked mode, Reflex now receives the effective output interval before the next simulation starts. This gives the driver the cap it needs to coordinate rendered and generated frames, instead of holding finished frames behind a second limiter. The normal FPS setting still counts real frames: 60 at x2 targets 120 output; 75 with an optional 130 output cap becomes 65 + 65. Unchanged Reflex options also avoid an unnecessary driver configuration call every frame.

VideoOut takes over during background modes, errors, FG off and cap changes until the current foreground policy is accepted. FSR and fixed game-timing modes keep their existing limiting paths. HDR, the independent caps, saves, settings and the R34 input/history protections remain included.

The new regression runs the production NVIDIA methods and GNM submission boundary against R34. It reproduces the duplicated token, checks the corrected ordering under forced preemption, and covers cap conversion at x2/x3/x4/x6, live changes, focus, errors and FG off. Windows and Linux checks also retain the earlier token, scene-input and object-history regressions.

I have rebuilt the launcher and native components. These checks verify the host code; the improvement in displayed smoothness still needs the same gameplay comparison on my PC. NVIDIA's hardware scheduling means the real-frame graph alone cannot measure every generated frame's display time. The [FG guide](../frame-generation.md) has more detail.

Extract the game ZIP into a new folder and keep your game, saves, mods and settings paths. The Developer ZIP is optional for playing.
