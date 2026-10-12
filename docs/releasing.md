# Publishing The Crowned Workshop

I publish the full rebuilt package so the launcher and renderer stay together. The current preview is **Revision 20**, with tag **windows-v1.6-tatsunakyo.20-preview**.

## Files and release page

Use **Bloodborne-Windows-v1.6-TatsunaKyo-Revision-20.zip** and its **.zip.sha256** file. The prepared release page delivered with them contains the title, description, exact source commit and archive checksum. The same information is in **Crowned-Workshop-Revision-20-Release.json**, with the text in **Crowned-Workshop-Revision-20-Release.md**.

1. Open the prepared page and review the preview.
2. Attach the full ZIP and its SHA256 file.
3. Publish when the build is ready for other users to try.

The package's **BUILD-IDENTITY.json** records its source commit and binary hashes. I pin the release to that commit so a later branch update does not change which source matches the uploaded build. The [Revision 20 notes](releases/windows-v1.6-tatsunakyo.20.md) describe the changes and checks.

## Building the package

[Windows build instructions](../packaging/windows/README.md) cover the native components, launcher, pinned runtimes and licenses. Both Bloodborne.exe and the native renderer are rebuilt for each revision. Keep the full package contents when uploading; no game files belong in the release.

For the project's feature overview, see the [README](../README.md). Testing and open reports are in [Testing](testing.md), and planned work is in [the roadmap](tatsunakyo-next.md).

[Earlier publishing records](history/releasing-through-15.md) remain available as an archive.
