> Historical/upstream record: statements and test results below describe their original revision or environment. [Current guides](../index.md) · [Current reports](../known-issues.md) · [Published releases](../releases/index.md)

# Windows 1.6-tatsunakyo.51

The supplied R50 capture still has a 34.38 ms traversal interval, with about 196 MiB of buffer-upload operations concentrated in the window. R51 changes the vertex upload footprint: eligible direct draws synchronize the vertices their indices can fetch, while keeping the original buffer binding offsets, bounds, vertex IDs and draw parameters. Per-instance data and cases without proven CPU index ranges retain the previous path. Large cached index buffers are not converted into repeated stream uploads.

The production cache/tracker control reduces a 4 MiB descriptor with 6000 fetched bytes from a full 4 MiB upload to 64 KiB, retaining the existing sparse-block granularity. Needed bytes match; unused pages remain dirty, later draws and writes upload correctly, and GPU-authored bytes survive. Production index-snapshot and binding code, 30000 byte-coverage cases, interleaved/prepared/instance paths and ASan/UBSan are checked. This byte-count result is not a gameplay speedup measurement.

The diagnostic exporter also fixes silent truncation of event lists at 100 items. All 17295 validated events from the owner's separate R50 timeline now survive privacy filtering. Existing file/window limits and incomplete-capture status remain.

Evidence, tradeoffs and target limits: `docs/investigations/2026-10-16-r50-traversal-followup.md`. Windows build, launcher and package verification are recorded inside the single complete ZIP plus SHA256. NVIDIA libraries, frame-cap ownership and motion reconstruction are retained. Cemetery traversal, displayed-frame spacing, the stairs halo and transient geometry are not claimed resolved without a target Windows/NVIDIA run.
