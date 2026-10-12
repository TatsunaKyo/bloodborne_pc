# Reflex and AMD Anti-Lag 2

I added independent latency controls because choosing an upscaler or turning Frame Generation off should not remove the option to reduce the render queue. The launcher exposes them in Graphics; the in-game menu has them under Frames.

| Control | Choices | Requirements |
|---|---|---|
| NVIDIA Reflex | Off, On, On + Boost | A supported NVIDIA GPU and driver reporting Reflex availability. |
| AMD Anti-Lag 2 | Off, On | A supported Radeon GPU and driver exposing `VK_AMD_anti_lag`. |

## NVIDIA Reflex

Reflex can run without DLSS upscaling or FG. NVIDIA FG automatically uses low-latency Reflex because the integration requires it; Boost is still a separate choice. I attach simulation, render-submission and presentation markers to the actual real frame, and run Reflex sleep before the next simulation starts. The completion thread and submission lock stay free during that sleep so earlier work can finish.

The SDK's display-rate limiter stays disabled. The normal cap controls real game frames, and the optional FG cap derives its real-frame ceiling from the negotiated multiplier. This keeps the two caps working together.

**Show PC latency in overlay** displays a completed Reflex report, from simulation start to GPU completion. It shows `N/A` when no valid report is available, and excludes the monitor and input-device delay. That number is separate from the frametime graph.

## AMD Anti-Lag 2

I negotiate the driver extension before creating the Vulkan device. When supported and enabled, the adapter paces the CPU before the game samples input and carries that input ID to the matching real presentation. If FSR FG adds an intermediate frame, it does not consume the real frame's marker. Unsupported hardware leaves the control unavailable rather than substituting a different latency feature.

The adapter's recorded-call checks cover capability negotiation, input/present matching, lifetimes and presentation progress during an input wait. My gameplay PC has an RTX 5070 Ti, so I need Radeon users to test the actual driver path. Anti-Lag 2 does not supply the overlay with a Radeon latency measurement.

## Other latency features

Intel XeSS Low Latency remains separate work. The XeSS 3.0.2 runtime integrated here provides Super Resolution through Vulkan; the published XeLL/FG interface in that SDK does not provide the Vulkan path needed by this renderer. I do not expose a toggle that has no working backend.

I keep the default one-frame GPU queue for lower latency. Larger **Frames ahead of the GPU** values may help throughput on some systems, but compare the response as well as the FPS. [Display settings](display-and-overlay.md) explains the window/presentation choices.

Vendor references: [NVIDIA Reflex integration guide](https://github.com/NVIDIA-RTX/Streamline/blob/v2.14.1/docs/ProgrammingGuideReflex.md), [AMD Anti-Lag Vulkan extension](https://docs.vulkan.org/refpages/latest/refpages/source/VK_AMD_anti_lag.html), [Intel XeSS 3.0.2 documentation](https://github.com/intel/xess/tree/v3.0.2/doc). Gameplay coverage and open reports are in [Testing](testing.md).
