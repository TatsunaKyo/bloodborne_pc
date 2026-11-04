# Revision 56 — Supermedo 1.9.7 integration

Status: unreleased

This is the source changelog. The latest published binary remains [Revision 55](windows-v1.6-tatsunakyo.55.md); its existing ZIP, tag and checksum are unchanged.

## Upstream and renderer

- Integrate Supermedo Windows through `b48052617a919fc4d6b10ae3395e209c9e94e17a`, covering 443 commits since the previous common baseline.
- Adopt the coherent upstream tracker/cache/rasterizer generation and low-VRAM handling. Supersede the incompatible tracker and sparse arena experiments.
- Integrate parallel pipeline preload, shader-build cache fingerprints, separate driver-cache persistence, native frame-generation completion and upstream gameplay/input/save/online fixes.
- Retain bounded/checksummed Workshop shader records, draining accepted writes, atomic settings and per-session motion-address relocation.
- Preserve nonblocking speculative preparation, sleeping draw drains, ordered copy completion and the disabled shader-patch lookup fast path.

## Features and compatibility

- Integrate FSR 4.1.1/4.1.2 and experimental AMD ML Frame Generation 4.0.1/4.0.2, with capability checks, a launcher list limited to confirmed providers, and fallback distinct from the saved request.
- Keep Workshop HDR FSR/Streamline routes, NVIDIA x2–x6 where supported, DLSS model controls, seven XeSS modes, independent real/output limits, cheats and save/support tools.
- Select one latency owner at startup. Streamline/native family changes and native latency changes require restart; pending provider changes continue with real frames.
- Reconcile launcher, ImGui and native PC Settings provider/quality/cap mappings. Keep independent XeSS quality and live overlay edits when saving from the launcher.
- Add upstream frame/render-latency, memory and load readouts alongside the Workshop compact overlay.

## Launcher, packaging and documentation

- Adopt the upstream simple/expert launcher with Workshop branding. Keep XeSS quality independent, restore the three capture/compare actions, and expose Support Report from Advanced and Log.
- Keep one automatic pre-launch snapshot under the Save Manager lease, migrate the existing backup preference, and preserve imported/legacy backups.
- Keep the updater on exact TatsunaKyo stable assets and require checksum/release identity validation before transactional installation.
- Use one release assembler, include the new capability helper, launcher assets and pinned AMD runtime/source/license closure, and omit local API/debug staging records.
- Refresh the README, current guides, integration map and roadmap. Keep source status separate from the published release and retain dated investigation records.

## Verification and remaining reports

See the [integration evidence](../investigations/2026-11-02-supermedo-197.md). Compilation, recorded API tests, actual Tk construction and software Vulkan have different scope from Windows vendor-driver gameplay.

The cemetery traversal hitch, 119–121-FPS delivery variation, stair halos and transient foreground assets remain open. This source changelog does not declare them fixed. A future binary release must pass the Windows package/launcher checks and ship as one complete ZIP plus its SHA256.

[Integration map](../integration-map.md) · [Current reports](../known-issues.md) · [All releases](index.md)
