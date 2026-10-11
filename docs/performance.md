# Performance work and optional comparisons

I can remove redundant work that is visible in the code without asking for a profiling capture first. In Revision 10, I removed repeated camera mapping checks, cached unchanged mip bias, avoided repeated object-image read barriers and staggered periodic index scans. The changes and their technical details are in [Quality and performance](quality-and-performance.md). In earlier revisions, I also reused the upscaled display image view and avoided FSR color/interpolation allocations on the NVIDIA FG path.

Overall CPU and GPU utilization do not reveal every bottleneck. One busy thread can be hidden by the CPU average; a GPU can spend time waiting between expensive passes. Lowering input resolution helping FPS means some work scales with pixels, but does not identify the entire cause of a slow scene.

## Comparing a change during play

Use the same save, location, camera direction, output resolution, cap and FG mode. Let shader compilation settle. Compare DLSS Performance/preset L and Ultra Performance separately, keeping each before/after pair on the same settings. Real FPS and generated output FPS should be compared separately. Frame-time spikes matter alongside average FPS.

For more detail, Advanced offers frame statistics and GPU pass timing in the log. Advanced → Diagnostics also offers per-session developer profiling and crash diagnostics. These are optional and add overhead, so leave them off for normal play. Logs are written under the chosen saves folder, or `user/` beside the launcher. The upscaler passes are labeled with their provider.

I kept the default one-frame GPU queue because I want low latency. You can try a larger Frames ahead value if it helps your configuration, but check the extra delay as well. I've reduced the repeated renderer work I found; I still welcome gameplay comparisons from other PCs to see how much that helps in practice.

I test gameplay on my Windows 11 / RTX setup. [Testing and known issues](testing.md) collects that coverage and the remaining checks.
