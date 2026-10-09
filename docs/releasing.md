# Publishing TatsunaKyo revisions

The launcher checks releases in `TatsunaKyo/bloodborne_pc`. Use these names consistently:

| Item | Revision 3 |
|---|---|
| Launcher `VERSION` | `1.6-tatsunakyo.3` |
| GitHub release tag | `windows-v1.6-tatsunakyo.3` |
| Windows asset | `Bloodborne-Windows-v1.6-TatsunaKyo-Revision-3.zip` |
| Release title | `Bloodborne for Windows v1.6 — TatsunaKyo revision 3` |

Increment the revision number for subsequent releases. Increase the upstream version
when rebasing onto a newer upstream release. The updater compares the numeric version
and revision, rejects unrelated tags, and selects the exact Windows package name.

## Build

Follow [the Windows build instructions](../packaging/windows/README.md) on the commit
to be released. Build the renderer and freeze the launcher from that same checkout.
The normal packaging script creates `dist/bbport-windows.zip`; rename the completed
ZIP to the asset name above. Include all executables, runtime DLLs, `_internal/`, FSR
assets, the DLSS bridge/runtime and applicable licenses. Do not include game files,
saves, account credentials or personal settings.

Run the launcher settings and updater regressions before packaging:

```bash
python tests/test_launcher_window_settings.py
python tests/test_launcher_updates.py
python tests/test_background.py
```

On Windows, verify that `Bloodborne.exe` displays TatsunaKyo revision, the preset
dropdown opens with both FSR and DLSS selected, and L3+R3 / Insert exposes the new
controls. Check preservation of saved settings and test borderless presentation with
your GPU and Windows version. Record validation limits in the release notes.

## Release

Create a release in this fork using the names above and target the verified revision
commit. Paste [the revision 3 notes](releases/windows-v1.6-tatsunakyo.3.md), attach the
full Windows ZIP and its SHA-256 file, then publish when testing is complete. GitHub
provides source archives for the release tag. Do not replace an existing release tag
with a different commit.

With the GitHub CLI, a release can first be prepared as a draft:

```bash
gh release create windows-v1.6-tatsunakyo.3 \
  Bloodborne-Windows-v1.6-TatsunaKyo-Revision-3.zip \
  Bloodborne-Windows-v1.6-TatsunaKyo-Revision-3.zip.sha256 \
  --repo TatsunaKyo/bloodborne_pc --target tatsunakyo-revision --draft \
  --title 'Bloodborne for Windows v1.6 — TatsunaKyo revision 3' \
  --notes-file docs/releases/windows-v1.6-tatsunakyo.3.md
```

Only published, non-prerelease releases are returned by the launcher's latest-release
endpoint. Keep upstream credits and third-party licenses in both source and packages.
