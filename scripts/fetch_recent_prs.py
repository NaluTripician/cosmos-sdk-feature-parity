"""
Fetch merged PRs from the last 14 days that touch each SDK's Cosmos subtree.

For each SDK in data/sdks.yaml, queries the GitHub API for pull requests that
merged in the trailing 14-day window and whose file changes land in the
Cosmos-specific path for that SDK (repo-wide for the single-package .NET repo).
Writes the consolidated result to data/scraped/recent_prs_latest.json so the
dashboard can surface a "Recent Activity" view per SDK.

Usage:
    python scripts/fetch_recent_prs.py

Environment:
    GITHUB_TOKEN - GitHub token (recommended; the unauth rate limit is too low
                   to reliably crawl five SDK repos in one run).
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import yaml

GITHUB_API = "https://api.github.com"
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
DATA_DIR = REPO_ROOT / "data"
SCRAPED_DIR = DATA_DIR / "scraped"

WINDOW_DAYS = 14
MAX_PRS_PER_SDK = 25

# Cosmos-specific path prefix per SDK. ``None`` means the SDK repo is
# single-package and every PR counts.
#
# GitHub's commits API treats ``?path=`` as a prefix match, so using the
# ``sdk/cosmos`` directory root for java/python/rust captures every sibling
# Cosmos package (e.g. ``azure-resourcemanager-cosmos``, ``azure-mgmt-cosmosdb``,
# ``azure_data_cosmos_driver``) instead of only the flagship client library.
SDK_PATH_FILTERS: dict[str, str | None] = {
    # Single-package repo; the whole repo is Cosmos, no path filter needed.
    "dotnet": None,
    # Java mono-repo: match anything under sdk/cosmos/ (azure-cosmos,
    # azure-resourcemanager-cosmos, azure-cosmos-encryption, ...).
    "java": "sdk/cosmos",
    # Python mono-repo: match anything under sdk/cosmos/ (azure-cosmos,
    # azure-mgmt-cosmosdb, azure-cosmos-encryption, ...).
    "python": "sdk/cosmos",
    # Go mono-repo: Cosmos data-plane SDK lives under sdk/data/azcosmos.
    "go": "sdk/data/azcosmos",
    # Rust mono-repo: match anything under sdk/cosmos/ (azure_data_cosmos,
    # azure_data_cosmos_driver, ...).
    "rust": "sdk/cosmos",
}


def github_headers() -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get(url: str, params: dict | None = None) -> requests.Response | None:
    """GET with soft handling of rate limits and transient errors."""
    try:
        resp = requests.get(url, headers=github_headers(), params=params, timeout=30)
    except requests.RequestException as e:
        print(f"  ! network error {url}: {e}", file=sys.stderr)
        return None

    if resp.status_code == 403 and "rate limit" in resp.text.lower():
        reset = resp.headers.get("X-RateLimit-Reset")
        print(f"  ! rate limited (reset={reset}); aborting further calls", file=sys.stderr)
        return None
    if resp.status_code >= 400:
        print(f"  ! {resp.status_code} {url} :: {resp.text[:200]}", file=sys.stderr)
        return None
    return resp


def _get_json(url: str, params: dict | None = None):
    """GET and safely parse JSON. Returns ``None`` on network error,
    HTTP error, or non-JSON response body (e.g. GitHub maintenance / abuse
    rate-limit HTML pages). Callers should treat ``None`` as "no data" and
    move on rather than crashing the whole scrape."""
    resp = _get(url, params)
    if resp is None:
        return None
    try:
        return resp.json()
    except ValueError as e:
        snippet = (resp.text or "")[:200].replace("\n", " ")
        print(
            f"  ! non-JSON response from {url} (status {resp.status_code}): "
            f"{snippet!r} ({e})",
            file=sys.stderr,
        )
        return None


def load_sdk_config() -> dict:
    with open(DATA_DIR / "sdks.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["sdks"]


def fetch_recent_prs_for_sdk(sdk_id: str, repo: str, path_prefix: str | None,
                             since: datetime) -> list[dict]:
    """Return merged PRs touching path_prefix since ``since`` (UTC)."""
    since_iso = since.strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{sdk_id}] {repo} path={path_prefix or '<repo>'} since={since_iso}")

    pr_numbers: set[int] = set()

    if path_prefix is None:
        # Single-package repo: list recently closed PRs, keep merged ones in window.
        for page in range(1, 4):  # up to 150 PRs
            page_prs = _get_json(
                f"{GITHUB_API}/repos/{repo}/pulls",
                params={
                    "state": "closed",
                    "sort": "updated",
                    "direction": "desc",
                    "per_page": 50,
                    "page": page,
                },
            )
            if not page_prs:
                break
            stop = False
            for pr in page_prs:
                merged_at = pr.get("merged_at")
                updated_at = pr.get("updated_at")
                if not merged_at:
                    if updated_at and updated_at < since_iso:
                        # Sorted desc by update; once we pass the window in
                        # updates we can stop paginating.
                        stop = True
                    continue
                if merged_at < since_iso:
                    stop = True
                    continue
                pr_numbers.add(pr["number"])
            if stop:
                break
    else:
        # Mono-repo: walk commits touching the path page-by-page and map each
        # commit to its PR(s). We cap by the number of *unique PRs* seen, not
        # by the number of commits walked — a single verbose PR can easily
        # contribute dozens of commits, and we don't want that to short-circuit
        # the scrape before we've found other recent PRs.
        total_commits = 0
        for page in range(1, 4):  # up to 300 commits
            page_commits = _get_json(
                f"{GITHUB_API}/repos/{repo}/commits",
                params={
                    "path": path_prefix,
                    "since": since_iso,
                    "per_page": 100,
                    "page": page,
                },
            )
            if not page_commits:
                break
            total_commits += len(page_commits)

            hit_cap = False
            for commit in page_commits:
                sha = commit.get("sha")
                if not sha:
                    continue
                commit_prs = _get_json(f"{GITHUB_API}/repos/{repo}/commits/{sha}/pulls")
                if not commit_prs:
                    continue
                for pr in commit_prs:
                    if pr.get("merged_at") and pr["merged_at"] >= since_iso:
                        pr_numbers.add(pr["number"])
                if len(pr_numbers) >= MAX_PRS_PER_SDK:
                    hit_cap = True
                    break

            if hit_cap:
                break
            if len(page_commits) < 100:
                break
        print(f"  {total_commits} commits walked, {len(pr_numbers)} unique PRs")

    # Hydrate each PR (author, labels, title, merged_at).
    out: list[dict] = []
    for num in pr_numbers:
        pr = _get_json(f"{GITHUB_API}/repos/{repo}/pulls/{num}")
        if not pr:
            continue
        if not pr.get("merged_at"):
            continue
        out.append({
            "number": pr["number"],
            "title": pr.get("title", ""),
            "url": pr.get("html_url", f"https://github.com/{repo}/pull/{pr['number']}"),
            "merged_at": pr["merged_at"],
            "author": (pr.get("user") or {}).get("login", ""),
            "labels": [lbl.get("name") for lbl in pr.get("labels", []) if lbl.get("name")],
        })

    out.sort(key=lambda p: p["merged_at"], reverse=True)
    return out[:MAX_PRS_PER_SDK]


def main() -> int:
    sdks = load_sdk_config()
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=WINDOW_DAYS)

    by_sdk: dict[str, list[dict]] = {}
    for sdk_id, sdk in sdks.items():
        path_prefix = SDK_PATH_FILTERS.get(sdk_id)
        try:
            prs = fetch_recent_prs_for_sdk(sdk_id, sdk["repo"], path_prefix, since)
        except Exception as e:
            print(f"[{sdk_id}] failed: {e}", file=sys.stderr)
            prs = []
        print(f"[{sdk_id}] -> {len(prs)} PRs")
        by_sdk[sdk_id] = prs
        # Light throttle so we don't burn the search/core quotas back-to-back.
        time.sleep(0.2)

    SCRAPED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SCRAPED_DIR / "recent_prs_latest.json"
    payload = {
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_days": WINDOW_DAYS,
        "by_sdk": by_sdk,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
