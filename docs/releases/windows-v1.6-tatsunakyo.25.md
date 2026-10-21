> Historical/upstream record: statements and test results below describe their original revision or environment. [Current guides](../index.md) · [Current reports](../known-issues.md) · [Published releases](../releases/index.md)

# Bloodborne: The Crowned Workshop — Revision 25

I continued the pacing work by removing another source of contention on the shared Vulkan queue. NVIDIA FG state and latency queries now let the renderer submit its next command buffer while they run. QueuePresent itself stays serialized, and I kept the scene-depth, motion-history and input-completion protections that resolved the earlier flashing.

## Frame delivery

The change affects the presentation wrapper's queue-lock scope. The NVIDIA lifecycle lock and presentation-thread API calls stay in place; I have not switched FG queue-parallelism modes or removed an SDK fence. Swapchain failure still follows the existing recovery path.

The regression executes the actual presentation block with held SDK/queue phases. It reproduces the contention in Revision 24, permits renderer progress in the corrected path and verifies that a queue operation still excludes another queue operation. Windows/Linux CI run the fixture alongside the existing renderer, cache, launcher and save/report regressions.

This removes unnecessary waiting in the code. I would welcome same-scene comparisons with Revision 24, especially in Hunter's Dream with NVIDIA FG/MFG, because the practical frametime benefit depends on the workload and driver.

## Feature illustrations

I applied the approved upscaling, window, history, launcher, in-game menu and overlay figures. The banner and introductory writing stay intact. The new FG GIF uses the actual menu/overlay drawing functions with an illustrative 60-real/120-output example. Its real-frame graph stays at 16.7 ms: generated frames add display updates, while the game still renders 60 frames per second. These values are examples, not a recorded benchmark.

## Installation

Extract the complete ZIP into a new folder and select your existing game and saves locations in **Game & files**. The package includes the recompiled launcher/core, source identity and SHA-256 verification. Your Bloodborne CUSA03173 1.09 files, saves, mods and preferences remain yours.

[Renderer work](../quality-and-performance.md#presentation-queue-scope) · [Frame Generation](../frame-generation.md) · [Current reports](../known-issues.md)
