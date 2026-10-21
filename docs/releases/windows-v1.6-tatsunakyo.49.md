> Historical/upstream record: statements and test results below describe their original revision or environment. [Current guides](../index.md) · [Current reports](../known-issues.md) · [Published releases](../releases/index.md)

# Windows 1.6-tatsunakyo.49

The supplied R48 capture still has a 40.02 ms traversal interval, with 704 read-only write-watch operations taking 8.337 ms inside 25.033 ms of draw recording. R49 reconstructs eligible Windows write-watch installation as an ordered worker with bounded native-call batching and explicit snapshot/fence/remap dependencies. It overlaps this work where possible while preserving synchronous access grants and watches on already-current images.

Real protected-memory, concurrency and scheduler controls pass, including pre-install guest writes, post-snapshot faults, reused mappings and fences which exclude future requests. A controlled ready batch of 64 contiguous same-view requests becomes one native protection call. Windows cross-build, sanitizers, six compiled-launcher Tk checks and 1960 overlay layouts pass. These checks do not establish a gameplay performance gain. Evidence and tradeoffs: `docs/investigations/2026-10-16-r48-traversal-followup.md`.

One full ZIP plus SHA256 includes runtime, required dependencies/licenses, source, verification and compact recovery. Launch normally; optional traversal capture still works with FG on or off. Original NVIDIA libraries and both matching SR DLL paths remain, with RTX 20/30 mods opt-in.

The cemetery route, output-frame spacing, stairs halo and transient geometry are not verified resolved on Windows/NVIDIA. R49 does not change motion reconstruction or implement Encore NR support. The separate Encore report identifies rejected Vulkan depth capture despite an active FG provider; its NR engine is not running.
