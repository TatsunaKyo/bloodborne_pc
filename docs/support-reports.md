# Generate Support Report

I added this to make bug reports easier to put together without asking you to upload a whole diagnostic folder. It reuses the logs and measurements the port already records. It does not enable another profiler or start a background benchmark.

Open **Advanced → Diagnostics → Generate Support Report**, or use the same button in **Log**. Select a file in the list to inspect exactly what will go into the ZIP. You can leave recent logs out, and the anonymous CPU/RAM profile starts off. **Export ZIP** verifies the archive before saving it. Sharing is your choice: the bug and performance buttons open GitHub's forms, where you attach the file yourself.

## Included information

| File | What I include |
|---|---|
| `report.json` | Port revision, Windows build, GPU/driver information and validated graphics/FG/latency/window settings. Selected settings and the latest observed renderer are separate. |
| `report-summary.md` | A short summary you can copy into the issue form. Add the affected scene, steps and expected/actual behavior. |
| `build-identity.json` | Available build revision/source identity and hashes of relevant executables/vendor runtimes. Absolute build paths are omitted. |
| `sessions/` | Up to three recent sessions, using fixed anonymous filenames. Only whitelisted metadata and sanitized text logs are collected. |
| `logs/last_run.log` | Sanitized current/last-run output, including when developer profiling was off. |
| `performance.json` | Relevant timing/FPS/latency lines from those existing logs. It does not invent measurements when no timings were recorded. |
| `hardware-submission.json` | Optional anonymous CPU/RAM profile, settings and an **unreviewed** compatibility submission. |
| `manifest.json` | File sizes and SHA-256 hashes used to check archive integrity. |

The selected Vulkan GPU and driver come from the newest available session that recorded them. Local Windows queries provide the installed adapter/driver list and OS build; the report does not assume that the first adapter is the one used by the game. If information is missing, the report says so.

## Privacy and export

I exclude game files, save files, passwords, online credentials, arbitrary environment variables, raw crash memory dumps and frame captures. Personal paths, known usernames/account names, email addresses, network addresses and credential-bearing log records are removed. Metadata uses a key and value whitelist. Oversized logs retain bounded startup/recent sections; malformed metadata is skipped with a warning.

Please inspect the preview before sharing, especially if a mod writes unusual information into the log. Changing either collection checkbox discards the previous preview and rebuilds the candidate. Nothing is sent to GitHub automatically.

Exports use a temporary ZIP, verify its manifest and contents, then replace the destination. An interrupted export leaves an existing completed report intact. A `.partial` file left by a terminated process is not a completed export.

## Hardware compatibility submissions

The optional JSON separates **a player's report** from **reviewed gameplay evidence**. It starts with `reviewed: false` and `status: "unverified"`, even on a machine where the launcher and diagnostics ran successfully. You can describe genuine gameplay in `evidence`: the scene, duration, result and a reviewed report/capture reference. Compilation, a launcher screenshot or these generated files alone do not confirm gameplay compatibility.

I review that evidence before adding a confirmed row to the [compatibility database](hardware/compatibility.json). The [submission schema](hardware/submission.schema.json) keeps submissions unreviewed; the existing reviewed database keeps its own format. There is no automatic promotion or upload.

For pacing reports, collect matching scenes/settings for the compared revisions and include both real/FG caps. The [performance guide](performance.md) explains the measurements, including the difference between real-frame intervals and displayed FG cadence.

[Launcher and menu](launcher-and-menu.md) · [Current reports](known-issues.md) · [Compatibility](compatibility.md)
