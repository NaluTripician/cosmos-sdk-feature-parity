"""
Fetch live GitHub issue metadata for every `issues[].url` in
`data/features.yaml` and cache the results to
`data/scraped/issues.json`.

The site consumes the cache so issue chips can render live open/closed
state and titles instead of the static `title` stored in YAML.

Output shape:

    {
      "scraped_at": "2026-04-23T22:00:00Z",
      "issues": {
        "https://github.com/Azure/...": {
          "url": "https://github.com/Azure/...",
          "state": "open",
          "state_reason": null,
          "title": "...",
          "labels": ["area/cosmos"],
          "assignees": ["alice"],
          "updated_at": "2026-04-22T14:10:00Z"
        },
        ...
      },
      "errors": [
        {"url": "...", "status": 404, "message": "Not Found"}
      ]
    }

Non-github.com URLs are recorded under `errors` with `status: "skipped"`
so the dashboard can still render them (falling back to the static
title). A 404 or auth error for a single URL does not fail the run —
the bad entry goes into `errors` and the remaining URLs continue.

Usage:
    GITHUB_TOKEN=ghp_... python scripts/sync_issues.py

Exit codes:
    0 — output written (even if some URLs failed individually)
    2 — no URLs found in features.yaml (nothing to do; caller should
        still consider this non-fatal)
    1 — fatal error (bad YAML, network layer crash, etc.)
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib import error as urlerror
from urllib import request as urlrequest

import yaml

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
FEATURES_PATH = REPO_ROOT / "data" / "features.yaml"
OUT_PATH = REPO_ROOT / "data" / "scraped" / "issues.json"

# Match https://github.com/{owner}/{repo}/issues/{n}    (also pull/{n})
GH_ISSUE_RE = re.compile(
    r"^https?://github\.com/([^/]+)/([^/]+)/(?:issues|pull)/(\d+)(?:[/?#].*)?$"
)

USER_AGENT = "cosmos-sdk-feature-parity-sync/1.0"


def _collect_issue_urls(features: dict) -> list[str]:
    urls: set[str] = set()
    for cat in features.get("categories") or []:
        for feat in cat.get("features") or []:
            if not isinstance(feat, dict):
                continue
            for cell in (feat.get("sdks") or {}).values():
                if not isinstance(cell, dict):
                    continue
                for issue in cell.get("issues") or []:
                    if isinstance(issue, dict):
                        url = issue.get("url")
                        if isinstance(url, str) and url.strip():
                            urls.add(url.strip())
    return sorted(urls)


def _gh_api_get(api_url: str, token: str | None) -> tuple[int, dict | None, str]:
    req = urlrequest.Request(
        api_url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    try:
        with urlrequest.urlopen(req, timeout=30) as resp:
            status = resp.status
            body = resp.read().decode("utf-8")
            return status, json.loads(body), ""
    except urlerror.HTTPError as e:
        return e.code, None, f"{e.code} {e.reason}"
    except Exception as e:  # noqa: BLE001
        return 0, None, str(e)


def _fetch_one(url: str, token: str | None) -> tuple[dict | None, dict | None]:
    m = GH_ISSUE_RE.match(url)
    if not m:
        return None, {"url": url, "status": "skipped", "message": "not a github.com issue/pr URL"}
    owner, repo, number = m.group(1), m.group(2), m.group(3)
    api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{number}"
    status, data, err = _gh_api_get(api_url, token)
    if status != 200 or data is None:
        return None, {"url": url, "status": status or "error", "message": err or "unknown error"}
    record = {
        "url": url,
        "state": data.get("state"),
        "state_reason": data.get("state_reason"),
        "title": data.get("title"),
        "labels": [l.get("name") for l in (data.get("labels") or []) if isinstance(l, dict) and l.get("name")],
        "assignees": [a.get("login") for a in (data.get("assignees") or []) if isinstance(a, dict) and a.get("login")],
        "updated_at": data.get("updated_at"),
        "html_url": data.get("html_url"),
    }
    return record, None


def main(argv: list[str]) -> int:
    with open(FEATURES_PATH, "r", encoding="utf-8") as f:
        features = yaml.safe_load(f)

    urls = _collect_issue_urls(features)
    if not urls:
        print("No issue URLs found in features.yaml; nothing to sync.")
        return 2

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print(
            "warning: no GITHUB_TOKEN / GH_TOKEN set; falling back to "
            "unauthenticated API (60 requests/hour, strict rate limit).",
            file=sys.stderr,
        )

    issues: dict[str, dict] = {}
    errors: list[dict] = []
    for i, url in enumerate(urls, start=1):
        record, err = _fetch_one(url, token)
        if record is not None:
            issues[url] = record
        if err is not None:
            errors.append(err)
        # Simple pacing so we stay well under the 5000/hour authenticated limit.
        if i < len(urls):
            time.sleep(0.2)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "scraped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "issues": issues,
        "errors": errors,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")

    print(
        f"Wrote {OUT_PATH.relative_to(REPO_ROOT)}: "
        f"{len(issues)} issue(s), {len(errors)} error(s)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
