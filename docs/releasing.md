# Publishing The Crowned Workshop

I publish a game package and an optional Developer archive so the launcher, native components, runtimes and source records match. Release preparation reads the game package's `BUILD-IDENTITY.json`, matching notes and Developer checksum; there is no revision number to edit in the tool. The game ZIP retains every runtime and license, while source records, regression programs and specialist scripts are kept in Developer. The complete source patch stays in the game ZIP for installed-updater compatibility. The unsplit candidate is preserved under `dist/complete` during assembly.

## Version and channel

| Channel | New tag | GitHub setting |
|---|---|---|
| Stable | `windows-v<upstream-version>-tatsunakyo.<revision>` | Prerelease off; make it Latest when ready. |
| Preview | Same version with `-preview` | Prerelease on; keep it out of the stable updater. |

The public Revision 19 and 21 tags end in `-preview` even though GitHub marks those releases stable. I keep those tags intact. The corrected updater accepts them by version and release status; genuine drafts/prereleases are excluded. Revision 22's new stable tag has no suffix so installed older launchers can recognize it too.

## Prepare the exact package

```bash
python tools/release_integrity.py path/to/Bloodborne-Windows-v1.6-TatsunaKyo-Revision-28.zip --repo . --require-sidecar
python tools/prepare_release.py path/to/Bloodborne-Windows-v1.6-TatsunaKyo-Revision-28.zip --repo . --channel stable --output dist/release.md
```

Use the actual package filename for the revision you built. The second command writes a ready-to-review Markdown description and JSON containing the publishing URL, exact source commit, tag, channel, package and checksum. It reads the matching notes already included in the package and refuses mismatched executables, runtimes, source or dependencies.

`--channel preview` prepares a prerelease. To regenerate the form for an already-published legacy stable tag, use `--channel stable --existing-tag windows-v1.6-tatsunakyo.21-preview` with that release's package. The tool never edits tags or publishes a release.

1. Review the prepared page and its source target.
2. Upload **both ZIPs and both .zip.sha256 files**. Keep them together in the same release; players only need the ordinary game package.
3. Test the candidate on the intended Windows hardware, then publish with the selected channel setting.
4. Keep the verification records and build identity with the package. The Published release integrity workflow checks the uploaded assets against their tag/source.

## Automated builds

[Windows build and package](../.github/workflows/windows-build.yml) rebuilds native programs and the launcher, runs regressions and prepares a candidate. Unchanged SDK DLLs/licenses come from the checksum-pinned stable baseline; current native executables, launcher and repository files replace their older counterparts. Installed MSYS2 versions, compiler details, hashes and source/tree are recorded. Fixed inputs improve repeatability; I do not claim that different hosts produce byte-identical compiler output.

Publication stays manual. [Repository settings](repository-setup.md) explains Issues/Actions activation; [Windows build instructions](../packaging/windows/README.md) cover local builds. [Contributing](../CONTRIBUTING.md), [tests](testing.md) and [the infrastructure plan](infrastructure-plan.md) describe the gates and next work.

[Earlier publishing records](history/releasing-through-15.md) remain archived.

## README revision badge

After changing the launcher version and adding its release notes, run `python tools/update_readme_revision.py`. CI checks that the badge and its notes link match that version. The badge describes the current build; **Download latest** follows the latest published GitHub release. Preparing or delivering a ZIP does not publish it.

The launcher now applies the package validator before running a downloaded update, including its published checksum. Keep uploading the `.zip.sha256` sidecar under the exact package filename. Invalid or incomplete downloads leave the installed launcher open.

The published-release check waits briefly for uploads and records a clear failure if an asset remains missing. It validates the Developer archive when the build identity declares one; older releases with a single ZIP remain valid. After correcting an upload, rerun the failed job rather than changing its public tag or disabling the checks.
