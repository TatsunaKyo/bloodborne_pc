# Testing The Crowned Workshop

I test gameplay on my Windows 11 / RTX 5070 Ti PC and keep those results separate from automated checks. Current reports are in [their own page](known-issues.md), and [Compatibility](compatibility.md) records which hardware has gameplay evidence.

## Portable regressions

With Python, Tk/Pillow, a C++ compiler, zstd and the pinned ImGui submodule available, first run `python3 tools/setup_test_headers.py`, then `python3 tools/ci_regressions.py`. The setup command verifies and prepares the same pinned Vulkan/VMA declarations used by the recording harnesses. Add `--gui` under a display or `xvfb-run` for the actual launcher layout/popup tests.

The suite executes settings and updater behavior, altered-package rejection, production renderer branches with recorded calls, real ImGui controls and optional Tk layouts. It needs no game dump. The CI workflow uses the same entry point; private-image cheat tests and hardware gameplay remain separate.

## Windows checks

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
