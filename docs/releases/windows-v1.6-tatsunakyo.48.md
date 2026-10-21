> Historical/upstream record: statements and test results below describe their original revision or environment. [Current guides](../index.md) · [Current reports](../known-issues.md) · [Published releases](../releases/index.md)

# Windows 1.6-tatsunakyo.48

R47's supplied traversal capture still stalls for 39.04 ms, with 708 page-protection calls consuming 8.336 ms inside draw preparation. R48 batches actual CPU-dirty read-only buffer uploads within already-resident sparse blocks, including recycled addresses. It also corrects cold-page classification after a write notification and adds bounded resource-byte/permission attribution to the existing traversal diagnostic.

The upload policy caps read-ahead at 64 KiB, rejects GPU-modified/hot neighbours and unreadable/unmapped padding, and excludes writable/texel bindings. Extra upload traffic for unused neighbours is a possible tradeoff. A controlled reuse case executes 49 instead of 156 protections/staging batches/copy commands with matching bytes; this is not a game benchmark. Full evidence and limits: `docs/investigations/2026-10-16-r47-traversal-followup.md`.

One complete ZIP plus its SHA256. Runtime, required dependencies/licenses, source and compact recovery are included. Use the normal launcher for gameplay; `Capture-Traversal.cmd` still needs no F8 and exports its ZIP after exit, with FG enabled or disabled. No automatic upload is performed.

Windows/NVIDIA gameplay, the cemetery route, 119–121 output fluctuations and image artifacts are not locally verified resolved. The NVIDIA feature libraries, both required SR DLL locations and RTX 40/50 versus optional RTX 20/30 paths are retained.
