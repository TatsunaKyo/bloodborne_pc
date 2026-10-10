# Publishing TatsunaKyo revisions

The launcher checks releases in `TatsunaKyo/bloodborne_pc`. Use these names consistently:

| Item | Revision 10 |
|---|---|
| Launcher `VERSION` | `1.6-tatsunakyo.10` |
| GitHub release tag | `windows-v1.6-tatsunakyo.10` |
| Windows asset | `Bloodborne-Windows-v1.6-TatsunaKyo-Revision-10.zip` |
| Release title | `Bloodborne for Windows v1.6 — TatsunaKyo revision 10` |

Increment the revision number for subsequent releases. Increase the upstream version when rebasing onto a newer upstream release. The updater compares the numeric version and revision, rejects unrelated tags, and selects the exact Windows package name.

## Build

Follow [the Windows build instructions](../packaging/windows/README.md) on the commit to be released. Build the renderer and freeze the launcher from that same checkout. The normal packaging script creates `dist/bbport-windows.zip`; rename the completed ZIP to the asset name above. Include all executables, runtime DLLs, `_internal/`, FSR assets, the DLSS bridge/runtime and applicable licenses. Do not include game files, saves, account credentials or personal settings.

Run the launcher settings and updater regressions before packaging:

```bash
python tests/test_launcher_window_settings.py
python tests/test_launcher_updates.py
python tests/test_background.py
python tests/test_overlay_controls.py
ninja -C out/gpu frame-generation-test
out/gpu/frame-generation-test
g++ -std=c++20 -O2 -I. tests/test_temporal_history.cpp -o temporal-history-test
./temporal-history-test
g++ -std=c++20 -O2 -I. tests/test_motion_history.cpp -o motion-history-test
./motion-history-test
g++ -std=c++20 -pthread -Igpu/shim tests/test_background_pause.cpp gpu/shim/bbport_background.cpp -o background-pause-test
./background-pause-test
```

On Windows, verify that `Bloodborne.exe` displays TatsunaKyo revision, the Play preset row opens with DLSS selected and is hidden with other upscalers, and L3+R3 / Insert exposes the new controls. Check preservation of saved settings and test borderless presentation with your GPU and Windows version. Record gameplay results on the shared testing page and specific regressions in the release notes; the main setup is Windows 11 with TatsunaKyo’s RTX 5070 Ti.

## Release

Create a release in this fork using the names above and target the verified revision commit. Paste [the revision 10 notes](releases/windows-v1.6-tatsunakyo.10.md), attach the full Windows ZIP and its SHA-256 file, then publish when testing is complete. GitHub provides source archives for the release tag. Do not replace an existing release tag with a different commit.

With the GitHub CLI, a release can first be prepared as a draft:

```bash
revision_commit="$(git rev-parse HEAD)"
gh release create windows-v1.6-tatsunakyo.10 \
  Bloodborne-Windows-v1.6-TatsunaKyo-Revision-10.zip \
  Bloodborne-Windows-v1.6-TatsunaKyo-Revision-10.zip.sha256 \
  --repo TatsunaKyo/bloodborne_pc --target "$revision_commit" --draft \
  --title 'Bloodborne for Windows v1.6 — TatsunaKyo revision 10' \
  --notes-file docs/releases/windows-v1.6-tatsunakyo.10.md
```

Only published, non-prerelease releases are returned by the launcher's latest-release endpoint. Keep upstream credits and third-party licenses in both source and packages.
