#!/usr/bin/env python3
"""Refresh the atlas's upstream tracker snapshot without changing local evidence."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
HEADERS = {"User-Agent": "CoroPerf-Evidence-Atlas", "Accept": "text/html"}
STATUS_LABELS = {
    "issueOpened": "open",
    "issueClosed": "closed",
    "issueClosedNotPlanned": "closed",
}
PULL_LABELS = {
    "pullOpen": "open",
    "pullOpened": "open",
    "pullDraft": "open",
    "draft": "open",
    "pullClosed": "closed",
    "pullMerged": "merged",
}


class IssueHeader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.states = set()

    def handle_starttag(self, tag, attrs):
        if tag == "span":
            values = dict(attrs)
            if values.get("data-testid") == "header-state":
                self.states.add(STATUS_LABELS.get(values.get("data-status")))


class PullHeader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.states = set()

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "span" and values.get("data-component") == "StateLabel":
            state = PULL_LABELS.get(values.get("data-status"))
            if state:
                self.states.add(state)


def pull_route(url):
    route = urlsplit(url)
    parts = route.path.strip("/").split("/")
    if route.hostname == "github.com" and len(parts) == 4 and parts[2] == "pull" and parts[3].isdigit():
        return parts[0], parts[1], parts[3]
    return None


def fetch_pull(url):
    owner, repo, number = pull_route(url)
    try:
        with urlopen(Request(url, headers=HEADERS), timeout=15) as response:
            canonical = pull_route(response.url)
            page = PullHeader()
            page.feed(response.read().decode("utf-8"))
        if canonical and canonical[2] == number and len(page.states) == 1:
            return page.states.pop()
    except (URLError, TimeoutError, ValueError):
        pass

    api = f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}"
    try:
        request = Request(api, headers={**HEADERS, "Accept": "application/vnd.github+json"})
        with urlopen(request, timeout=15) as response:
            document = json.load(response)
        if document["number"] == int(number) and document["state"] in {"open", "closed"}:
            return "merged" if document["merged_at"] else document["state"]
    except (URLError, TimeoutError, ValueError, KeyError):
        pass
    return "unconfirmed"


def apache_jira_key(url):
    match = re.fullmatch(r"https://issues\.apache\.org/jira/browse/([A-Z][A-Z0-9]*-\d+)", url)
    return match[1] if match else None


def fetch_apache_jira(url, key):
    result = {"url": url, "status": "unconfirmed"}
    api = f"https://issues.apache.org/jira/rest/api/2/issue/{key}?fields=status"
    try:
        request = Request(api, headers={**HEADERS, "Accept": "application/json"})
        with urlopen(request, timeout=15) as response:
            document = json.load(response)
        if document["key"] != key:
            return result
        status = document["fields"]["status"]
        category = status["statusCategory"]["key"]
        if category == "done":
            result["status"] = "closed"
            if status["name"] == "Resolved":
                result["display_status"] = "resolved"
        elif category in {"new", "indeterminate"}:
            result["status"] = "open"
    except (URLError, TimeoutError, ValueError, KeyError, TypeError):
        pass
    return result


def fetch(case):
    url = case["url"]
    if key := apache_jira_key(url):
        return fetch_apache_jira(url, key)
    route = urlsplit(url)
    parts = route.path.strip("/").split("/")
    if route.hostname != "github.com" or len(parts) != 4 or parts[2] != "issues" or not parts[3].isdigit():
        raise ValueError(f'Expected a supported upstream issue URL for {case["id"]}')
    owner, repo, _, issue_number = parts

    try:
        with urlopen(Request(url, headers=HEADERS), timeout=15) as response:
            canonical = urlsplit(response.url)
            page = IssueHeader()
            page.feed(response.read().decode("utf-8"))
        if (canonical.hostname == "github.com" and canonical.path.endswith("/issues/" + issue_number)
                and page.states in ({"open"}, {"closed"})):
            return {"url": url, "status": page.states.pop()}
    except (URLError, TimeoutError, ValueError):
        pass

    # The API provides the issue state when the public page has a different layout.
    api = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"
    try:
        request = Request(api, headers={**HEADERS, "Accept": "application/vnd.github+json"})
        with urlopen(request, timeout=15) as response:
            document = json.load(response)
        if ("pull_request" not in document and document["number"] == int(issue_number)
                and document["state"] in {"open", "closed"}):
            return {"url": url, "status": document["state"]}
    except (URLError, TimeoutError, ValueError, KeyError):
        pass
    return {"url": url, "status": "unconfirmed"}


def main():
    catalogue = json.loads((DATA / "cases.json").read_text(encoding="utf-8"))
    cases = catalogue["cases"]
    followups = catalogue.get("deferred_followups", [])
    entries = cases + followups
    fix_urls = {(case.get("fix") or {}).get("url", "") for case in entries}
    pull_urls = sorted(url for url in fix_urls if pull_route(url))
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = dict(zip((entry["id"] for entry in entries), pool.map(fetch, entries), strict=True))
        pulls = dict(zip(pull_urls, pool.map(fetch_pull, pull_urls), strict=True))
    snapshot = {
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "issues": results,
        "pull_requests": pulls,
    }
    with TemporaryDirectory(dir=DATA) as staging:
        pending = Path(staging) / "upstream-status.json"
        pending.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
        pending.replace(DATA / pending.name)
    print("Evidence issues:", dict(Counter(results[case["id"]]["status"] for case in cases)))
    if followups:
        print("Deferred follow-ups:", dict(Counter(results[row["id"]]["status"] for row in followups)))
    print("Unconfirmed:", [identifier for identifier, result in results.items() if result["status"] == "unconfirmed"])
    print("Linked pull requests:", dict(Counter(pulls.values())))
    print("Unconfirmed pull requests:", [url for url, state in pulls.items() if state == "unconfirmed"])


if __name__ == "__main__":
    main()
