# coroPerf Coroutine Evidence Atlas

A bilingual static research site for selected issues whose diagnosis benefits from coroutine stack stitching. Each issue has English and [Simplified Chinese](zh-cn/index.html) pages with its upstream report, reproduction scope, findings, and call-stack evidence. The globe in the header marks the language selector. Choose **English** or **简体中文** there to read the same page in that language. On evidence pages, switching languages preserves links to individual join points. Each retained case explains what stitching revealed. The page places a labeled join point between the two captured stack blocks and shows the original physical stack alongside it.

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

- `index.html` summarizes the issue types, diagnosis counts, and upstream status. The index supports search and filters for issue type, upstream status, and reproduction scope.
- `evidence/` contains the static issue pages.
- `research.html` summarizes representative error, scheduling, and native attribution cases.
- `zh-cn/` mirrors the index, research notes, and evidence pages in Simplified Chinese. Function names, paths to public upstream reports, and evidence labels from the graph retain their original spelling.
- `data/focus.json` lists the reviewed cases, their primary issue types, exact creation/observation pairs, and what each join establishes.
- `data/cases.json` contains the exported findings, stacks, and graph edges in the public snapshot.
- `data/upstream-status.json` records the GitHub tracker state at the last check.

To update the snapshot from the original research workspace, run the export command first. For a text edit, update the case data, the site copy in `scripts/copy_text.py`, or the research notes fragments, then rebuild. The scripts use Python 3.10 or newer and its standard library. Chinese case findings come from the study's Chinese records. Most Chinese index headlines use the leading observation from the same record.

```sh
python3 scripts/export_snapshot.py /path/to/research-workspace
python3 scripts/refresh_issue_status.py
python3 scripts/build.py
```

Refresh the GitHub snapshot when checking tracker status. The page build uses the saved snapshot offline. Commit the generated HTML with the updated data so GitHub Pages can serve the refreshed site.

## Reading the stack evidence

- A coroutine join requires nonempty stacks at both endpoints, the same captured instance, and an explicit graph edge or an audited runtime task ID within one process. Ancestors appear only when the graph records the parent relationship.
- A join point links to the two captured record IDs and names the graph edge or identity check that supports it. In the connected view, the instance label uses the first record ID for that instance in the capture.
- Each selected join supplies missing caller context or attributes the observed behavior to its initiating task or request. The original physical stack remains next to its connected view.
- Count each previously reported issue once by its main symptom or diagnostic question. Use `functional` for functional failures and correctness issues, `performance` for observed performance problems, `profiling` for CPU or wait-time attribution, and `debugging` for recovering missing diagnostic context.
- To add an issue, record its primary type, diagnostic contribution, and reviewed record IDs in `data/focus.json`. The exporter checks that each pair is a valid instance join before it can enter the catalog.

Instrument Serif is distributed under the [SIL Open Font License](assets/fonts/OFL.txt).
