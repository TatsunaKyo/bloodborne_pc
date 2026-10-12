# Contributing to The Crowned Workshop

I welcome fixes, hardware results and improvements that make the port easier to use. Please check the [roadmap](docs/tatsunakyo-next.md) and [current reports](docs/known-issues.md) first so we can build on what is already there.

For a code change, work from the `windows` branch and keep the PR focused. Explain the behavior before and after the change, and include the tests you actually ran. Gameplay results, command-recording tests and compilation cover different things; name the environment so I know what was checked. The [test guide](docs/testing.md) has the portable suite and Windows build instructions.

Keep saves, settings, mods and old release compatibility intact. Startup game patches must remain version-checked. A shared setting belongs in the same category in the launcher and in-game menu; new controls should apply live where the implementation allows it. Explicitly label the cases that require a restart.

Please retain the original authorship and vendor licenses. Use your own authorship for your contributions; I maintain the fork as TatsunaKyo. Do not include game executables, decrypted assets, saves, SDK credentials or private diagnostics in a PR. New dependencies need their source, license and integrity information.

For a hardware report, include the port revision, GPU/driver, Windows version, settings and the scenes you tested. I review that evidence before adding it to the [compatibility matrix](docs/compatibility.md). An unreviewed report does not automatically become a confirmed configuration.

I prefer clear explanations of what you changed and why it helps. Keep current guides separate from the development history and avoid repeating every revision in the main README.
