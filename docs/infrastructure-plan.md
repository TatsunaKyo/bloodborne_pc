# Repository and release plan

I checked the audit against the repository and published assets on 12 October 2026, after finishing Revision 21. I am keeping this work separate from rendering and gameplay changes.

| Finding | What I verified | Next step |
|---|---|---|
| Updater rejects the current release | Stable Revision 21 and Revision 19 have `-preview` tags; the old parser rejected both. | Corrected in Revision 22, with the real release metadata as a regression fixture. Existing tags stay unchanged. |
| Release script is stale | `prepare_release.py` was tied to Revision 15; the publishing guide still introduced Revision 20. | Use the package identity, exact source/tree, matching embedded notes and actual checksum. |
| Missing CI and report forms | No `.github` files were present; repository Issues were disabled. | Add regression/build/release workflows and forms; enable the repository settings separately. |
| Current-problem page mixes statuses | Fixed flashing, inherited reports, old cheat reports and untested hardware were listed together. | Separate current reports, coverage, test methods and dated history. |
| Existing diagnostics | Session logs, settings, timings and crash capture already exist. | Extend them with a reviewed/redacted support archive; do not build a second profiler. |

## P0 — Revision 22

The updater accepts legacy stable tags while excluding drafts and actual prereleases. New stable releases use `windows-v<version>-tatsunakyo.<revision>`; previews use the `-preview` suffix and GitHub's prerelease flag. Revision 22's stable tag is deliberately compatible with the already-installed old parser.

Release preparation derives the version, source and notes from the complete package. Validation checks the archive, exact executable/runtime hashes, AMD64 PE files, DLL import/export closure, sidecar checksum and source patch/tree. The new Windows workflow rebuilds native executables and the launcher; unchanged SDK redistributables are taken from a checksum-pinned stable baseline. This records provenance and fixed dependencies without claiming byte-identical compiler output.

Portable CI executes the existing settings, renderer and actual GUI regressions. Windows CI executes CPU regression programs and checks the compiled launcher before assembling a candidate. Publication stays manual. The repository settings and first hosted workflow runs are separate checks; local source tests do not count as a completed hosted Windows CI run.

## P1 — Player documentation and reviewed evidence

The main README keeps the artwork and feature introductions, with download/installation/compatibility navigation at the top, a live-editing guide and a visible roadmap. Current documents use the workshop name and seven matching categories; older notes remain dated records with a link back to the current guides.

I want genuine gameplay screenshots alongside the illustrations. The supplied navigation concept is a layout example, not gameplay evidence; I will use actual reviewed captures for that gallery.

The next support-report change should extend the existing diagnostics with GPU/driver, Windows build, revision/build identity, a whitelist of renderer preferences, timings and selected logs. It should redact personal paths and account/token fields, exclude game/save files and raw memory dumps by default, and let the player inspect the ZIP locally before sharing. Tests must include fake credentials, usernames, custom paths and missing/corrupt diagnostics. No automatic submission is planned.

Reviewed hardware reports can populate the compatibility JSON/table. Keep the raw report's provenance and review state; only a maintainer-approved gameplay result becomes a confirmed row. CI can validate the schema and generated table, but compilation or a recorded-call test is not a hardware result.

## P2 — Presentation and a documentation site

Create an editable 1280 × 640 social preview from the existing workshop artwork, restrained lettering and crowned TK emblem, then export a PNG for GitHub's repository settings. The main feature illustrations stay with their explanations.

Evaluate MkDocs Material with the existing guides after the release path is reliable. Preserve current Markdown links and historical records, test desktop/mobile navigation and avoid maintaining a second set of feature descriptions. Pages deployment needs its own repository setting and is not part of the current release.

## Gameplay priorities remain

The existing [gameplay roadmap](tatsunakyo-next.md) stays active: recheck the reported cheat cases, add Save Manager, improve native input, support ultrawide/HUD placement and continue pacing/HUDless-FG work. Infrastructure improvements do not replace those tasks or justify unrelated rendering changes in this revision.
