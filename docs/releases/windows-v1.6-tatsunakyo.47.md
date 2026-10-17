# Windows R47 — first-use resource tracking and instance identity cost

R46 still shows a 44.46 ms traversal interval. Its draw-recording thread spends 30.92 ms in the relevant window, including 788 guest-page-protection calls totaling 10.18 ms. Presentation takes 0.11 ms for that event. R47 intervenes in resource preparation independently of FG.

- Windows first-use write watches can share mapped 64 KiB windows. Protected neighbours remain pending uploads; genuine writes, GPU readbacks, mapping holes and unmaps retain tracking. A pending cold write releases its group without invalidating neighbouring clean meshes.
- Instance identity generation packs and hashes the same ordered finite world transforms with XXH3, replacing the slow production bytewise hash. Current contents are still checked; pose bindings, index-content validation and shader calculations are retained.
- The bounded traversal trace distinguishes model-identity and index-hash work. `Capture-Traversal.cmd` remains usable with FG on or off, without F8 or image readbacks.

Controlled production-code tests reduce protection calls from 788 to 50 for a sequential 788-page first-use case, with all requested upload bytes verified. The local 32-record identity microbenchmark is 4.69× faster. These are tests of the host code, not a measured result on the owner's Bloodborne route.

See [the R46 capture follow-up](../investigations/2026-10-16-r46-traversal-followup.md) for the data, design and limits. The cemetery route, displayed-output cadence and image defects are not yet verified resolved on NVIDIA. Distribution remains one complete ZIP and SHA256 sidecar with source, licenses, verification and compact recovery.
