# Testing The Crowned Workshop

## R55 evidence and source maintenance

The published R55 record contains 23 cross-compiled Windows targets, 69 verification logs, six compiled-launcher checks and 1,960 ImGui layouts. These are compilation/component/UI/package evidence. They do not mean the cemetery route, NVIDIA inference or physical display cadence ran on this host. [R55 integration record](investigations/2026-10-20-upstream-integration.md) · [Post-R55 changes](maintenance.md)

Current source checks first-party Python, every first-party Markdown destination/anchor and the revision badge before the portable suite. Install `tools/requirements-checks.txt` in your test environment. `--gui` enables real Tk checks, including Achievements in English/Russian at three scales. `--glm-include`, `--glslang` and `--validator` accept explicit tool paths. Add `--vulkan` only to request actual camera-shader execution on a Vulkan device/ICD; hosted Linux CI explicitly requests it with Mesa installed. The default suite needs no GPU.

The output-selector fixture clicks/reloads all ten choices and checks all 100 output transitions in both languages. The assembler fixture verifies actual ZIP assembly/source replay with fixture Windows/toolchain boundaries. Neither is Windows/NVIDIA gameplay.

I test gameplay on my Windows 11 / RTX 5070 Ti PC and keep those results separate from automated checks. Current reports are in [their own page](known-issues.md), and [Compatibility](compatibility.md) records which hardware has gameplay evidence.

## Portable regressions

With Python, Tk/Pillow, a C++ compiler, GLM headers, zstd and the pinned ImGui submodule available, first run `python3 tools/setup_test_headers.py`, then `python3 tools/ci_regressions.py`. The setup command verifies and prepares the same pinned Vulkan/VMA declarations used by the recording harnesses. Add `--gui` under a display or `xvfb-run` for the actual launcher layout/popup tests.

The suite executes settings and updater behavior, altered-package rejection, production renderer branches with recorded calls, real ImGui controls and optional Tk layouts. It needs no game dump. The CI workflow uses the same entry point; private-image cheat tests and hardware gameplay remain separate.

`tests/test_camera_motion_kernel.py` executes the production GLSL body with float32 GLM vectors and bounded image adapters. Its eight cases cover matched/new/untracked history, overwritten surfaces, invalid vectors and behind-camera points. This catches the arithmetic and history-selection cases without a GPU; `camera-motion-test.exe` remains the Vulkan counterpart.

`tests/test_release_split.py` retains historical split-layout compatibility tests and rejects modern split exports before creating outputs. In the legacy cases it verifies that the original complete candidate is preserved, all its files survive the separation, runtime validation still passes and an interrupted export leaves no partial outputs. It also checks explicit ZIP dates in the local and central headers, writable Windows attributes, reproducible exports with a fixed timestamp and rejection of invalid dates. Release preparation and the published-release tests also check Developer provenance, sidecars, missing/corrupted companions and delayed uploads. The release-integrity and split tests run on Windows as well as Linux.

`tests/test_launcher_startup.py` runs the real main function with frozen startup behavior, in English and Russian, including the `--play` fallback when no game files are configured. Pass the compiled `Bloodborne.exe` to test its actual entry-point bytecode. On Windows, the same test also starts the executable as a separate process through its normal entry point, checks the window and closes it with the normal Windows close message. This catches startup failures that a constructor-only layout test or a `--script` runtime test can miss. All settings and file operations use disposable folders.

## Windows checks

Revision 36 adds `tests/test_audio_background.py` and `tests/test_cache_hotpaths.py` on both hosts. The audio fixture runs the production ports and pause gate with a recorded SDL boundary: startup out of focus, two-port feeding, twelve pause/resume cycles, retained PCM, fresh clock cadence, a closed paused port and silent/failed devices. Its R35 control reproduces the music/output continuing while the game is paused. The cache fixture proves that the old and new serializers produce identical bytes and cross-read both files, including nested containers, strings, floating-point bit patterns, append behavior and malformed lengths. It also executes the production shader-patch lookup with real filesystem operations: disabled features do no path work, while enabled patches and debug collection still load the expected words.

The manual **Windows build and package** workflow compiles native components and the launcher, executes the CPU regression programs and checks the compiled Windows launcher before assembling a candidate. It pins MSYS2 package checksums and the unchanged vendor runtime baseline. Package validation checks PE imports/exports, binary/runtime hashes, source commit/tree, source patch and SHA256 sidecar.

A successful hosted build does not test a player's graphics driver. FSR/NVIDIA presentation, HDR, latency, focus transitions and affected scenes still need the named hardware results. The first hosted Windows build is a separate manual run; portable CI starts automatically on source pushes. Local tests and hosted results are recorded with their actual environment.

## Reporting a comparison

Use the same scene and settings when comparing revisions. Include the revision, GPU/driver, Windows version, input/output resolution, upscaler quality/model, FG mode, both FPS caps and HDR. The optional graph records real-frame presentation intervals; displayed FG cadence and Reflex PC latency measure different things.

I mark an issue resolved when the relevant result supports it. Old reports, inherited upstream reports, untested hardware and confirmed current regressions should not share one undifferentiated list.

[Historical test records through Revision 21](history/testing-through-21.md) retain the individual regression counts and environments. [Performance](performance.md), [current reports](known-issues.md), [hardware coverage](compatibility.md) and [contributing](../CONTRIBUTING.md) explain the next checks.

## Support Report and Save Manager

`tests/test_support_report.py` checks bounded collection, missing/malformed logs, credentials and custom paths, optional hardware submissions, ZIP integrity and interrupted exports. `tests/test_save_manager.py` checks complete save/metadata/memory snapshots, retention, rollback, corrupt/unsafe archives, locked writers and processes killed at three restore stages. The native lease fixture exercises the same C guard linked into the game, together with the Python manager.

The two actual Tk dialog tests exercise inspection/export, named snapshots, restoration, source-folder scope and compact/high-DPI layouts. Windows infrastructure CI also executes the real Windows file-sharing cases and the frozen launcher self-test. These checks use disposable fixtures; the maintainer gameplay configuration and evidence remain in [Compatibility](compatibility.md).

## Integration and recovery checks

Portable CI now also runs the twelve existing CPU/provider fixtures through `tests/test_cpu_integrations.py`: real/FG caps, timer phase, background gates, output counts/Reflex reports, raw frametimes, camera/object history, settings, FSR support, XeSS quality/SDK contracts and AMD input/present contracts. It adds the swapchain recovery fixture, which executes the production failure/drain blocks against competing queue work. Windows CI compiles that fixture with MSVC as well.

`tests/test_update_archive.py` exercises the actual updater worker: a rejected checksum does not extract or execute a candidate, while a complete verified package reaches the expected launcher path. Altered binaries, wrong metadata/version, missing runtimes, malformed checksums, Windows aliases and truncated ZIPs are rejected. The frozen Windows runtime also imports the same release/dependency validators. [Code review](code-review-2026-10-13.md) records the findings and remaining hardware comparisons.

<!-- workshop-current-navigation -->
[All current guides](index.md) · [Published releases](releases/index.md) · [Source maintenance](maintenance.md)
