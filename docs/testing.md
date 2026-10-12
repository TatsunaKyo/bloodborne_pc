# Testing The Crowned Workshop

I test gameplay on my Windows 11 / RTX 5070 Ti PC and keep those results separate from automated checks. Current reports are in [their own page](known-issues.md), and [Compatibility](compatibility.md) records which hardware has gameplay evidence.

## Portable regressions

With Python, Tk/Pillow, a C++ compiler, Vulkan headers and the pinned ImGui submodule available, run `python3 tools/ci_regressions.py`. Add `--gui` under a display or `xvfb-run` for the actual launcher layout/popup tests.

The suite executes settings and updater behavior, altered-package rejection, production renderer branches with recorded calls, real ImGui controls and optional Tk layouts. It needs no game dump. The CI workflow uses the same entry point; private-image cheat tests and hardware gameplay remain separate.

## Windows checks

The manual **Windows build and package** workflow compiles native components and the launcher, executes the CPU regression programs and checks the compiled Windows launcher before assembling a candidate. It pins MSYS2 package checksums and the unchanged vendor runtime baseline. Package validation checks PE imports/exports, binary/runtime hashes, source commit/tree, source patch and SHA256 sidecar.

A successful hosted build does not test a player's graphics driver. FSR/NVIDIA presentation, HDR, latency, focus transitions and affected scenes still need the named hardware results. The first hosted run is pending until the repository's Actions settings enable it; local tests are recorded with their actual environment.

## Reporting a comparison

Use the same scene and settings when comparing revisions. Include the revision, GPU/driver, Windows version, input/output resolution, upscaler quality/model, FG mode, both FPS caps and HDR. The optional graph records real-frame presentation intervals; displayed FG cadence and Reflex PC latency measure different things.

I mark an issue resolved when the relevant result supports it. Old reports, inherited upstream reports, untested hardware and confirmed current regressions should not share one undifferentiated list.

[Historical test records through Revision 21](history/testing-through-21.md) retain the individual regression counts and environments. [Performance](performance.md), [current reports](known-issues.md), [hardware coverage](compatibility.md) and [contributing](../CONTRIBUTING.md) explain the next checks.
