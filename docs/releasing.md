# Publishing The Crowned Workshop

Publish **one complete Windows ZIP and its matching `.zip.sha256`**. Include required runtime dependencies/licenses, exact current startup sources, source patch and compact reusable recovery/verification in that ZIP. Exclude compiled regression programs, unused optional tools, redundant reports and a second toolchain copy. Legacy split archives remain readable; modern revisions cannot use the split writer.

## Version and channel

Stable releases have GitHub prerelease disabled; preview releases enable it. Keep existing public tags intact, including R55's `windows-v1.6-tatsunakyo.55-preview`: GitHub marks it stable despite that legacy suffix. Release status and verified identity determine the updater channel. Never move a published tag to a later source tree.

## Prepare the exact package

Commit current source, update VERSION/launcher and the matching revision notes, then run `python tools/update_readme_revision.py`. Build current native components and launcher using the pinned [Windows workflow](../.github/workflows/windows-build.yml). The assembler replaces all tracked startup/runtime files, including patch XML and red-zone data, instead of inheriting them from a previous ZIP. Both required NGX DLSS SR search paths must contain matching DLL bytes.

```bash
python tools/release_integrity.py path/to/Bloodborne-Windows-v1.6-TatsunaKyo-Revision-55.zip --repo . --require-sidecar
python tools/prepare_release.py path/to/Bloodborne-Windows-v1.6-TatsunaKyo-Revision-55.zip --repo . --channel stable --existing-tag windows-v1.6-tatsunakyo.55-preview --output out/release.md
```

Use the actual revision filename/tag. The existing-tag example reproduces the published R55 form; a new release uses its own version/tag and channel. Preparation reads the ZIP's identity and notes, verifies executables/runtime/source/checksum and writes a local reviewable form. Those temporary files are not additional user deliverables. The tool does not publish or move tags.

Run the packaged startup regression against the **finished ZIP**, with its own compiled launcher, and verify import closure, binary hashes, runtime/source identity and checksum. Keep compile/UI/package checks distinct from Windows/GPU gameplay and physical display-cadence evidence.

1. Review the exact prepared notes, source target, channel and test results.
2. Attach **only the ZIP and its `.zip.sha256`** to the matching GitHub release.
3. Publish after the intended hardware/candidate checks; state remaining limits accurately.
4. Run **Published release integrity** against the published tag/assets; rerun after a corrected upload without moving the tag.

## Automated builds

[Windows build and package](../.github/workflows/windows-build.yml) rebuilds native programs and the launcher, executes regressions and assembles the candidate. The baseline supplies pinned unchanged redistributables/licenses. Compiler/package versions and source/tree are recorded; different hosts are not claimed to produce byte-identical compiler output. Publication remains manual.

[Build instructions](../packaging/windows/README.md) · [Testing](testing.md) · [Repository settings](repository-setup.md) · [Historical publishing records](history/releasing-through-15.md)

## README revision badge

`python tools/update_readme_revision.py --check` checks the launcher version, badge and matching notes link. The badge describes current source; **Download latest** follows the latest published release. Later maintenance belongs on [its own page](maintenance.md), without implying that the existing R55 ZIP was rebuilt.
