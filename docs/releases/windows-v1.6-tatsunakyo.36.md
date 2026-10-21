> Historical/upstream record: statements and test results below describe their original revision or environment. [Current guides](../index.md) · [Current reports](../known-issues.md) · [Published releases](../releases/index.md)

# Revision 36 — background audio and lighter cache preparation

Background Pause stopped the game but left the music playing. I have connected the audio device and output threads to the same pause state: the queued sound stays in place, and its clock starts fresh when you return. This also covers starting the game out of focus. The 30/60 FPS background modes and Keep running continue playing sound.

I also removed two avoidable costs during shader preparation. The port no longer checks and creates a shader-patch directory when patching and shader collection are both disabled. Flat cache tables now copy in one operation instead of growing and copying element by element. Their bytes match the previous format exactly, so existing compatible cache records remain usable.

My latest R35 retest no longer shows the earlier 120 FPS choppiness, but I still get spikes while rotating the camera and leaving the cemetery. This revision is another step in reducing unnecessary CPU and disk work. I cannot promise that these changes eliminate those spikes or raise FPS on every setup; comparisons from other users are welcome. I have kept the R34 flashing correction and R35 NVIDIA scheduling intact.

The new audio test reproduces R35's unpaused playback and runs twelve pause/resume cycles with two ports, including startup in the background, retained samples, fresh deadlines, a closed paused port and missing/failed devices. Cache tests compare old/new bytes, cross-read both versions and check malformed input. The enabled shader-patch and collection paths are checked too. Existing NVIDIA token, pose-history, scene-input, focus and cap regressions remain included.

I have rebuilt the Windows launcher and native components. Windows/Linux automated checks and the compiled launcher controls are recorded with the package. The next gameplay check on my Windows 11 / RTX 5070 Ti PC is the same cemetery route and camera rotation; I am keeping that result open until I can compare it.

The package also includes the ZIP date and raw Windows archive-name validation corrections made after R35. Extract into a new folder and keep your game, saves, mods and settings paths. The Developer ZIP is optional for playing.
