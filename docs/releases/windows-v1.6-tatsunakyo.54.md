# TatsunaKyo revision 54 — repair the packaged 30-FPS regression

R53 mixed current startup scripts with R52's `patches/Bloodborne.xml` and `patches/redzone.json`. The patch fingerprint therefore used different ranges from the digest expected by the scripts. In the shipped-file replay, the requested unlocked mode fell back to 30 and no timing patches were emitted, with FG both enabled and disabled.

R54 replaces the entire first-party startup payload from the release commit and verifies every shipped file against that commit, including patch data. The release validator also checks both native bridge identities and the duplicate NVIDIA feature search paths. CI runs the startup regression against the finished ZIP and compiled launcher entry point.

The modern real-frame cap, including Auto, supersedes the old launcher `frame_cap`. A derived vblank is recomputed after restart; explicit advanced overrides are retained. The renderer and Supermedo integration are retained. Existing settings, saves and shader caches do not need to be deleted.

Validation includes the actual R53 ZIP as a negative control, packaged startup/patch compilation and restarts on a synthetic ELF, compiled launcher/Tk controls, live FG-off cap transitions, Windows cross-compilation, complete first-party source identity, PE dependency closure and ZIP/SHA256 verification. These are startup/correctness checks, not execution of Bloodborne on Windows/NVIDIA. Cemetery stutter, exact 120-FPS cadence and reconstruction artifacts remain unverified in target gameplay.
