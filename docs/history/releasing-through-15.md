<!-- crowned-workshop-navigation -->
> Historical document. [The Crowned Workshop current guides](../index.md) · [Current reports](../known-issues.md). This page retains its original context and credits.

## Revision 15

I rebuilt the workshop launcher and native components together. Use the package's `BUILD-IDENTITY.json` source commit, the full ZIP checksum and `tools/prepare_release.py` to open the prepared Revision 15 release form. Upload the complete ZIP and its `.sha256` file, then publish when ready. The roadmap and release notes are part of the same source revision.

Earlier release instructions remain below as an archive.

# Publishing TatsunaKyo revisions

## Revision 14

I publish the complete rebuilt package, so the launcher and renderer stay together. For this revision, use **Bloodborne-Windows-v1.6-TatsunaKyo-Revision-14.zip** and its **.zip.sha256** file, with tag **windows-v1.6-tatsunakyo.14**.

The prepared publishing page delivered with the ZIP contains the title, description, exact source commit and archive checksum. Open it, attach those two files, review the preview and publish. I leave the upload to you; opening the form does not publish anything.

The source commit also lives in `BUILD-IDENTITY.json` inside the package. I pin the release to that commit, rather than assuming the current branch head still matches the binaries. The [Revision 14 notes](../releases/windows-v1.6-tatsunakyo.14.md) give the changes and checks.

To regenerate the same publishing page from the completed ZIP:

```bash
python tools/prepare_release.py Bloodborne-Windows-v1.6-TatsunaKyo-Revision-14.zip --output Revision-14-Release.md
```

The helper reads the package identity and calculates its SHA256 before creating the link. GitHub supports the tag, target, title and body parameters in its [release-form documentation](https://docs.github.com/en/repositories/releasing-projects-on-github/automation-for-release-forms-with-query-parameters).

## Earlier Revision 10 package

The details below belong to the existing Revision 10 ZIP. I keep them here for its original publishing request; they are separate from Revision 14.

I pointed the launcher at releases in `TatsunaKyo/bloodborne_pc`, so an update keeps users on this fork. Use these names consistently:

| Item | Revision 10 |
|---|---|
| Launcher `VERSION` | `1.6-tatsunakyo.10` |
| GitHub release tag | `windows-v1.6-tatsunakyo.10` |
| Windows asset | `Bloodborne-Windows-v1.6-TatsunaKyo-Revision-10.zip` |
| Release title | `Bloodborne for Windows v1.6 — TatsunaKyo revision 10` |
| Source commit for the existing ZIP | `f84ca08107e77ac7441124835cbb1a38cd386aed` |
| Existing ZIP SHA-256 | `7f334a030bfb20a4a6a716d0913fef459c9ffc4f9654e8935e7e4eba3b3df06d` |

Increment the revision number for subsequent releases. Increase the upstream version when rebasing onto a newer upstream release. The updater compares the numeric version and revision, rejects unrelated tags, and selects the exact Windows package name.

## Build

Follow [the Windows build instructions](../packaging/windows/README.md) on the commit to be released. Build the renderer and freeze the launcher from that same checkout. The normal packaging script creates `dist/bbport-windows.zip`; rename the completed ZIP to the asset name above. Include all executables, runtime DLLs, `_internal/`, FSR assets, the DLSS bridge/runtime and applicable licenses. Do not include game files, saves, account credentials or personal settings.

Run the launcher settings and updater regressions before packaging:

```bash
python tests/test_launcher_window_settings.py
python tests/test_launcher_updates.py
python tests/test_background.py
python tests/test_overlay_controls.py
ninja -C out/gpu frame-generation-test
out/gpu/frame-generation-test
g++ -std=c++20 -O2 -I. tests/test_temporal_history.cpp -o temporal-history-test
./temporal-history-test
g++ -std=c++20 -O2 -I. tests/test_motion_history.cpp -o motion-history-test
./motion-history-test
g++ -std=c++20 -pthread -Igpu/shim tests/test_background_pause.cpp gpu/shim/bbport_background.cpp -o background-pause-test
./background-pause-test
```

On Windows, verify that `Bloodborne.exe` displays TatsunaKyo revision, the Play preset row opens with DLSS selected and is hidden with other upscalers, and L3+R3 / Insert exposes the new controls. Check preservation of saved settings and test borderless presentation with your GPU and Windows version. I use my Windows 11 / RTX 5070 Ti PC for gameplay and record the results on the shared testing page, with specific regressions in the release notes.

## Ready-to-use Revision 10 page

[Open the Revision 10 publishing page](https://github.com/TatsunaKyo/bloodborne_pc/releases/new?tag=windows-v1.6-tatsunakyo.10&target=f84ca08107e77ac7441124835cbb1a38cd386aed&title=Bloodborne+for+Windows+v1.6+%E2%80%94+TatsunaKyo+revision+10&body=In+this+revision+I+worked+on+temporal+stability+and+on+reducing+some+unnecessary+renderer+work.+I+wanted+the+upscalers+and+Frame+Generation+to+handle+abrupt+camera+changes+more+cleanly%2C+and+to+avoid+repeating+checks+that+did+not+need+to+happen+on+every+frame.%0A%0A%23%23+What%27s+new+in+Revision+10%0A%0AI+added+a+shared+history+reset+for+teleports%2C+sudden+camera+turns%2C+abrupt+FOV+changes+and+returning+from+loading+screens.+DLSS%2C+FSR%2C+XeSS%2C+TAA+and+FG+now+receive+the+same+reset%2C+so+they+can+start+from+the+new+scene+instead+of+carrying+the+previous+one+into+it.+Normal+movement+and+gradual+zoom+still+keep+their+history.%0A%0AI+also+removed+repeated+camera+checks%2C+cached+unchanged+mip-bias+calculations%2C+and+reduced+redundant+image+barriers.+Mesh+verification+is+now+spread+across+frames+instead+of+arriving+in+one+periodic+burst.+I%27ve+done+this+optimization+work+to+reduce+avoidable+overhead%2C+but+I+can%27t+guarantee+an+FPS+increase+on+other+configurations+yet.+Testing+and+feedback+from+other+users+are+very+welcome.%0A%0AI+refreshed+the+project+guide+as+well%2C+so+the+README+explains+what+I+added+and+where+to+find+each+option.%0A%0A%23%23+What+this+package+includes%0A%0AThese+are+the+features+available+in+Revision+10%2C+including+the+work+from+the+earlier+revisions%3A%0A%0A-+%2A%2AUpscaling+choices%3A%2A%2A+DLSS%2C+FSR+3.1%2C+FSR+4%2C+XeSS+Super+Resolution+3.0.2+and+native-resolution+TAA.+I+added+XeSS+for+supported+Intel+and+other+GPUs%2C+and+exposed+DLSS+presets+E%2FF%2C+J%2FK+and+M%2FL+separately+from+Quality%2FBalanced%2FPerformance.+You+can+change+the+preset+in+the+launcher+or+while+playing.%0A-+%2A%2AFrame+Generation+and+Reflex%3A%2A%2A+analytical+FSR+FG+x2+and+NVIDIA+DLSS+FG%2FMFG%2C+with+fixed+x2%E2%80%93x6+choices+depending+on+the+GPU+and+driver.+Both+FG+paths+support+SDR+and+HDR10.+I+kept+Reflex+available+independently%2C+so+you+can+use+it+without+FG.+NVIDIA%27s+integration+uses+Streamline+2.14.1+and+the+production+DLSS-G+310.9.1+runtime.%0A-+%2A%2AExact+FPS+control%3A%2A%2A+75+FPS+is+available+between+60+and+90%2C+and+both+caps+have+editable+number+fields.+The+ordinary+cap+limits+real+game+frames%3B+the+optional+FG+cap+limits+total+output.+For+example%2C+a+130+output+cap+at+x2+gives+a+65+real-frame+ceiling.%0A-+%2A%2AA+cleaner+Play+page%3A%2A%2A+FG+is+available+directly+on+Play.+The+DLSS+preset+row+appears+only+with+DLSS+selected%2C+and+the+NVIDIA+multiplier+has+its+own+row+above+Output.+Customize+overlay%E2%80%A6+takes+you+to+the+detailed+overlay+settings.%0A-+%2A%2AA+smaller%2C+optional+overlay%3A%2A%2A+keep+the+original+basic+readout%2C+disable+it+entirely%2C+or+add+the+DLSS+preset+letter%2C+input%2Foutput+resolution%2C+active+FG+mode+and+Reflex+PC+latency.+The+extra+information+stays+on+the+same+line.+NVIDIA+FPS+uses+the+SDK%27s+actual+presentation+count%2C+so+selecting+a+multiplier+alone+does+not+inflate+the+readout.%0A-+%2A%2ABorderless+and+background+options%3A%2A%2A+choose+Windowed%2C+Borderless+fullscreen+or+Fullscreen%2C+and+decide+whether+the+game+keeps+running%2C+pauses+game%2Frendering%2C+or+uses+a+30%2F60+FPS+background+limit+when+you+switch+windows.+Cooperative+pause+keeps+window+events+responsive+so+you+can+return+to+the+game.%0A-+%2A%2AEnglish+in-game+settings%3A%2A%2A+Insert+or+L3%2BR3+opens+the+English%2FRussian+menu.+I+corrected+the+checkbox+handling+and+keep+settings+shared+with+the+launcher.%0A-+%2A%2AOptional+cheats+and+diagnostics%3A%2A%2A+damage%2C+incoming-damage+reduction%2C+Echoes+and+movement+multipliers%2C+infinite+stamina%2C+consumables%2Fammunition+kept+and+no+fall+damage+sit+alongside+the+original+cheats.+Revision+9+extended+the+stamina+guards+to+continuous+running.+The+developer+diagnostics+option+is+off+by+default+and+can+keep+session+logs+and+crash+details+when+needed.%0A%0A%23%23+Testing+and+remaining+work%0A%0AI+test+the+revisions+on+my+Windows+11+PC+with+an+RTX+5070+Ti.+I+rebuilt+the+launcher+and+native+components%2C+and+the+camera-history%2C+controls%2C+settings%2C+hook+and+package+checks+passed.+If+you+try+this+build+on+another+GPU+or+configuration%2C+please+send+your+settings+and+results%3B+that+helps+me+improve+compatibility+and+performance+beyond+my+own+PC.%0A%0AUneven+frame+pacing+and+the+crash+reported+while+firing+with+several+cheats+enabled+remain+on+my+list.+The+inherited+character-creation+preview+and+some+AMD+world-loading+issues+are+also+still+open.+The+game+HUD+can+show+FG+interpolation+artifacts.+Dynamic+MFG%2C+XeSS+FG%2C+AMD+ML+FG+and+FG+model+presets+A%2FB+are+future+work.+Current+checks+and+details+are+in+%5BTesting+and+known+issues%5D%28https%3A%2F%2Fgithub.com%2FTatsunaKyo%2Fbloodborne_pc%2Fblob%2Fwindows%2Fdocs%2Ftesting.md%29.%0A%0A%23%23+Installing%0A%0ADownload+%2A%2ABloodborne-Windows-v1.6-TatsunaKyo-Revision-10.zip%2A%2A%2C+extract+the+complete+package+into+a+new+folder+and+open+%2A%2ABloodborne.exe%2A%2A.+Choose+your+own+game+folder+and+keep+your+existing+saves%2C+mods+and+preferences.+Use+the+whole+package%2C+including+bin+and+_internal%2C+when+updating.%0A%0A%2A%2ANo+game+files+are+included.+You+need+your+own+decrypted+Bloodborne+CUSA03173+1.09+dump.%2A%2A%0A%0ASource+commit%3A+%60f84ca08107e77ac7441124835cbb1a38cd386aed%60%0A%0AZIP+SHA-256%3A+%607f334a030bfb20a4a6a716d0913fef459c9ffc4f9654e8935e7e4eba3b3df06d%60%0A%0ARevision+maintained+by+TatsunaKyo%2C+based+on+Supermedo%27s+Windows+port%2C+deadinside28%27s+bbport+and+the+shadPS4+renderer.+Full+project%2C+patch+and+runtime+credits+remain+in+the+%5BREADME%5D%28https%3A%2F%2Fgithub.com%2FTatsunaKyo%2Fbloodborne_pc%23credits%29%2C+and+their+licenses+are+included+with+the+package.%0A). I have filled in the tag, source commit, title and description for the existing rebuilt ZIP. Attach `Bloodborne-Windows-v1.6-TatsunaKyo-Revision-10.zip` and its `.sha256` file, review the preview, then publish. The [release text](../releases/windows-v1.6-tatsunakyo.10.md) is also available to copy directly.

## Release

Create a release in this fork using the names above and target the verified revision commit. Paste [the revision 10 notes](../releases/windows-v1.6-tatsunakyo.10.md), attach the full Windows ZIP and its SHA-256 file, then publish when testing is complete. GitHub provides source archives for the release tag. Do not replace an existing release tag with a different commit.

For the already rebuilt Revision 10 ZIP, use the source commit in the table. I have updated the documentation since that build, so the current branch head may be a later documentation commit. If runtime code changes, rebuild and record a new package identity before publishing it.

With the GitHub CLI, a release can first be prepared as a draft:

```bash
revision_commit="f84ca08107e77ac7441124835cbb1a38cd386aed"
gh release create windows-v1.6-tatsunakyo.10 \
  Bloodborne-Windows-v1.6-TatsunaKyo-Revision-10.zip \
  Bloodborne-Windows-v1.6-TatsunaKyo-Revision-10.zip.sha256 \
  --repo TatsunaKyo/bloodborne_pc --target "$revision_commit" --draft \
  --title 'Bloodborne for Windows v1.6 — TatsunaKyo revision 10' \
  --notes-file docs/releases/windows-v1.6-tatsunakyo.10.md
```

Only published, non-prerelease releases are returned by the launcher's latest-release endpoint. Keep upstream credits and third-party licenses in both source and packages.
