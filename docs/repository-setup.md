# GitHub settings for this fork

The source files can provide workflows and report forms, but the repository settings have to enable their use. I checked the repository during the Revision 22 infrastructure work: Issues were disabled and no workflows had been committed yet.

1. Open **Settings → General → Features** and enable **Issues**. The Bug report, Performance regression and Feature request forms will then appear under New issue.
2. Open **Actions**. If GitHub asks to enable workflows on the fork, choose **I understand my workflows, go ahead and enable them**.
3. In **Settings → Actions → General**, allow the pinned workflows' actions. They use `actions/checkout`, `actions/setup-python`, `actions/upload-artifact` and `msys2/setup-msys2`. Keep the default token read-only; these workflows do not need permission to publish releases or write to the repository.
4. Run **Regression checks**, then **Windows build and package** from Actions using the `windows` branch. The Windows job produces a candidate ZIP, checksum, identity/provenance and a prepared release page. Review the results and test the candidate before publishing it.
5. Run **Published release integrity** for the existing Revision 21 tag to check its assets and source. The workflow also runs after future release publication.

Optional: enable **Security → Private vulnerability reporting** before directing private security reports there. [SECURITY.md](../SECURITY.md) also describes the fallback when that feature is unavailable.

A social-preview image is uploaded under **Settings → General → Social preview**. The planned 1280 × 640 export will use the workshop painting and crowned TK emblem. GitHub Pages remains a later option; no site is enabled by this revision.

Branch rules are a separate choice. Once the checks have successful runs, I can require the Regression checks status on pull requests without blocking recovery work before the first run.

GitHub references: [Actions settings](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository), [fork workflow events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows), [issue forms](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/creating-an-issue).
