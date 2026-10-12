<!-- crowned-workshop-navigation -->
> Historical document. [The Crowned Workshop current guides](../index.md) · [Current reports](../known-issues.md). This page retains its original context and credits.

# Bloodborne: The Crowned Workshop — Revision 17

I still had assets flashing in front of me and far away in the Hunter's Dream on Revision 16. I kept this revision focused on the data each draw uses. The workshop launcher and seven-tab in-game menu are retained.

## Vertex tables now have their own freshness check

The renderer prepares some draws ahead of time. It checked registers and flattened shader resources before reusing that work, but vertex descriptors come through a separate pointed-to table. The pointer could stay the same while the table changed to another mesh, leaving the prepared inputs wrong for the current draw.

I now compare every effective vertex descriptor before accepting the prepared pipeline and again when binding its vertex buffers. If the table changed, I use the current-data path. This covers mesh addresses, stride, size, formats, swizzles and secondary/instance streams, including instruction offsets and typed overrides.

## CPU DMA waits for earlier source reads

CPU fill/copy could overwrite guest data after the draw thread recorded it but before the Vulkan recorder or copy workers had read it. A private copy batch inside an ongoing draw burst was also still vulnerable. I finish those host reads and earlier ordered signals before the CPU write. GPU-modified buffers and GDS copies keep their GPU-command path.

## A useful comparison if the scene still flashes

Start **Bloodborne.exe** normally first. If the Hunter's Dream still flashes, the ZIP includes:

- **Diagnose-Geometry-Normal.cmd**: your usual renderer settings with a retained diagnostic session.
- **Diagnose-Geometry-Serial.cmd**: one reference run without draw-preparation workers, two-stage draws, deferred Vulkan recording or copy workers. It can reduce FPS. It keeps the same graphics/FG settings and saves, and does not overwrite launcher preferences.

Configure your game folder in the launcher before using these starts, close the game between runs and compare the same position/view. Each run keeps its `session.log` and `session.json` in `diagnostics` under your selected user folder. Those files record the actual thread settings. Diagnostic sessions also report the first stale worker tables rejected by the new checks. Ordinary starts keep the existing opt-in profiling behavior.

## Build and checks

I rebuilt **Bloodborne.exe** and the native Windows components. The vertex regression uses the production guest pointer reader, descriptor layout and pipeline/binding acceptance branches: Revision 16 accepts 1,024 stale pipelines and 1,025 stale bindings; the new code accepts none of those stale inputs. The DMA regression uses the actual draw queue, copy pool, CPU fill/copy branches and completion waits: Revision 16 corrupts 768 of 1,024 snapshots, and the correction preserves all 1,024. Unchanged inputs and GPU/GDS paths are checked too.

The two regressions also run with Address/UndefinedBehavior checks. Launcher diagnostics, preference handling and the update channel are checked again. The package includes the earlier menu/layout, upscaler, pacing and vendor-contract results with their original revision labels.

My gameplay setup is Windows 11 with an RTX 5070 Ti. The remaining flash is confirmed on Revision 16; the same Hunter's Dream view is the next comparison for this build. The command-data tests establish the two code defects and their corrections. I will keep the scene report open until I check the visible result.

Extract the complete ZIP into a separate folder and keep your saves, preferences and mods. You need your own CUSA03173 1.09 files. No game files are included. See [testing and open issues](../testing.md) and [the roadmap](../tatsunakyo-next.md).

Revision by **TatsunaKyo**, based on Super Medo's native Windows port. Existing contributor and vendor credits are retained.
