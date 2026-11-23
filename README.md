# coroPerf Coroutine Evidence Atlas

An English-language static research site for the coroPerf issue corpus. Each issue has a permalink with its upstream report, reproduction scope, findings, and call-stack evidence. When the capture supplies a valid join, the default view compares the connected stack with the physical stack on the same execution record.

## Publish to GitHub Pages

1. Create a GitHub repository and push this directory’s contents to its `main` branch. Include `.nojekyll` at the repository root.
2. Open **Settings → Pages**. Under **Build and deployment**, select **Deploy from a branch**, then **main** and **/(root)**.
3. Open the URL shown in Pages settings. A typical project site appears at `https://OWNER.github.io/REPOSITORY/`.

GitHub Pages serves the checked-in files directly. Fonts, filters, and issue evidence use relative URLs. [GitHub Pages publishing-source documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)

## Preview and update

From the repository root, run the following command and open [the local preview](http://localhost:8000/).

```sh
python3 -m http.server 8000
```

- `index.html` is the issue index with search and evidence filters.
- `evidence/` contains the static issue pages.
- `research.html` summarizes the performance and assembly measurements.
- `data/cases.json` contains public case findings, exported frame sequences, endpoint record IDs, and the types of recorded links.

To update the snapshot from the original research workspace, run the export command first. For an edit to the published text or data, update `data/cases.json` or the research notes fragment, then rebuild. The scripts use Python 3.10 or newer and its standard library.

```sh
python3 scripts/export_snapshot.py /path/to/research-workspace
python3 scripts/build.py
```

Commit the generated HTML with the updated snapshot so GitHub Pages can serve the refreshed site.

## Reading the stack evidence

- A coroutine join requires nonempty stacks at both endpoints, the same captured instance, and an explicit graph edge or an audited runtime task ID within one process. Ancestors appear only when the graph records the parent relationship.
- Renderer chains use recorded JSX ownership and the physical frames of the linked rendering observation.
- The case labels distinguish issue-review observations from additional observations in the same capture. Each page shows up to three representative joins. Physical frames stay available when the capture lacks a verified join.
- The coverage count describes the published capture graphs. The reviewed origin lower bound describes issue-relevant origins in the full study.

Instrument Serif is distributed under the [SIL Open Font License](assets/fonts/OFL.txt).
