# Bloodborne: The Crowned Workshop — Revision 18 diagnostic preview

My Windows 11 / RTX 5070 Ti test still shows flashing assets in the Hunter's Dream on Revision 17, even with draw preparation, the draw pipeline, deferred Vulkan recording and copy workers disabled. I am keeping that result in the rendering investigation instead of treating the previous ordering fixes as the end of it.

This preview adds a way to capture the actual scene entering DLSS and the output from the same frames. It also records depth, camera/object motion and a frame's render-pass/resource trace. These images should show whether the unwanted objects are already in the rendered scene or appear during temporal reconstruction. The capture ends before Frame Generation, so a problem confined to generated frames needs a separate presentation check.

## Capture the affected scene

1. Extract the complete package into its own folder. Configure the game folder in **Bloodborne.exe**, then close the launcher/game.
2. Start **Capture-Flashing-Assets.cmd**, load the Hunter's Dream and press **F8** while the assets are flashing.
3. Keep playing for a few seconds, then close the game. The launcher creates **Flashing-assets-diagnostic.zip** in the latest session under `user/diagnostics`, or under the user folder selected in the launcher. Send that ZIP with a brief description of the view you captured.

One F8 press records eight consecutive frames. Capturing needs temporary disk space and can cause a short hitch. It runs the same serial reference as the confirmed Revision 17 test and retains the selected DLSS preset, FG, HDR and other graphics settings. Launcher preferences and saves are preserved. Ordinary starts keep profiling and capture off.

The package retains the workshop launcher, compact in-game tabs, upscalers, Frame Generation, latency controls and the earlier source-data ordering fixes. **The Hunter's Dream flashing issue remains open.** This release is an investigation preview.

## Build verification

I rebuilt **Bloodborne.exe** and the native Windows game components. Checks execute the production F8 file trigger and frame polling, and exercise the rebuilt launcher's capture environment and ZIP archive. They cover conflicting saved environment settings, preference preservation, exact binary capture bytes, archive contents and a run where F8 was never pressed. The source patch and Windows imports are checked when packaging.

The gameplay result recorded here is my Revision 17 Windows/RTX test. The eight-frame capture still needs to be run on that PC. Earlier graphics/layout tests remain in the package with their original revision labels.

Maintained by TatsunaKyo. Super Medo's Windows port, bbport, shadPS4 and vendor credits remain in the project.
