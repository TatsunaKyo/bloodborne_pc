# Windows R46 — sparse backing allocation and reliable trace export

R45 traces locate a concrete part of the recurring traversal hitch in the draw-recording thread: one 65.32 ms real interval contains 261 `vkAllocateMemory` calls totaling 24.393 ms. R46 pools small physical sparse-memory allocations instead of allocating once per newly discovered mesh range. Sparse guest residency, data uploads and submission ordering are retained. Allocation failures fall back to the former exact-size request when possible.

The new `Capture-Traversal.cmd` works with FG on or off and needs no F8 press. It saves `Traversal-diagnostic.zip`. The NVIDIA image-capture command also saves a logs-only ZIP when there are no images; the archive explicitly distinguishes missing images from a captured sequence. GPU timestamp profiling stays off in both modes.

The optional RTX 20/30 FG integration keeps Neural Rendering off in new configurations and does not install `nvngx_dlssnr.dll`. The separate Encore NR hash/version rejection and reported NR crash do not establish an FG failure or a preset-C cause. RTX 40/50 retain the original NVIDIA path.

See [the capture follow-up](../investigations/2026-10-16-r45-capture-followup.md) for the measured spans, implementation, test controls and limits. This build does **not** claim that the cemetery route, 119–121 output fluctuations, halo or foreground geometry have been verified resolved. Windows cross-compilation and CPU/recording-backend tests are distinct from a Bloodborne/NVIDIA gameplay run.

Distribution is one complete ZIP plus its SHA256 sidecar, including source, licenses, verification and compact build recovery.
