# Save Manager

I added Save Manager because I want progress protected before a new session or an experimental change. It copies the original save tree without editing the game's save contents, and verifies each snapshot before offering it for restoration.

Open **Game & files → Open Save Manager**. The dialog shows the selected saves folder and has separate **Snapshots** and **Backup options** tabs. It uses the same custom saves location as the launcher; reopening the manager after changing that location selects the new folder.

## Backups and named snapshots

**Back up existing saves before each launch** starts on. The backup finishes before the native runtime opens saves or applies its startup audio correction. It also covers Play shortcuts and an in-game Apply and restart. A first launch with no save files simply continues; a failed required backup stops the launch and explains the problem in the log.

The default retention is **10 automatic snapshots**, adjustable from **1 to 100**. Retention removes only verified automatic snapshots for that saves folder. The latest backup is kept even if the system clock changes. Manual snapshots, rollback copies and damaged archives are left alone.

For a manual snapshot, close the game, enter a name such as “Before the next boss” and choose **Create snapshot**. The ZIP lives in `save-backups/` inside your selected saves folder. All save users/titles, companion `.sce_sys` metadata, save memory and empty directories are retained. Shader caches, credentials and game files are outside that tree.

## Restore and rollback

Select a verified snapshot and choose **Restore selected**. The confirmation shows the destination. Save Manager prepares the replacement in a separate staging directory, checks its contents, and creates a verified rollback ZIP of your current saves before replacing the live tree. You can restore that rollback snapshot to return to the previous progress.

**Import backup** verifies an external ZIP first. A backup from another saves location needs an explicit import confirmation; the dialog keeps its destination fixed throughout the operation.

The archive manifest records every file's relative path, size, timestamp and SHA-256 hash. Missing files, damaged payloads, duplicate/case-conflicting paths, unsafe filenames, links/junctions and unexpected archive entries are rejected. An archive checksum verifies the stored bytes; Save Manager does not rewrite Bloodborne's internal save format.

## Closed-game protection and interrupted operations

The native runtime holds an OS lease for the saves folder before any startup save edits, keeping it for the session. Backup and restore acquire that same lease. On Windows, snapshot source handles also deny writers and deletion. Older running Bloodborne processes are checked as well. **The game must be closed: a background rendering pause is still an active game.**

An interrupted backup does not become a completed snapshot. Restoration has a durable journal and a separately verified rollback archive. The next launch checks for an unfinished restore before starting the native process; **Recover interrupted restore** in the manager performs the same recovery. A committed, verified replacement is kept; an unfinished replacement restores the previous progress. Recovery files are retained when needed, and the native runtime refuses to proceed while a pending restore still needs attention.

If a journal or required rollback is damaged, the manager stops and leaves the available files intact. Keep those files and recover from a verified snapshot before continuing. I have not enabled live snapshots: reliable save protection needs the writer to be stopped, rather than a guess based on unchanged timestamps.

## Next stages

This first version includes automatic backups, named snapshots, verified restoration/rollback, retention and custom save locations. Named save profiles and a genuine coordinated live-save boundary are later work. The next PC priorities are native mouse/full remapping and measured real/generated frame pacing comparisons against Revision 21.

[Launcher settings](launcher-and-menu.md) · [Support Report](support-reports.md) · [Development roadmap](tatsunakyo-next.md)
