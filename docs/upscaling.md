# DLSS, FSR and XeSS upscaling

![DLSS, FSR and XeSS: input scene, reconstruction and display output](assets/features/upscaling.png)

I wanted more control over image quality and more choices for people playing on different GPUs. The original port already had DLSS, FSR and TAA; I added **XeSS Super Resolution** and a separate **DLSS model-preset selector**, with the same settings available in the launcher and while playing.

| Upscaler | Available option |
|---|---|
| DLSS 3.7, 4 & 4.5 | Quality/render scale plus a separate model preset; requires a RTX GPU. |
| FSR 3.1 | The existing reconstruction path, also used as a fallback if another provider fails. |
| FSR 4 | Available with its shader assets and the required device features. |
| XeSS Super Resolution 3.0.2 | The added Intel Vulkan integration, with seven dedicated quality modes for supported Intel and other GPUs. |
| TAA / native AA | Temporal AA at the scene's native resolution. |

For DLSS, I exposed the following presets exactly as separate choices:

| Preset | Dropdown label |
|---|---|
| Default | Driver default |
| E | E (CNN / legacy) |
| F | F (CNN / legacy) |
| J | J (Transformer 1st gen) |
| K | K (Transformer 1st gen) |
| M | M (Transformer 2nd gen) |
| L | L (Transformer 2nd gen) |

The letter selects the model hint; **Quality / Balanced / Performance / Ultra Performance** still controls the input resolution. I put the selector in **Play**, **Graphics** and the in-game menu so you can try another preset without restarting the game. Play shows it only with DLSS selected; Graphics disables it with another upscaler. Your saved choice stays available when you return to DLSS.

I gave **XeSS its own quality dropdown** on Play, in Graphics and in the in-game menu. It appears when you select XeSS and includes Ultra Quality Plus and Ultra Quality. I keep your XeSS choice separate from DLSS/FSR quality, so switching upscalers does not overwrite it.

The ratios below divide each output dimension to get the input size. These are the options used by this fork; XeSS uses Intel's modern quality ratios, so the same label can render fewer pixels than the DLSS/FSR option. The renderer rounds the resulting dimensions to even pixels for the game's half-resolution effects.

| Quality option | DLSS / FSR ratio | XeSS ratio | XeSS input → 1080p | XeSS input → 1440p | XeSS input → 4K |
|---|---|---|---|---|---|
| Native AA | ×1.0 | ×1.0 | 1920 × 1080 | 2560 × 1440 | 3840 × 2160 |
| Ultra Quality Plus | — | ×1.3 | 1476 × 830 | 1970 × 1108 | 2954 × 1662 |
| Ultra Quality | — | ×1.5 | 1280 × 720 | 1706 × 960 | 2560 × 1440 |
| Quality | ×1.5 | ×1.7 | 1130 × 636 | 1506 × 848 | 2258 × 1270 |
| Balanced | ×1.7 | ×2.0 | 960 × 540 | 1280 × 720 | 1920 × 1080 |
| Performance | ×2.0 | ×2.3 | 834 × 470 | 1114 × 626 | 1670 × 940 |
| Ultra Performance | ×3.0 | ×3.0 | 640 × 360 | 854 × 480 | 1280 × 720 |

I preserve the input resolution when migrating an older XeSS setting: the old shared Quality option becomes XeSS Ultra Quality, for example. Live resolution mode applies a new choice on the next frame and resets temporal history. If you use the startup resolution patch, the new choice is saved for the next launch; the in-game menu shows that a restart is needed. Intel's [XeSS integration guide](https://github.com/intel/xess/blob/main/doc/xess_sr_developer_guide_english.md) explains the modern and legacy mappings.

The output columns above mean **1920 × 1080**, **2560 × 1440** and **3840 × 2160**, respectively.

I do not currently own an Intel GPU, so I would especially appreciate XeSS results from people who can try it on Intel hardware. The package includes the vendor runtimes and their licenses, and the renderer logs a reason if a provider fails and falls back to FSR 3.1.
