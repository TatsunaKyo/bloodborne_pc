# Release delivery

The owner's delivery preference, updated 15 October 2026, is **one ZIP and its matching `.zip.sha256` file per revision**.

- The ZIP must include the complete playable Windows runtime, required dependencies and licenses, and the source material required for distribution.
- Put the small checkpoint, release notes, verification summary and genuinely reusable build recovery data inside that same ZIP when they are needed to resume the work. Keep each item once, with clear paths such as `source/recovery/`.
- Reuse the existing shared toolchain checkpoint. Do not copy the entire toolchain or Git checkout into every revision. Git remains the canonical source history.
- Omit unused optional tools, compiled regression executables, redundant reports, old captures and other files that neither players nor future maintenance need. Preserve the runtime dependencies of supported features.
- Do not deliver or persist a separate Developer ZIP, complete-candidate duplicate, build-delta archive, input manifest, checkpoint JSON, release HTML/JSON/Markdown file or individual report. Necessary recovery files belong inside the single deliverable ZIP, rather than as additional saved artifacts.
- Do not put another complete release ZIP inside the deliverable. Temporary local build and packaging files are fine; only the final ZIP and checksum should be saved or attached.
- Earlier checkpoints and packaging scripts describe the previous split-package workflow. Their instructions to save multiple artifacts are superseded by this delivery preference. Use a single archive without developer-companion metadata; keep legacy package-reading compatibility where needed.
- Do not regenerate an already delivered revision solely to change its packaging. Apply this rule to the next requested build, avoiding another redundant saved copy. Existing saved files are not to be deleted without an explicit request.

Validate the final archive's contents, executable/dependency hashes, source identity and checksum before delivery. Include enough recovery information to continue from the saved work without storing a second copy of the same build.

NVIDIA feature DLLs can be loaded dynamically through NGX search paths and do not appear in PE import tables. Preserve both `bin/nvngx_dlss.dll` and `bin/streamline/nvngx_dlss.dll` with matching bytes; Streamline initializes NGX before the separate SR bridge. Run `verify_dlss_search_paths` on the assembled layout. Identical DLL contents at distinct required search paths are not unused optional files. Report compilation, UI/package verification and actual GPU/game execution separately.
