"""
Scrape retry-policy source files from each Cosmos DB SDK repo and detect drift.

Reads `audit_refs` from `data/retries.yaml` to learn which files to watch.
Fetches each file at HEAD of its repo's default branch, normalizes line endings,
hashes the content (SHA-256), and records the blob SHA, last-touching commit,
and normalized content hash.

When a file's normalized content hash differs from the previous run, the SDK
is marked `drift_detected: true` and an entry is appended to
`data/scraped/retry_drift.md`. The scraper never mutates `data/retries.yaml`
itself — a human must re-audit and update curated retry behavior.

Usage:
    python scripts/scrape_retry_policies.py

Environment:
    GITHUB_TOKEN - optional; increases API rate limit.
"""

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

GITHUB_API = "https://api.github.com"
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
DATA_DIR = REPO_ROOT / "data"
SCRAPED_DIR = DATA_DIR / "scraped"
LATEST_PATH = SCRAPED_DIR / "retry_policies_latest.json"
DRIFT_REPORT = SCRAPED_DIR / "retry_drift.md"


def github_headers(raw: bool = False) -> dict:
    headers = {
        "Accept": "application/vnd.github.v3.raw" if raw else "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def load_retries_config() -> dict:
    """Load retries.yaml (source of truth for which files to watch)."""
    with open(DATA_DIR / "retries.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_sdks_config() -> dict:
    with open(DATA_DIR / "sdks.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["sdks"]


def load_previous_snapshot() -> dict | None:
    if LATEST_PATH.exists():
        with open(LATEST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def fetch_file_content(repo: str, path: str) -> tuple[str, str]:
    """Return (raw_content_text, blob_sha) for a file at HEAD of the default branch."""
    url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
    resp = requests.get(url, headers=github_headers(), timeout=30)
    resp.raise_for_status()
    data = resp.json()
    blob_sha = data.get("sha", "")
    # Fetch raw
    raw_resp = requests.get(url, headers=github_headers(raw=True), timeout=30)
    raw_resp.raise_for_status()
    return raw_resp.text, blob_sha


def fetch_latest_commit(repo: str, path: str) -> dict | None:
    """Return the most recent commit touching a path."""
    url = f"{GITHUB_API}/repos/{repo}/commits"
    params = {"path": path, "per_page": 1}
    resp = requests.get(url, headers=github_headers(), params=params, timeout=30)
    resp.raise_for_status()
    commits = resp.json()
    if not commits:
        return None
    c = commits[0]
    return {
        "sha": c["sha"],
        "date": c["commit"]["committer"]["date"],
        "message": c["commit"]["message"].split("\n")[0][:200],
        "url": c["html_url"],
    }


def normalize(content: str) -> str:
    """Normalize line endings and trailing whitespace for stable hashing."""
    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(line.rstrip() for line in lines)


def content_hash(content: str) -> str:
    return "sha256:" + hashlib.sha256(normalize(content).encode("utf-8")).hexdigest()


def scrape_all() -> dict:
    retries_config = load_retries_config()
    sdks = load_sdks_config()
    audit_refs = retries_config.get("audit_refs", {})

    previous = load_previous_snapshot() or {}
    prev_sdks = previous.get("sdks", {})

    now = datetime.now(timezone.utc).isoformat()
    result = {"scraped_at": now, "sdks": {}}
    drift_entries: list[str] = []

    for sdk_id, files in audit_refs.items():
        sdk = sdks.get(sdk_id)
        if not sdk:
            print(f"  WARN: no sdks.yaml entry for '{sdk_id}', skipping", file=sys.stderr)
            continue

        repo = sdk["repo"]
        print(f"Scraping retry policies for {sdk['name']} ({repo})...")

        prev_files_by_path = {
            f["path"]: f for f in prev_sdks.get(sdk_id, {}).get("files", [])
        }

        sdk_files: list[dict] = []
        sdk_drift = False

        for path in files:
            try:
                content, blob_sha = fetch_file_content(repo, path)
                commit = fetch_latest_commit(repo, path)
                chash = content_hash(content)
                entry = {
                    "path": path,
                    "blob_sha": blob_sha,
                    "content_hash": chash,
                    "last_commit_sha": commit["sha"] if commit else None,
                    "last_commit_date": commit["date"] if commit else None,
                    "last_commit_message": commit["message"] if commit else None,
                    "last_commit_url": commit["url"] if commit else None,
                }

                prev = prev_files_by_path.get(path)
                if prev and prev.get("content_hash") and prev["content_hash"] != chash:
                    sdk_drift = True
                    drift_entries.append(
                        f"- **{sdk['name']}** `{path}`\n"
                        f"  - prev hash: `{prev['content_hash']}`\n"
                        f"  - new hash:  `{chash}`\n"
                        f"  - new commit: [{entry['last_commit_sha'][:8] if entry['last_commit_sha'] else 'unknown'}]"
                        f"({entry['last_commit_url']}) — {entry['last_commit_message']}\n"
                    )

                sdk_files.append(entry)
                print(f"  ok  {path}")
            except requests.HTTPError as e:
                print(f"  ERROR {path}: {e}", file=sys.stderr)
                sdk_files.append({"path": path, "error": str(e)})

        result["sdks"][sdk_id] = {
            "name": sdk["name"],
            "repo": repo,
            "files": sdk_files,
            "drift_detected": sdk_drift,
        }

    return result, drift_entries


def write_outputs(result: dict, drift_entries: list[str]) -> None:
    SCRAPED_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    dated = SCRAPED_DIR / f"retry_policies_{today}.json"
    with open(dated, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    with open(LATEST_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"\nSaved: {dated}")
    print(f"Saved: {LATEST_PATH}")

    if drift_entries:
        header = (
            f"# Retry-policy drift detected — {today}\n\n"
            "The following retry-policy source files have changed since the last scrape. "
            "Re-audit and update `data/retries.yaml` to reflect any behavioral changes.\n\n"
        )
        with open(DRIFT_REPORT, "w", encoding="utf-8") as f:
            f.write(header + "\n".join(drift_entries) + "\n")
        print(f"Saved drift report: {DRIFT_REPORT}")
    else:
        # Clear any previous drift report so stale reports don't linger
        if DRIFT_REPORT.exists():
            DRIFT_REPORT.unlink()
        print("No drift detected.")


def main() -> int:
    print("Starting retry-policy scrape...\n")
    try:
        result, drift_entries = scrape_all()
    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        return 1

    write_outputs(result, drift_entries)

    print("\n=== Summary ===")
    for sdk_id, data in result["sdks"].items():
        errors = [f for f in data["files"] if "error" in f]
        drift = " DRIFT" if data["drift_detected"] else ""
        print(
            f"  {data['name']:<8} {len(data['files'])} file(s), "
            f"{len(errors)} error(s){drift}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
