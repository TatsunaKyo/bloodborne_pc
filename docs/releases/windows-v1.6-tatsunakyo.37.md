> Historical/upstream record: statements and test results below describe their original revision or environment. [Current guides](../index.md) · [Current reports](../known-issues.md) · [Published releases](../releases/index.md)

# Revision 37 — parallel asset reads and NVIDIA FG presets

The hitch at the cemetery exit repeats at the same boundary. I am working on the area-streaming path: R36's cache changes did not establish the cause of that traversal hitch.

On Windows, positioned asset reads previously used a synchronous file object and saved/restored its shared cursor around each request. I added a separate overlapped reader for read-only game assets. Concurrent requests now have independent offsets and completion events, and closing a file waits until its reads finish. Mod links still select the same underlying file; save writes keep their existing path. If Windows cannot open the additional reader, the original read path remains available.

This removes a concrete source of serialization during streaming. I still need to compare the same cemetery crossing on my Windows 11 / RTX 5070 Ti PC before calling its hitch resolved. I have kept the R34 pose-history correction, scene snapshots and fences, and R35 NVIDIA frame scheduling intact.

I also added **NVIDIA FG preset: Default / A / B / C** under **Frames** in the launcher and in-game menu. The choice is applied before the next renderer launch through a dedicated NVIDIA profile for this installation. Default restores the previous FG settings. I keep a recovery journal before changing the driver, and refuse to overwrite conflicting settings or another application's profile.

The in-game menu reports the preset only when NVIDIA's process feedback confirms an evaluated override without an error. Otherwise it says the model is unconfirmed. **C needs NVIDIA's updated beta runtime**: selecting it does not install that runtime. The package retains the signed runtime from the latest public Streamline SDK. [Requirements and implementation](../frame-generation.md#nvidia-fg-presets-a--b--c).

I rebuilt the Windows launcher and native components and ran the local regression and compiled UI checks. The Windows streaming fixture covers concurrent reads, exact bytes, offsets above 4 GiB, EOF and pending-read closure. Profile tests cover restoration and failed/interrupted changes; both menus exercise all four choices. GitHub has not started the hosted run for this source, so I am keeping Windows fixture execution pending. The package records that distinction, along with the open gameplay comparison for C and the cemetery route.

Extract the full Windows ZIP into a new folder and keep your existing game, saves, mods and settings paths. The Developer ZIP is optional for playing.
