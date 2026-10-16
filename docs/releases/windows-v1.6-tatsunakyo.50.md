# Windows 1.6-tatsunakyo.50

R49's supplied traversal capture still contains a 41.656 ms hitch. R50 fixes two dependencies that could extend guest stalls and removes command-storage allocation from the recorder mutex:

- Protected snapshots wait for their own source range and captured request prefix. Aliased/flexible/unsafe mappings and access grants/remaps retain conservative full ordering.
- Guest copy fences capture their async copy epoch when requested and join it with recorder completion. Later copies and unrelated write watches no longer join that fence.
- New command chunks are allocated outside the recorder lock, with unused command storage left uninitialized until written and bookkeeping initialized normally.
- Optional traversal capture automatically includes a bounded CPU timeline with native thread IDs, resource/request links and compilation keys. No F8 is required for CPU evidence, and FG may be on or off.

Controls execute the production queue, C memory contract, protected snapshots, copy pool, scheduler fence bodies, allocator and timeline exporter. R49 controls reproduce late copy-epoch capture and allocation under the recorder mutex; current controls verify exclusion of deliberately held unrelated work, protected-copy ordering and 64 FIFO fence completions. Windows cross-build, matching compiled-launcher checks and package integrity are reported separately inside the archive.

One complete ZIP plus SHA256 contains runtime, required dependencies/licenses, source, verification and compact recovery. Evidence and limitations: `docs/investigations/2026-10-16-r50-dependencies.md`.

No Windows/NVIDIA game execution is available locally. The cemetery route, displayed-frame spacing, stairs halo and transient geometry are not claimed resolved. R50 does not change motion reconstruction, frame caps, NVIDIA feature DLLs or implement Encore NR compatibility.
