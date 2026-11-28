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

- `index.html` groups the cases by language in one table. Each row shows its upstream tracker state, repair evidence, and primary CoroPerf contribution. Search and filters cover language, upstream tracker state, contribution, reported issue type, and reproduction scope.
- `evidence/` contains the static issue pages.
- `research.html` groups the same issues by their primary diagnostic contribution, links to each call-stack comparison, and lists deferred follow-ups.
- `zh-cn/` mirrors the index, research notes, and evidence pages in Simplified Chinese. Function names, paths to public upstream reports, and evidence labels from the graph retain their original spelling.
- `data/focus.json` lists the reviewed cases, their reported issue types, primary diagnostic contributions, exact creation/observation pairs, and what each join establishes.
- `data/cases.json` contains the exported findings, stacks, and graph edges in the public snapshot.
- `data/upstream-status.json` records issue and linked repair PR states at the last check.
- `data/case-classification.csv` exports the bilingual paper taxonomy, evidence scope, repair evidence, and upstream issue and linked GitHub PR states.

To update the snapshot from the original research workspace, run the export command first. For a text edit, update the case data, site copy in `scripts/copy_text.py`, or optional case summaries in `scripts/research-notes.json`, then rebuild. The scripts use Python 3.10 or newer and its standard library. Chinese case findings come from the study's Chinese records. Most Chinese index headlines use the leading observation from the same record.

```sh
python3 scripts/export_snapshot.py /path/to/research-workspace
python3 scripts/refresh_issue_status.py
python3 scripts/build.py
```

Refresh the upstream snapshot when checking tracker status. The deferred list supports GitHub, Apache Jira and MySQL Bugs reports. The page build uses the saved snapshot offline. Commit the generated HTML with the updated data so GitHub Pages can serve the refreshed site.

## Reading the stack evidence

- A coroutine join requires nonempty stacks at both endpoints, the same captured instance, and an explicit graph edge or an audited runtime task ID within one process. Ancestors appear only when the graph records the parent relationship.
- The connected view starts at the execution stack and follows the joins back to creation. A join point links to the two captured record IDs and names the graph edge or identity check. The instance label uses the first record ID for that instance in the capture.
- Fix evidence is listed separately from the issue's upstream status. The evidence page can link to a tested repair, a merged change, a proposal or application workaround tested locally, or an upstream documentation update.
- Each selected join supplies missing caller context or attributes the observed behavior to its initiating task or request. The original physical stack remains next to its connected view.
- Assign one diagnostic contribution from the main fact established by the selected join. Record caller recovery, request and result handoffs, failure and task lifecycle, scheduling and contention, or performance cost attribution.
- Count each previously reported issue once by its main symptom or diagnostic question. Use `functional` for functional failures and correctness issues, `performance` for observed performance problems, `profiling` for CPU or wait-time attribution, and `debugging` for recovering missing diagnostic context.
- To add an issue, record its primary type, diagnostic contribution, and reviewed record IDs in `data/focus.json`. The exporter checks that each pair is a valid instance join before it can enter the catalog.

Instrument Serif is distributed under the [SIL Open Font License](assets/fonts/OFL.txt).

## Automatic discovery progress

[Search progress](discovery.html) and [搜索进度](zh-cn/discovery.html) show the separate, unverified discovery queue, framework coverage, official tracker windows, skipped review entries, and collection errors. Candidate counts do not change the verified evidence catalog. `scripts/build_discovery.py` renders both pages from `data/discovery.json`. In the research workspace, `research/github-issue-discovery/automation/README.md` describes the read-only scanner and two-hour report service.

[GitHub safety review](discovery.html#security-review) and [安全相关 GitHub issue](zh-cn/discovery.html#security-review) collect the persistent manual holds, automatic approval review rejections, and wording signals. Search by repository, issue number, title, or recorded reason; filter by hold source. Each row links to the original issue and preserves known local execution history. Signals and review rejections do not establish a security vulnerability. User-requested skips and environment or time-budget deferrals remain available under **All deferred entries**.

The classification CSV uses `upstream_status` for the issue state, covering GitHub and Apache Jira. Its issue URL identifies the tracker.

Official database discovery uses PostgreSQL archive relevance/date windows and MySQL Bugs relevance/update windows. The discovery page counts mail messages separately from approximate subject groups, displays native MySQL categories and states, and keeps these metrics separate from GitHub heat. Source windows and their retrieval times are included in the report download.

Regular discovery also covers Reactor, Netty and PostgreSQL JDBC, using framework-specific terms for Mono/Flux, ChannelFuture and LazyCleaner. Preparation failures have their own review status; they are distinct from unavailable external environments and safety holds.

## Open root-cause investigations

[Open investigations](open-issues.html) and [待分析 Issue](zh-cn/open-issues.html) provide a separate, ordered discussion queue. The review distinguishes unresolved root causes, partial upstream results, repair commits, workarounds, and incomplete status checks. Proposed CoroPerf observations are not verified diagnoses. The original discovery and verified-case records are preserved.

Update `data/open-root-cause-review.json`, then run `python3 scripts/build_open_root_cause_review.py` to rebuild both language pages. Each issue records its next step, the additional identity/resource evidence required, and the controls needed before a root-cause claim. The shared page template links to this queue; publish generated pages, the data, and `assets/open-issues.css` together.

The first independent investigation is [Asio #1720](investigations/asio-1720.html), also available in [Chinese](zh-cn/investigations/asio-1720.html). Its record is `data/investigations/asio-1720.json`; run `python3 scripts/build_investigation.py` to rebuild both pages. It is a planned investigation with no local reproduction, root-cause or repair result yet, and remains outside the verified-case catalog.

The [Reactor disposal-worker note](evidence/reactor-4478-resource.html) and its [Chinese version](zh-cn/evidence/reactor-4478-resource.html) are supplemental resource provenance outside the selected case catalogue. Rebuild them from `data/reactor-4478-verification.json` with `python3 scripts/build_reactor_resource.py`. They document one execution, the explicit extra factory observer, native versus recovered stacks, and the untested repair direction.

The pending C# runtime #117652 result pages were withdrawn at the user's request. The [skip record](data/dotnet-117652-user-skip.json) preserves their status; earlier local evidence remains historical and no further execution or attribution is planned for this issue.

The supplemental [gRPC Call resource graph](evidence/grpc-43462-resource-report.html) records one bounded loopback execution and an explicit weak API observer. It recovers an abandoned Call's application origin; it does not establish coroutine execution, a C-core ownership graph or unbounded resource exhaustion. The selected case catalogue is unchanged.
