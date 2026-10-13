# Bloodborne: The Crowned Workshop — Revision 27

I fixed the startup error in Revision 26 that stopped Bloodborne.exe before the launcher could open. When I replaced the updater's shared temporary folder, I left one reference to `UPDATE_DIR` in the normal startup path. That reference is now removed.

I added a regression test that calls the real startup function with the compiled launcher, opens the interface in English and Russian, handles `--play` without a configured game folder, and closes through the normal settings handler. The Windows checks also start the frozen executable as a separate process through its normal entry point, wait for its window and check that it closes successfully. These checks now run before packaging, alongside the existing update, save and diagnostic tests.

This build keeps Revision 26's presentation recovery, verified updates and all existing features. The renderer binaries are unchanged from Revision 26. My gameplay setup remains Windows 11 with an RTX 5070 Ti; this correction concerns launcher startup and does not claim a new gameplay or performance result.

## Installation

Extract the complete ZIP into a new folder. Select your existing game and saves locations in Game & files. Keep your game files, saves, settings and mods; the package contains none of your personal data. Use this build instead of Revision 26. Upload the complete ZIP and its matching `.zip.sha256` when publishing the revision.
