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

- `index.html` groups the cases by language in one table. Each row shows its GitHub state, repair evidence, and primary CoroPerf contribution. Search and filters cover language, GitHub state, contribution, reported issue type, and reproduction scope.
- `evidence/` contains the static issue pages.
- `research.html` groups the same issues by their primary diagnostic contribution and links to each call-stack comparison.
- `zh-cn/` mirrors the index, research notes, and evidence pages in Simplified Chinese. Function names, paths to public upstream reports, and evidence labels from the graph retain their original spelling.
- `data/focus.json` lists the reviewed cases, their reported issue types, primary diagnostic contributions, exact creation/observation pairs, and what each join establishes.
- `data/cases.json` contains the exported findings, stacks, and graph edges in the public snapshot.
- `data/upstream-status.json` records issue and linked repair PR states at the last check.
- `data/case-classification.csv` exports the bilingual paper taxonomy, evidence scope, repair evidence, and linked GitHub issue and PR states.

To update the snapshot from the original research workspace, run the export command first. For a text edit, update the case data, site copy in `scripts/copy_text.py`, or optional case summaries in `scripts/research-notes.json`, then rebuild. The scripts use Python 3.10 or newer and its standard library. Chinese case findings come from the study's Chinese records. Most Chinese index headlines use the leading observation from the same record.

```sh
python3 scripts/export_snapshot.py /path/to/research-workspace
python3 scripts/refresh_issue_status.py
python3 scripts/build.py
```

Refresh the GitHub snapshot when checking tracker status. The page build uses the saved snapshot offline. Commit the generated HTML with the updated data so GitHub Pages can serve the refreshed site.

## Reading the stack evidence

- A coroutine join requires nonempty stacks at both endpoints, the same captured instance, and an explicit graph edge or an audited runtime task ID within one process. Ancestors appear only when the graph records the parent relationship.
- The connected view starts at the execution stack and follows the joins back to creation. A join point links to the two captured record IDs and names the graph edge or identity check. The instance label uses the first record ID for that instance in the capture.
- Fix evidence is listed separately from the issue's GitHub status. The evidence page can link to a tested repair, a merged change, a proposal or application workaround tested locally, or an upstream documentation update.
- Each selected join supplies missing caller context or attributes the observed behavior to its initiating task or request. The original physical stack remains next to its connected view.
- Assign one diagnostic contribution from the main fact established by the selected join. Record caller recovery, request and result handoffs, failure and task lifecycle, scheduling and contention, or performance cost attribution.
- Count each previously reported issue once by its main symptom or diagnostic question. Use `functional` for functional failures and correctness issues, `performance` for observed performance problems, `profiling` for CPU or wait-time attribution, and `debugging` for recovering missing diagnostic context.
- To add an issue, record its primary type, diagnostic contribution, and reviewed record IDs in `data/focus.json`. The exporter checks that each pair is a valid instance join before it can enter the catalog.

Instrument Serif is distributed under the [SIL Open Font License](assets/fonts/OFL.txt).
