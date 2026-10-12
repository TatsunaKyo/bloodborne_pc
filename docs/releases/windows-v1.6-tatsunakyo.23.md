# Bloodborne: The Crowned Workshop — Revision 23

I added two launcher tools in this revision: Support Report to make useful reports easier to share, and the first Save Manager to protect progress before launching or restoring a save.

## Generate Support Report

You can open it from **Advanced → Diagnostics** or **Log**. It brings together the revision/build identity, Windows/GPU/driver information, validated graphics/FG/latency/window settings and recent diagnostic timings/logs. It uses the measurements already recorded by the port.

The preview lets you inspect every included file before exporting the ZIP. Recent logs can be excluded, the anonymous CPU/RAM profile is optional, and passwords, account details, personal paths, saves, game files and private memory dumps are excluded or removed. The ZIP is verified before it replaces the destination. GitHub's bug/performance forms now explain how to attach it manually; nothing is uploaded automatically.

The optional hardware submission stays unreviewed until I review actual gameplay evidence. A generated profile or successful compilation does not become a confirmed compatibility result.

## Save Manager

Open **Game & files → Open Save Manager**. Existing saves are backed up before launching, including shortcuts and in-game restarts. You can make named snapshots, inspect verified backups and restore one with a verified rollback copy of your current progress. Automatic retention defaults to ten snapshots and can be set from one to one hundred; manual and rollback snapshots are kept.

I retained the original save tree, companion metadata and save memory. Custom save locations use the launcher's existing selection. The native runtime and manager share an OS saves lease, and save operations require a closed game. An interrupted restore is recovered before the next launch; malformed or corrupted archives are rejected before they can replace progress. Live snapshots and named save profiles are later stages.

## Verification and installation

The new regressions exercise sanitized reports, malformed/missing inputs, credential/path removal, ZIP checksums, interrupted exports, save leases, copy/restore failures, retained rollback copies and processes terminated halfway through restoration. Actual Tk checks exercise the new dialogs and the existing launcher layouts. Windows infrastructure CI also compiles the native lease fixture and tests the frozen launcher runtime.

Rendering keeps Revision 21's visual correction and pacing implementation. Native mouse/remapping and further real/generated frame pacing work remain the next PC priorities.

Extract the complete ZIP into a new folder and select your existing game and saves locations in **Game & files**. The port requires your own decrypted Bloodborne 1.09 dump. The archive includes its source/build identity and SHA-256 verification file.

[Support Report guide](../support-reports.md) · [Save Manager guide](../save-manager.md) · [Current reports](../known-issues.md)
