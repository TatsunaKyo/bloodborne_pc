> Historical/upstream record: statements and test results below describe their original revision or environment. [Current guides](../index.md) · [Current reports](../known-issues.md) · [Published releases](../releases/index.md)

# TatsunaKyo revision 53 — Supermedo 1.9 integration candidate

Merges Supermedo's Windows 1.9 improvements while retaining the existing HDR/Streamline/Encore and launcher features. Adds selectable native Supermedo FSR FG and native DLSS FG for SDR. Native DLSS requires restart and uses an isolated bridge; the original NVIDIA path and explicit RTX 20/30 mod choice remain available.

Repairs the reproduced 56-buffer shader push-layout mismatch and migrates R52 SPIR-V before driver use. Adds persistent Vulkan driver pipeline caching, strict background pipeline compilation/preload, restored cached runtime state, device-address allocation flags and compatible sparse heap fallback. Bounded preupload uses quiet, already-resident CPU data. Integration fixes cover audio, input state, launcher modules and FG cap arbitration.

Windows compilation, production-code simulations, real Vulkan software execution, sanitizers, compiled Tk launcher and ImGui checks are documented inside the archive. No Windows/NVIDIA gameplay was run locally. Cemetery traversal, exact 120-FPS cadence and all reconstruction artifacts are not claimed resolved by these tests.

Read `docs/investigations/2026-10-17-supermedo-integration.md`. Delivery is one complete ZIP plus its SHA256, including runtime dependencies, licenses and source/recovery material.
