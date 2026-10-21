# R44 target failure: frame-pipeline investigation

The owner reports all three symptoms remain: repeatable cemetery traversal
hitch, variable FG output cadence and reconstruction/foreground artifacts.
This report replaces the assumption that passing local correctness tests
established a fix for these symptoms. R45 is an investigation build.

## Evidence from the actual run

`last_run(4).log` identifies launcher R44, 16 October 2026 12:25:31 +0200,
RTX 5070 Ti 16 GB, 1920x1080 scene to 3840x2160, DLSS preset L, native FG x2,
output cap 120, real cap 75 reduced to 60 by FG, Reflex on, HDR and Mailbox.
It already uses separate graphics/presentation queues in one family.
The supplied `session(4).json/log` identify R19 on 12 October; they are not
contemporaneous evidence for R44. The new journal markers confirm the new
renderer path in the actual R44 log.

| CPU measurement, submission 2487 | Duration |
| --- | ---: |
| Real-frame interval | 69.88 ms |
| Guest submission interval | 16.70 ms |
| GPU-thread flip interval | 69.56 ms |
| Submission to GPU-thread flip | 56.85 ms |
| Draw-pipe drain overlapping that phase | 49.28 ms |
| Guest waiting for previous submit retirement, overlapping | 41.61 ms |
| Frame preparation after flip | 0.30 ms |
| Setup and enqueue | 0.14 ms |
| Final present and SDK state | 0.08 ms |

These intervals overlap. They cannot be added. The drain is a dependency on
stage B, not an explanation of why stage B takes so long. The 1.30 ms compile
span does not explain a 69.88 ms frame. The nearly 48-second gap is distinct
from this event and must not be treated as the cemetery hitch.

After the initial transitions, steady real-frame averages are 59.974–60.044 FPS;
the recorded SDK-output estimates include 119.459–120.196. Real-frame p95 is
roughly 17.16–17.33 ms. These are host observations, not generated-image display
timestamps. The output estimate counts SDK-confirmed presentations in windows
of at least 0.5 seconds; an estimate alone cannot determine scanout cadence.
A controlled example using the actual counter reports 118.213–121.851 FPS
while its simulated display presents at exactly 120 Hz, with only 0–1 ms CPU
query delivery jitter. This establishes a measurement limitation; it is not
evidence that the owner’s actual display is evenly paced.
Neither the counter nor reported frame rate is clamped to make the result look
fixed. The frame-time tails remain material evidence.

## Why R44 did not establish a target fix

- `BindHelperWanted()` defaults to false. Its TLS snapshot defect is real, but
  that optional helper is not shown active in the owner's launch settings.
- Blocking a 40 ms busy wait reduces waiting-thread CPU use. It does not remove
  the underlying 40 ms task. The controlled CPU result was not a cemetery result.
- The old journal discards every CPU span shorter than 1 ms. Hundreds of shorter
  resource operations can occupy the critical thread without a single reported
  category explaining the time. Generic ordered tasks and deferred Vulkan
  commands also lose the producer operation's name at their thread handoff.

## Renderer/memory audit and upstream comparison

R44 uses the older device-local sparse buffer arenas. `EnsureResident` allocates
physical device memory on demand; `SubmitPendingArenaBinds` calls
`vkQueueBindSparse`. Buffer uploads traverse the guest region table and use
staging/copy workers. Tracked CPU/GPU ownership can require drains and readbacks.
The current Windows parent, Supermedo 1.8.2, still has this architecture; its
new VRAM fallback does not replace it.

The Linux upstream's 0.5-pre4 report describes a different memory module with
host imports, non-sparse VRAM mirrors, selective page-table updates, shared VRAM
budgeting and coherence fixes. It reports 30–70 ms stalls from repeated whole
mirror page-table walks under the mapping lock, and major improvements on its
measured route. This is relevant design evidence, not proof that R44 executes
that exact loop: R44 does not contain that mirror module. The author's Linux
NVIDIA sparse-binding report also cannot establish the same driver behavior on
the owner's Windows/Blackwell system.

A port of that memory model is a credible architectural direction. It needs
Windows host-import capability probing, mapping/allocation lifetime ownership,
CPU/GPU write coherence, retirement, budgeting and portable GPU-completion
checks. Enabling a Linux environment variable in R44 does not implement it.
Importing the upstream tree wholesale would also remove or conflict with this
fork's FG/XeSS/temporal work. It must be isolated behind a backend boundary and
validated against the existing backend before becoming the default.

## Image reconstruction and FG audit

DLSS-SR and FG consume reconstructed camera/object vectors and selected scene
depth. The game did not supply a PC-engine motion-vector contract. Finite matrix
and synthetic shader tests establish mathematical properties, not that every
live pass is the intended camera/depth/color frame. A heavier DLSS model cannot
repair stale, mismatched or incomplete inputs.

NVIDIA's integration guide requires matched dense motion/depth and camera state,
matching frame identity, correct scaling/jitter and valid resource lifetime. It
also recommends input visualization and a HUD-less color resource for quality.
Our FG path preserves depth/motion and tags the final backbuffer; a separate
HUD-less color tag is not currently supplied. That is an audit finding, not
proof that it causes the character halo or the foreground slab.

Streamline issue 115 reports an internal Vulkan FG input race despite the input
completion fence; it remains open at this investigation. The reporter explicitly
says the effect on final FG output is unknown. We must not turn that report into
a diagnosis for this game or introduce unconditional CPU waits on that basis.

## API/reconstruction decision

Keep Vulkan while identifying the actual critical operation. Replacing it with
D3D12 would require new resource/descriptor/command and synchronization backends
and a DXIL shader path alongside the current SPIR-V recompiler. DXC accepts HLSL
and emits DXIL or SPIR-V; that does not provide a drop-in translation of this
entire recompiler and memory model. API replacement also leaves guest-memory
ownership, streaming and temporal provenance to solve.

Choose a new memory backend if evidence identifies residency/page-table/copy
ownership as the dominant cost. Choose a Vulkan-driver workaround or another
API only if actual API timing/driver profiling identifies that boundary.
Do not remove required synchronization merely because its wait is large.

## R45 observation changes and one-run capture

The opt-in CPU flight recorder retains 65,536 spans, including operations under
1 ms, with thread identities and roles. It reports a clipped breakdown of the
actual pre-flip/preparation phases, inclusive totals/peaks/counts and bounded
ring/overflow diagnostics. Ordered draw tasks preserve their caller names;
deferred Vulkan commands preserve producer names until actual execution.
Normal command payloads stay unchanged when recording is off.

Explicit spans cover sparse backing allocation, the sparse queue lock,
`vkQueueBindSparse`, buffer creation, command-chunk acquisition, pending work,
temporal frame advance and object-history/index scans. Existing image, staging,
upload, shader, synchronization and present spans feed the same recorder.

`Capture-NVIDIA-FG.cmd` enables this recorder and the existing exact-input F8
capture without serializing the renderer or changing graphics/cap settings.
It leaves the GPU timestamp profiler off: that profiler ends render passes and
may block for query results, so it is a separate experiment. Reproduce the
cemetery hitch first; then press F8 at the visible halo/foreground artifact and
exit. The capture bundle joins current-run logs/settings to the exact tagged
depth/motion/camera and real backbuffer. Readbacks can affect timing after F8;
those frames must not be used as the clean traversal timing measurement.

The capture does not contain NVIDIA's internally generated image. If the real
backbuffers are clean while the visible generated result is not, an external
video and the SDK validation path are still needed. If CPU spans do not explain
the gap, use Nsight Systems CPU blocked-state/context-switch plus Vulkan tracing
on the owner's hardware. No such trace or target GPU execution is available in
this environment. R45 does not claim any of the three target symptoms fixed.

## Primary sources reviewed

- https://github.com/deadinside28/bloodborne_pc/releases
- https://github.com/deadinside28/bloodborne_pc/blob/master/docs/NVIDIA_MEMORY_MODEL.ru.md
- https://github.com/deadinside28/bloodborne_pc/blob/master/docs/MEMORY_MODULE_PLAN.ru.md
- https://github.com/NVIDIA-RTX/Streamline/blob/main/docs/ProgrammingGuideDLSS_G.md
- https://github.com/NVIDIA-RTX/Streamline/blob/main/docs/ProgrammingGuideReflex.md
- https://github.com/NVIDIA-RTX/Streamline/issues/115
- https://developer.nvidia.com/blog/using-nsight-systems-for-fixing-stutters-in-games/
- https://developer.nvidia.com/blog/vulkan-dos-donts/
- https://github.com/microsoft/DirectXShaderCompiler

The upstream measurements above are attributed to their author; they were not
reproduced on the owner's RTX 5070 Ti. Local execution/packaging checks and target
validation are recorded separately in the single release archive.
