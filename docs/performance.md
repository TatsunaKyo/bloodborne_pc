# Performance work and optional comparisons

Renderer review can find redundant work without requiring a profiling capture first. Revision 10 removes repeated camera mapping checks, caches unchanged mip bias, avoids repeated object-image read barriers and staggers periodic index scans. The implemented changes and workload result are in [Quality and performance](quality-and-performance.md). Earlier revisions also reuse the upscaled display image view and avoid FSR color/interpolation allocations on the NVIDIA FG path.

Overall CPU and GPU utilization do not reveal every bottleneck. One busy thread can be hidden by the CPU average; a GPU can spend time waiting between expensive passes. Lowering input resolution helping FPS means some work scales with pixels, but does not identify the entire cause of a slow scene.

## Comparing a change during play

Use the same save, location, camera direction, output resolution, cap and FG mode. Let shader compilation settle. Compare DLSS Performance/preset L and Ultra Performance separately, keeping each before/after pair on the same settings. Real FPS and generated output FPS should be compared separately. Frame-time spikes matter alongside average FPS.

For more detail, Advanced offers frame statistics and GPU pass timing in the log. General → Diagnostics also offers per-session developer profiling and crash diagnostics. These are optional and add overhead, so leave them off for normal play. Logs are written under the chosen saves folder, or `user/` beside the launcher. The upscaler passes are labeled with their provider.

The default one-frame GPU queue favors latency. A larger Frames ahead value may improve overlap on some configurations but can add latency; it is a user choice, not a required performance fix. There is no claimed sewer FPS increase attached to a synthetic cache test.

Gameplay testing is documented once in [Testing and known issues](testing.md), including TatsunaKyo's Windows 11 / RTX setup.
