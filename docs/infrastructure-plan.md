# Repository and release plan

I checked the audit against the repository and published assets on 12 October 2026, after finishing Revision 21. I am keeping this work separate from rendering and gameplay changes.

| Finding | What I verified | Current result |
|---|---|---|
| Updater rejects the current release | Stable Revision 21 and Revision 19 have `-preview` tags; the old parser rejected both. | Corrected in Revision 22, with the real release metadata as a regression fixture. Existing tags stay unchanged. |
| Release script is stale | `prepare_release.py` was tied to Revision 15; the publishing guide still introduced Revision 20. | Revision 22 derives metadata from the package identity, exact source/tree, matching notes and checksum. |
| Missing CI and report forms | No `.github` files were present; repository Issues were disabled. | Regression/build/release workflows and report forms are included. Hosted regression CI passes; Issues still needs enabling. |
| Current-problem page mixes statuses | Fixed flashing, inherited reports, old cheat reports and untested hardware were listed together. | Current reports, compatibility, test methods and dated history now have separate pages. |
| Existing diagnostics | Session logs, settings, timings and crash capture already exist. | Revision 23 reuses them in the inspected Support Report ZIP; hardware submissions stay unreviewed. |

## P0 — Revision 22

The updater accepts legacy stable tags while excluding drafts and actual prereleases. New stable releases use `windows-v<version>-tatsunakyo.<revision>`; previews use the `-preview` suffix and GitHub's prerelease flag. Revision 22's stable tag is deliberately compatible with the already-installed old parser.

Release preparation derives the version, source and notes from the complete package. Validation checks the archive, exact executable/runtime hashes, AMD64 PE files, DLL import/export closure, sidecar checksum and source patch/tree. The new Windows workflow rebuilds native executables and the launcher; unchanged SDK redistributables are taken from a checksum-pinned stable baseline. This records provenance and fixed dependencies without claiming byte-identical compiler output.

Portable CI executes the existing settings, renderer and actual GUI regressions. The [hosted regression run for Revision 22](https://github.com/TatsunaKyo/bloodborne_pc/actions/runs/38229068006) passed. The Windows build workflow also includes CPU regression programs and compiled-launcher checks before assembling a candidate, but its full hosted build still needs a separate run. Publication stays manual.

The bug, performance and feature forms are ready in `.github/ISSUE_TEMPLATE`. To make them available, enable **Settings → General → Features → Issues** in the repository. Actions is already running.

## P1 — Player documentation and reviewed evidence

The main README keeps the artwork and feature introductions, with download/installation/compatibility navigation at the top, a live-editing guide and a visible roadmap. Current documents use the workshop name and seven matching categories; older notes remain dated records with a link back to the current guides.

The opening follows my supplied layout: the existing banner, centered title and introduction, four badges, and direct download/installation links. My original introductory paragraphs remain below those links. **LIVE editing during play** belongs with the in-game menu, with links from the relevant features and a separate table for startup exceptions.

I want genuine gameplay screenshots alongside the illustrations. The supplied navigation concept is a layout example, not gameplay evidence; I will use actual reviewed captures for that gallery.

Revision 23 adds [Generate Support Report](support-reports.md), with Windows/GPU/driver and build identity, validated settings, bounded recent logs and existing measurements. The launcher shows each sanitized file before export, leaves the anonymous CPU/RAM profile optional and exports a verified ZIP for manual attachment. The privacy/archive tests include malformed inputs, credentials, custom paths and terminated exports.

The optional hardware JSON has its own submission schema and remains unreviewed. Only reviewed gameplay evidence can enter the confirmed compatibility database.

Reviewed hardware reports can populate the compatibility JSON/table. Keep the raw report's provenance and review state; only a maintainer-approved gameplay result becomes a confirmed row. CI can validate the schema and generated table, but compilation or a recorded-call test is not a hardware result.

## P2 — Presentation and a documentation site

Create an editable 1280 × 640 social preview from the existing workshop artwork, restrained lettering and crowned TK emblem, then export a PNG for GitHub's repository settings. The main feature illustrations stay with their explanations.

Evaluate MkDocs Material with the existing guides after the release path is reliable. Preserve current Markdown links and historical records, test desktop/mobile navigation and avoid maintaining a second set of feature descriptions. Pages deployment needs its own repository setting and is not part of the current release.

## Gameplay priorities remain

The existing [gameplay roadmap](tatsunakyo-next.md) stays active: check the remaining Echoes and pacing reports, extend the first Save Manager, improve native input, support ultrawide/HUD placement and continue HUDless-FG work. Each change gets its own regression coverage before it joins a release.

## Save protection: first implementation

Revision 23 includes [Save Manager](save-manager.md): pre-launch backups, named closed-game snapshots, verified restore/rollback, configurable automatic retention and the existing custom saves selection. Native/launcher OS leases protect the save writer, and interrupted restoration is recovered before the next launch. Named profiles and coordinated live snapshots remain separate later work. Native mouse/remapping and measured pacing comparisons against Revision 21 are the next PC priorities.
