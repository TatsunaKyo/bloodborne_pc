# Current reports

I keep confirmed problems, old reports and hardware coverage separate. A missing test on a different GPU does not mean that the feature is broken there. Likewise, a report from an older revision is useful, but it needs a current-build comparison before I call it a current regression.

## Latest gameplay evidence

The latest affected-scene report says the Hunter's Dream flashing is resolved after Revision 19 on my Windows 11 / RTX 5070 Ti setup with NVIDIA FG. Those fixes remain in the stable Revision 21. I am still collecting pacing comparisons; the optional real-frame graph is there to help make them easier to assess.

There is no newer confirmed reproduction attached to the older reports below. I have kept the reports so they can be checked again, without presenting the entire list as confirmed bugs in Revision 21.

| Earlier report to recheck | What to compare |
|---|---|
| Crash after firing with damage/reduction and kept consumables | Same shot/ammunition state, named cheat combination, revision and optional diagnostics. |
| Infinite Stamina during sustained running | Attacks already worked in the reported test; compare continuous sprinting with the current verified hooks. |
| Blood Echoes multiplier | Award source, selected multiplier and the value before/after the award. |
| Uneven delivery with NVIDIA FG | Same scene, real/output caps, HDR, upscaler and FG mode; distinguish real-frame graph from displayed-frame measurements. |

## Inherited reports and implementation limits

- The upstream empty character-creation preview and some AMD world-loading crashes need confirmation on this fork/current hardware. They are inherited reports, not confirmed failures of every current installation.
- The game's HUD is still included in FG input. HUD separation remains planned; moving UI can produce interpolation artifacts.
- Dynamic NVIDIA MFG, XeSS FG/XeLL, AMD ML FG and selectable FG model presets are separate roadmap items. Their unavailable controls are not broken implementations in this package.

## Resolved or superseded reports

| Report | Available result |
|---|---|
| Hunter's Dream phantom/flashing objects with NVIDIA FG | Latest maintainer gameplay report indicates the Revision 19 correction resolved it on Windows 11 / RTX 5070 Ti. |
| Ignored in-game checkboxes | Actual click/navigation/save checks cover the shared controls; the interface work remains included. |
| Fixed FPS readout with NVIDIA FG | The overlay uses confirmed NVIDIA presentation counts and has an optional active-FG field. |
| Background pause failing to regain focus | Cooperative pause/refocus handling and its regression remain included. |
| Stable release with a legacy `-preview` tag rejected by updater | Reproduced using the published Revision 21 metadata and corrected in Revision 22; existing public tags stay intact. |

If one of these happens again, report the current revision and reproduction details. More hardware coverage belongs in [Compatibility](compatibility.md), and the automated checks are in [Testing](testing.md).
