# Building The Crowned Workshop on Windows

Players can use the ordinary game ZIP without installing Python or a compiler. The optional Developer ZIP keeps source records, regression programs and specialist scripts. Start with [the player guide](README-Windows.txt) and [current documentation](../../docs/index.md). This page is for building the port.

## Verified release candidates

I keep release preparation separate from the older development ZIP command. The **Windows build and package** workflow installs the checksum-pinned package set, builds the native programs and launcher, executes the Windows CPU regressions, checks the compiled launcher and assembles a complete candidate. It does not publish a release.

For the same process in an MSYS2 CLANG64 shell, set `WINPYTHON` to a python.org Python 3.14.8 executable, commit your source changes and run:

```bash
"$WINPYTHON" tools/fetch_windows_dependencies.py
pacman -U --noconfirm out/dependencies/*.pkg.tar.zst
bash build.sh
ninja -C out/gpu frame-limits-test frame-pacing-test background-pause-test temporal-history-test motion-history-test xess-presets-test amd-antilag-test camera-motion-test
set -euo pipefail
mkdir -p out/verification
for test in frame-limits frame-pacing background-pause temporal-history motion-history xess-presets amd-antilag camera-motion; do
  ./out/gpu/${test}-test.exe | tee -a out/verification/native-windows-tests.log
done
bash packaging/windows/package.sh --launcher-only
"$WINPYTHON" -m pip install PyInstaller==6.19.0 Pillow==12.3.0
"$WINPYTHON" tests/test_launcher_updates.py out/pyi-dist/Bloodborne/Bloodborne.exe
"$WINPYTHON" tests/test_launcher_window_settings.py out/pyi-dist/Bloodborne/Bloodborne.exe
"$WINPYTHON" tools/assemble_windows.py --baseline out/dependencies/runtime-baseline.zip --dll-dir "$(cygpath -w /clang64/bin)" --channel stable
```

The baseline contributes unchanged SDK redistributables and their licenses; the workflow replaces the native executables, launcher and project files with the new build. The candidate records its source commit/tree, executable/runtime hashes and dependencies. The validator checks DLL imports, the source patch, package contents and SHA-256 before preparing the publication page. Assembly preserves the unsplit candidate under `dist/complete`, then exports the game and Developer ZIPs with matching sidecars. Release preparation verifies both archives against the same source. Use `--channel preview` for an actual prerelease. See [Releasing](../../docs/releasing.md) for the tag policy and publication steps.

## Development builds

I added the NVIDIA Vulkan FG/Reflex integration in Revision 7 using the included Streamline 2.14.1 declarations. For a usable Windows package, place the matching production `sl.interposer.dll`, `sl.common.dll`, `sl.dlss_g.dll`, `sl.reflex.dll`, `sl.pcl.dll`, `NvLowLatencyVk.dll`, `nvngx_dlssg.dll` and `nvngx_dlss.dll` in `bin/streamline/`. Include NVIDIA's license files and the matching Microsoft Visual C++ runtime dependencies. I bundle these components in the revision ZIP; copying only `bb-probe.exe` is insufficient. Do not substitute the SDK's development DLLs or mix SDK versions. See [the FG guide](../../docs/frame-generation.md) for supported paths and remaining hardware validation.

The port targets 64-bit Windows 10 (1903+) / 11. My gameplay testing is on Windows 11 with an RTX GPU; other configurations are listed separately in [Compatibility](../../docs/compatibility.md).

## Build

Install [MSYS2](https://www.msys2.org) (`winget install MSYS2.MSYS2`), open the
**MSYS2 CLANG64** shell and install the toolchain and libraries (the counterpart of
`shell.nix`):

```bash
pacman -S --needed git patch \
  mingw-w64-clang-x86_64-{toolchain,cmake,ninja,pkgconf,python} \
  mingw-w64-clang-x86_64-{vulkan-headers,vulkan-loader,vulkan-memory-allocator,glslang} \
  mingw-w64-clang-x86_64-{sdl3,fmt,boost,robin-map,xxhash,ffmpeg,zydis} \
  mingw-w64-clang-x86_64-{spirv-tools,spirv-headers,spirv-cross} \
  mingw-w64-clang-x86_64-{protobuf,openssl,zlib,miniupnpc,nlohmann-json}
```

magic_enum, miniz and xbyak (not packaged by MSYS2) are submodules under `gpu/third_party/`.
Then, in the repository:

```bash
git submodule update --init --recursive
bash build.sh                      # out/bb-probe.exe, out/bb-gpu-capabilities.exe
BB_GAME_DIR=F:/path/to/CUSA03173 python run.py
python launcher/bbport_launcher_win.py
bash packaging/windows/package.sh  # dist/bbport-windows/ and .zip: Bloodborne.exe + DLLs
```

`run.py` is the Windows `run.sh` (same variables; works from a plain Windows Python too).
The package freezes the launcher with PyInstaller (a private venv in `out/pyenv`, from a
python.org Python) into `Bloodborne.exe`, which also runs `run.py` (`--run`), the preparation
scripts (`--script`) and the game without the window (`--play`): players need no Python.
`Play Bloodborne.exe` (`packaging/windows/play.c`) is a small native program that runs
`Bloodborne.exe --play` from its folder and waits for it, for players who want to start the
game directly with the saved settings.
`patches.py` applies the 1.09 patches only to a 1.09 game (`BB_FORCE_PATCHES=1` overrides);
`run.py` then runs other versions at 30 FPS with live resolution changes.
From a source tree it adds `C:\msys64\clang64\bin` (or `$MSYS2_ROOT`) to `PATH` for the DLLs.
`bash tools/fetch_fsr4_assets.sh` works in the CLANG64 shell as on Linux.

DLSS (optional): `DLSS_SDK_ROOT=<checkout of github.com/NVIDIA/DLSS> bash
packaging/windows/build_dlss.sh` builds `bbport_dlss.dll` (`gpu/dlss_bridge`, the only code that
uses the NVIDIA SDK, compiled with MSVC 2022) and copies it with `nvngx_dlss.dll` next to
`out/bb-probe.exe`; `package.sh` ships both when present. The renderer loads the bridge at run
time (`vk_dlss.cpp`), adds the Vulkan extensions NGX asks for, and DLSS gets the same inputs as
FSR 3 (scene color, depth, render-pixel motion vectors, jitter). `BB_DLSS=0` turns it off.

The launcher texts are written in English with the Russian beside them; the other languages
are in `launcher/bbport_lang.py` (one list per language in the order of `KEYS`; a missing or
empty text falls back to English). The icon (`launcher/bloodborne.ico`/`.png`) is drawn by
`packaging/windows/make_icon.py` and built into `Bloodborne.exe`, `bb-probe.exe` (the game
window) and `bb-gpu-capabilities.exe`.

## What is different from Linux

| Linux | Windows |
|---|---|
| `mov rax, fs:[0]` rewritten to `gs:[0]`, GS base set with `arch_prctl` | GS is the TEB and cannot move. The loader rewrites the displacement to `gs:[0x1480 + 8*slot]` (the TEB's `TlsSlots[slot]`, same 9-byte instruction) and each guest thread keeps its TCB in that TLS slot. The slot is claimed first thing in `main` (Vulkan drivers take many). |
| One memfd for direct + flexible memory, `mmap(MAP_FIXED)` views | A pagefile-backed section; the PS4 range 64 GiB–1 TiB is reserved as one placeholder and views replace placeholders (`VirtualAlloc2`/`MapViewOfFile3`, as in shadPS4). Partial unmaps split views and restore page protections (GPU tracking). |
| `-no-pie`, heap below 1 TiB | `--disable-high-entropy-va`: heaps and thread stacks stay low and out of the PS4 range. |
| SIGSEGV handler, `sigsetjmp` recovery | Vectored exception handler; `bb_setjmp`/`bb_longjmp` (`src/compat_win.c`) restore all Win64 callee-saved registers without SEH unwinding (guest frames have no unwind data; clang's `__builtin_longjmp` restores a wrong frame pointer on Win64). |
| Guest thread stacks from `runtime_low_map` | Windows allocates them, fully committed (`pthread_attr_setstacksize`): guest code has no stack probes and would skip the guard page. The main thread stack is 16 MiB committed. |
| glibc `nanosleep`, monotonic condition variables | High-resolution waitable timers (`compat_sleep_ns`; winpthreads' sleep rounds to 15.6 ms); semaphore deadlines use `CLOCK_REALTIME` (winpthreads rejects monotonic condition variables). |
| `libbbgpu.so` | `libbbgpu.a`, linked into `bb-probe.exe` by CMake (`gpu/CMakeLists.txt`), with a manifest for UTF-8 paths and long paths. |
| `execlp bash run.sh` (in-game restart) | `run.py` puts its command line in `BB_RESTART_COMMAND`; the new launch waits for the old process (`--after PID`). The launcher keeps the game in a job object. |
| Mod overlay with symlinks | Symlinks when allowed (Developer Mode), else junctions for folders and hard links for files. |

Diagnostics added on the way: `BB_FRAME_DUMP_TRIGGER=<file>` writes the guest display buffer
and the presented image of the next frame to `BB_DUMP_DIR` (raw 32-bit pixels), which also
works for menus and movies.

The Windows path does not use the Linux signal watchdog, userfaultfd tracking (`BB_UFFD`), MangoHud or GCC PGO. The Tk launcher replaces the GTK launcher. Portable CPU regression programs run in Windows CI; the renderer recording and sanitizer harnesses run on Linux where their required APIs are available.
