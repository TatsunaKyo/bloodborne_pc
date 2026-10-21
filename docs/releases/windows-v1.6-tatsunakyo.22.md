> Historical/upstream record: statements and test results below describe their original revision or environment. [Current guides](../index.md) · [Current reports](../known-issues.md) · [Published releases](../releases/index.md)

# Bloodborne: The Crowned Workshop — Revision 22

I have focused this revision on updating, releases and documentation. It keeps the renderer and gameplay changes from Revision 21, including the Hunter's Dream flashing fixes and the shared launcher/in-game settings categories.

## Updating and releases

I fixed the launcher refusing stable releases whose older tags end in `-preview`, including Revision 21. Existing public tags stay unchanged. From this revision onward, stable releases use a plain revision tag; actual previews use the suffix and GitHub's prerelease flag. The new stable tag also lets older launchers recognize Revision 22.

I replaced the release script's fixed revision number with the packaged build identity, source commit and matching release notes. Preparation checks executable and runtime hashes, Windows binary dependencies, the source patch/tree and the ZIP checksum before producing the publication page. I added regression, Windows build/package and published-release verification workflows, plus forms for bugs, performance regressions and feature requests. Publishing remains manual.

## Finding the right information

The README now puts download, installation and compatibility links near the introduction, explains which settings I made editable while playing and includes the roadmap. The new live-settings guide also explains the startup exceptions, so users know when a restart is actually needed.

I reorganized current reports, hardware coverage, testing and older development notes. Old reports remain available without presenting every one as a confirmed current bug. The guides use The Crowned Workshop name and the matching Image, Frames, Window, Overlay, Cheats, Effects and Advanced categories; historical notes keep their dates and credits with links to current guidance.

I added contribution/security guidance and a reviewed hardware record. My confirmed gameplay setup remains Windows 11 / RTX 5070 Ti. The broader support-report generator, genuine gameplay gallery, social preview and documentation website have their own next steps in the infrastructure plan.

## Checks and installation

The rebuilt launcher passes update tests using the published Revision 21 metadata, saved-setting checks, 180 actual Tk layouts and 84 XeSS popup selections. The existing renderer regression harnesses and 1,960 actual ImGui layouts also pass. Package tests reject mismatched versions, modified binaries, missing dependencies, unsafe archive paths and incorrect checksums. These automated checks complement my Windows gameplay reports; the first hosted Windows workflow run is a separate verification.

Extract the complete ZIP into its own folder and select your existing game and save folders in **Game & files**. I have kept the same saved-setting keys and update exclusions for saves, settings and mods. Do not copy only `Bloodborne.exe`.

Repository owners: enable **Issues** and the new **Actions** workflows as described in [Repository setup](../repository-setup.md). The full plan is in [Repository and release plan](../infrastructure-plan.md), alongside the existing gameplay roadmap.
