Bloodborne: The Crowned Workshop — Windows
Maintained by TatsunaKyo, based on Super Medo’s native Windows port and bbport/shadPS4.

Start here

Extract the complete ZIP into a new folder, open Bloodborne.exe, and select your decrypted CUSA03173 1.09 game folder in Game & files. No game files are included. Keep your existing saves, settings and mods. You can choose the saves folder; the normal default is user\ beside the launcher. The matching SHA256 file verifies your download. Source, release notes and compact build recovery are inside this same ZIP; no separate Developer package is needed.

Windows 10 1903+ / Windows 11, 64-bit, Vulkan 1.3 and a current graphics driver are required. Individual upscalers/FG/latency features have their own hardware requirements. See docs\compatibility.md and the provider guides; unverified hardware is not automatically incompatible.

Live settings

Insert or L3+R3 opens the port’s menu. Both interfaces use Image, Frames, Window, Overlay, Cheats, Effects and Advanced. DLSS model presets, supported FG/multiplier and latency choices, unlocked real/FG output caps, window/background policy and optional overlay fields can change while playing. Preset letters and both resolutions can appear on the compact overlay; the optional real-frame graph adds a small row.

For live changes to upscaler quality/output resolution, enable Image → Live resolution changes before launch. Fixed sizing is still available for lower processing overhead. Object-motion vectors, model detail, effect/startup patches, mods, timing patches, profiling and several startup switches require a restart. The exact list is in docs\live-settings.md.

Frames keeps the ordinary cap tied to real game frames and offers a separate generated-output cap. Both accept exact numbers; dragging makes small changes. Window keeps background Keep running / Pause / 30 / 60 choices. FG is suspended under background pause/limits and the foreground policy returns on refocus.

Input, mods and online

Keyboard fallback: WASD move, arrows camera, Space Cross, Left Shift Circle, E Square, Q Triangle, 1/3 L1/R1, R/F L2/R2, Z/C L3/R3, I/K/J/L d-pad, Enter Options, Tab left touchpad, Backspace right touchpad. Native mouse look/full remapping remain planned.

Mods & patches retains the original folder/mod-order and 1.09 XML patch support. Use each mod’s game-relative directories. Online co-op remains the inherited beta integration; its account settings live in Online co-op. Keep account details out of public reports.

Diagnostics and help

Advanced → Diagnostics enables optional per-session profiling/crash capture before launch. It starts off. Review logs before sharing; raw dumps can contain private memory. Current reports are in docs\known-issues.md, hardware coverage in docs\compatibility.md and test methods in docs\testing.md. Old reports and past checks are kept in the history pages, not presented as all-current failures.

Documentation and roadmap

README.md introduces the added features. docs\index.md links installation, live editing, graphics, FG, latency, caps, overlay, cheats, diagnostics and build/release guides. docs\tatsunakyo-next.md keeps Save Manager, input, ultrawide/HUD and pacing work alongside the separate infrastructure plan.

Credits and licenses

The full project/community credits are retained in README.md. Original copyright notices and third-party runtime licenses are included. The launcher, shared settings and update channel belong to this TatsunaKyo fork; game and upstream work keep their original authorship.
