# Testing The Crowned Workshop

## R56 integration checks

[The integration record](investigations/2026-11-02-supermedo-197.md) identifies the upstream range and separates compiled binaries, production component tests, software Vulkan, and the Windows gameplay checks still open. [R55’s historical record](investigations/2026-10-20-upstream-integration.md) remains attached to the published binary.

On a Linux host, install the dependencies from [Regression checks](../.github/workflows/regressions.yml), then run:

```bash
python3 -m pip install -r tools/requirements-checks.txt
python3 tools/setup_test_headers.py
xvfb-run -a -s '-screen 0 3200x2200x24' python3 tools/ci_regressions.py --gui --vulkan
```

`--gui` runs the current launcher pages and real combobox selections. `--vulkan` also executes the production camera shader on a Vulkan driver; Mesa llvmpipe can run it without a physical GPU. The suite checks updater/archive rejection, save and support tools, settings migration, live controls, provider ownership, shader persistence, transfer and presentation lifetimes, and ImGui controls. It needs no game data.

Build `frame-generation-test` separately from the GPU CMake project. Run it with Khronos validation 1.4.341 or newer and a Vulkan device exposing the required features. The fixture exercises capture, FSR optical flow/interpolation, SDR/HDR and delayed NVIDIA input capture. It does not call the NVIDIA SDK or present to a display. Exit 77 means a prerequisite is missing.

`tests/test_launcher_startup.py` exercises the actual main function in English and Russian, including the `--play` fallback with no game files. Pass the compiled `Bloodborne.exe` to read its embedded launcher code. On Windows the test also starts that executable as a separate process, waits for its window and closes it through the Windows close message. This is distinct from building the native renderer or inspecting Tk source layouts.

## Windows checks

Revision 36 adds `tests/test_audio_background.py` and `tests/test_cache_hotpaths.py` on both hosts. The audio fixture runs the production ports and pause gate with a recorded SDL boundary: startup out of focus, two-port feeding, twelve pause/resume cycles, retained PCM, fresh clock cadence, a closed paused port and silent/failed devices. Its R35 control reproduces the music/output continuing while the game is paused. The cache fixture proves that the old and new serializers produce identical bytes and cross-read both files, including nested containers, strings, floating-point bit patterns, append behavior and malformed lengths. It also executes the production shader-patch lookup with real filesystem operations: disabled features do no path work, while enabled patches and debug collection still load the expected words.

The manual **Windows build and package** workflow compiles native components and the launcher, executes the CPU regression programs and checks the compiled Windows launcher before assembling a candidate. It pins MSYS2 package checksums and the unchanged vendor runtime baseline. Package validation checks PE imports/exports, binary/runtime hashes, source commit/tree, source patch and SHA256 sidecar.

A successful hosted build does not test a player's graphics driver. FSR/NVIDIA presentation, HDR, latency, focus transitions and affected scenes still need the named hardware results. The full candidate workflow is a manual run. GitHub currently reports that workflows on the fork are suspended; [repository setup](repository-setup.md) records how the maintainer can restore them. Local tests and hosted results are recorded with their actual environment.

## Reporting a comparison

Use the same scene and settings when comparing revisions. Include the revision, GPU/driver, Windows version, input/output resolution, upscaler quality/model, FG mode, both FPS caps and HDR. The optional graph records real-frame presentation intervals; displayed FG cadence and Reflex PC latency measure different things.

I mark an issue resolved when the relevant result supports it. Old reports, inherited upstream reports, untested hardware and confirmed current regressions should not share one undifferentiated list.

[Historical test records through Revision 21](history/testing-through-21.md) retain the individual regression counts and environments. [Performance](performance.md), [current reports](known-issues.md), [hardware coverage](compatibility.md) and [contributing](../CONTRIBUTING.md) explain the next checks.

## Support Report and Save Manager

`tests/test_support_report.py` checks bounded collection, missing/malformed logs, credentials and custom paths, optional hardware submissions, ZIP integrity and interrupted exports. `tests/test_save_manager.py` checks complete save/metadata/memory snapshots, retention, rollback, corrupt/unsafe archives, locked writers and processes killed at three restore stages. The native lease fixture exercises the same C guard linked into the game, together with the Python manager.

The two actual Tk dialog tests exercise inspection/export, named snapshots, restoration, source-folder scope and compact/high-DPI layouts. Windows infrastructure CI also executes the real Windows file-sharing cases and the frozen launcher self-test. These checks use disposable fixtures; the maintainer gameplay configuration and evidence remain in [Compatibility](compatibility.md).

## Integration and recovery checks

Portable CI now also runs the twelve existing CPU/provider fixtures through `tests/test_cpu_integrations.py`: real/FG caps, timer phase, background gates, output counts/Reflex reports, raw frametimes, camera/object history, settings, FSR support, XeSS quality/SDK contracts and AMD input/present contracts. It adds the swapchain recovery fixture, which executes the production failure/drain blocks against competing queue work. The recorder suite exercises that fixture on Linux; the Windows workflow runs its own compiled checks.

`tests/test_update_archive.py` exercises the actual updater worker: a rejected checksum does not extract or execute a candidate, while a complete verified package reaches the expected launcher path. Altered binaries, wrong metadata/version, missing runtimes, malformed checksums, Windows aliases and truncated ZIPs are rejected. The frozen Windows runtime also imports the same release/dependency validators. [Code review](code-review-2026-10-13.md) records the findings and remaining hardware comparisons.

<!-- workshop-current-navigation -->
[All current guides](index.md) · [Published releases](releases/index.md) · [Source maintenance](maintenance.md)
