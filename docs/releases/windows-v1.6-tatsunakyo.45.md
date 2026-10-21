> Historical/upstream record: statements and test results below describe their original revision or environment. [Current guides](../index.md) · [Current reports](../known-issues.md) · [Published releases](../releases/index.md)

# Revision 45 — renderer investigation

The owner's R44 run still shows all three reported symptoms. This build does
not claim them fixed. The evidence, upstream comparison, limits of the R44
changes, architecture decision and primary sources are documented in
[the investigation](../investigations/2026-10-16-frame-pipeline.md).

The opt-in CPU flight recorder retains 65,536 spans, including operations below
1 ms, with execution thread/role and the original producer operation's name.
At a hitch it reports clipped pre-flip/preparation counts, totals and peaks,
with explicit overlap and capacity diagnostics. Normal command payloads stay
unchanged when tracing is off. The renderer, graphics settings, frame limiter
and original NVIDIA libraries are retained.

Run `Capture-NVIDIA-FG.cmd`. Reproduce the cemetery hitch first; then press F8
at the halo/foreground artifact and close the game. Use the new session's
`NVIDIA-FG-diagnostic.zip`, under the saves folder's `diagnostics` directory.
It combines the current logs/settings and exact tagged depth/motion/camera
inputs with the corresponding real backbuffers. No files are uploaded.

This run preserves parallel rendering and leaves GPU timestamp profiling off:
that profiler can end render passes and block for query results. Capturing the
images after F8 adds readback work, so use the preceding traversal as the clean
timing reproduction. NVIDIA's internally generated frame is not captured.

The production command-handoff fixture exercises deferred/direct execution,
move-only captures, chunk overflow, caller labels and the disabled path. Trace
checks cover sub-millisecond accumulation, phase clipping, separate threads,
nested spans, category bounds and concurrent ring wrap. Existing synchronization,
frame-token/pacing and exact-readback/export checks are also run. Compilation,
compiled-launcher checks and package closure are recorded separately from
unavailable target Bloodborne/NVIDIA execution in the archive's verification.

Only one complete Windows ZIP and its SHA256 are delivered. Source, research
and compact recovery remain inside that ZIP; no full toolchain copy is added.
