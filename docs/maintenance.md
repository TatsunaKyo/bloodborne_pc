# Source maintenance after Revision 55

The published R55 download is from `6f8564dc973dd35d70438c43f0140fb0531949a3`. Changes below apply to subsequent source maintenance and need a later binary build. Its existing ZIP, tag and checksum retain their published identity.

- Reconcile the default Windows branch with the complete R55 source and upstream history.
- Restore missing trophy-grade colours and translated labels in Achievements; check the actual page, filters and empty states.
- Fix the assembler overwriting its final ZIP path during DLL dependency resolution; validate actual assembly and source/patch replay with fixture toolchain boundaries.
- Generate the overlay's ten output-resolution labels from the shared dimensions, avoiding the old four-element array overrun. Require restart when changing to, from or between ultrawide outputs so startup camera/HUD patches stay consistent.
- Remove unused first-party Python imports/locals, restore the patch test's missing fingerprint import and close toolchain-record streams explicitly.
- Reject modern revisions in the legacy split writer; retain historical reading/recovery tests.
- Refresh current guides, repair historical links and label dated evidence. Add Python, documentation/anchor and revision-badge gates to CI.

These corrections do not establish a fix for the cemetery route, physical display cadence or reconstruction artifacts. [Current reports](known-issues.md) · [Testing](testing.md) · [Published notes](releases/index.md)

## Supermedo 1.9.7 / unreleased R56

The current integration covers 443 upstream commits from `de2e38af055f09f819946951075c6bb119e62ae6` through `b48052617a919fc4d6b10ae3395e209c9e94e17a`. The tracker/cache/rasterizer rollback is adopted coherently, while Workshop shader integrity, motion relocation, nonblocking speculative preparation and sleeping draw drains are retained. Provider classes, shared settings, latency ownership, native PC Settings and packaging are reconciled. [Decisions and evidence](investigations/2026-11-02-supermedo-197.md) · [Integration map](integration-map.md)
