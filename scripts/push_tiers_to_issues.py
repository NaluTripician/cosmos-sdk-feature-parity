"""Push tier + per-issue labels from features.yaml onto linked GitHub issues.

For every `issues[].url` under a SDK cell, this script computes the set of
labels the issue SHOULD carry based on:

  1. The cell's `tier` looked up in the doc-level `tier_label_map`
     (e.g. `ga_blocker -> parity/ga-blocker`).
  2. Any explicit `issues[i].labels` list on the issue entry.

It then diffs against the labels already on the issue and, unless
`--apply` is given, prints the plan without mutating anything. The script
only ADDS labels — it never removes labels it doesn't manage, because the
target repos (Azure/azure-sdk-for-*) have their own label taxonomies we
don't own.

Labels considered "managed by this tool" are the union of:
  - all values in `tier_label_map`
  - all strings that ever appear in any `issues[].labels`
So if a cell's tier changes, the old tier label IS removed from the issue.

Auth: uses ISSUE_WRITE_TOKEN if set (PAT with `issues:write` on each
target repo), otherwise falls back to GITHUB_TOKEN. Cross-repo writes
normally require a classic PAT or a fine-grained token — the default
GITHUB_ACTIONS token cannot write to other repos.

Usage:
    python scripts/push_tiers_to_issues.py            # dry run
    python scripts/push_tiers_to_issues.py --apply    # actually mutate

Exit codes:
    0  clean (no changes needed OR --apply succeeded)
    1  fatal error (bad config, HTTP failure, etc.)
    2  changes WERE proposed but --apply not given (dry-run signal for CI)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
FEATURES_PATH = REPO_ROOT / "data" / "features.yaml"

GH_ISSUE_RE = re.compile(
    r"^https?://github\.com/([^/]+)/([^/]+)/(?:issues|pull)/(\d+)/?$"
)

API_BASE = "https://api.github.com"


def _auth_token() -> str | None:
    return os.environ.get("ISSUE_WRITE_TOKEN") or os.environ.get("GITHUB_TOKEN")


def _api(
    method: str, path: str, token: str | None, body: dict | None = None,
) -> tuple[int, dict | list | None]:
    url = f"{API_BASE}{path}"
    data = None
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "cosmos-sdk-feature-parity-tier-writeback",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = resp.read()
            return resp.status, (json.loads(payload) if payload else None)
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(body_text)
        except Exception:
            return e.code, {"raw": body_text}


def _collect(features_doc: dict) -> tuple[dict[str, dict], set[str]]:
    """Return ({url: plan}, managed_label_set).

    plan = {owner, repo, number, url, desired_labels: set[str], sources: list[str]}
    managed_label_set = all labels we consider ours to add/remove.
    """
    tier_label_map = features_doc.get("tier_label_map") or {}
    managed: set[str] = set()
    for v in tier_label_map.values():
        if isinstance(v, str) and v.strip():
            managed.add(v)

    plans: dict[str, dict] = {}
    for cat in features_doc.get("categories") or []:
        for feat in cat.get("features") or []:
            feat_id = feat.get("id", "?")
            for sdk_id, cell in (feat.get("sdks") or {}).items():
                if not isinstance(cell, dict):
                    continue
                tier = cell.get("tier")
                tier_label = tier_label_map.get(tier) if isinstance(tier, str) else None
                for issue in cell.get("issues") or []:
                    if not isinstance(issue, dict):
                        continue
                    url = (issue.get("url") or "").strip()
                    if not url:
                        continue
                    m = GH_ISSUE_RE.match(url)
                    if not m:
                        continue
                    owner, repo, number = m.group(1), m.group(2), int(m.group(3))
                    plan = plans.setdefault(url, {
                        "owner": owner, "repo": repo, "number": number, "url": url,
                        "desired": set(), "sources": [],
                    })
                    source = f"{feat_id}/{sdk_id}"
                    plan["sources"].append(source)
                    if tier_label:
                        plan["desired"].add(tier_label)
                    for lab in issue.get("labels") or []:
                        if isinstance(lab, str) and lab.strip():
                            plan["desired"].add(lab.strip())
                            managed.add(lab.strip())
    return plans, managed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true",
        help="Actually mutate issue labels. Default: dry-run only.",
    )
    parser.add_argument(
        "--pace", type=float, default=0.25,
        help="Seconds to sleep between write requests (default 0.25).",
    )
    args = parser.parse_args()

    if not FEATURES_PATH.exists():
        print(f"ERROR: {FEATURES_PATH} not found", file=sys.stderr)
        return 1
    with FEATURES_PATH.open("r", encoding="utf-8") as fh:
        doc = yaml.safe_load(fh) or {}

    plans, managed = _collect(doc)
    if not plans:
        print("No linked issues to process.")
        return 0
    if not managed:
        print(
            "WARNING: no labels would be managed by this run "
            "(tier_label_map empty and no issues[].labels set).",
            file=sys.stderr,
        )

    token = _auth_token()
    if args.apply and not token:
        print(
            "ERROR: --apply requires ISSUE_WRITE_TOKEN or GITHUB_TOKEN "
            "(a PAT with issues:write on target repos).",
            file=sys.stderr,
        )
        return 1

    changes_proposed = 0
    errors = 0
    for url, plan in sorted(plans.items()):
        owner, repo, number = plan["owner"], plan["repo"], plan["number"]
        status, payload = _api(
            "GET", f"/repos/{owner}/{repo}/issues/{number}", token,
        )
        if status != 200 or not isinstance(payload, dict):
            print(f"  ! {url}: GET failed (status={status})", file=sys.stderr)
            errors += 1
            continue
        current = {
            lab["name"] for lab in payload.get("labels") or [] if "name" in lab
        }
        desired = plan["desired"]
        # Add: desired labels not currently present.
        to_add = desired - current
        # Remove: managed labels currently present that are not desired.
        # (Only labels we own — never strip repo-native labels.)
        to_remove = (current & managed) - desired
        if not to_add and not to_remove:
            continue
        changes_proposed += 1
        src = ", ".join(sorted(set(plan["sources"])))
        print(f"{url}  [{src}]")
        if to_add:
            print(f"  + {sorted(to_add)}")
        if to_remove:
            print(f"  - {sorted(to_remove)}")
        if not args.apply:
            continue
        # PATCH issue with full target label set = (current - to_remove) | to_add.
        final_labels = sorted((current - to_remove) | to_add)
        status, payload = _api(
            "PATCH", f"/repos/{owner}/{repo}/issues/{number}",
            token, {"labels": final_labels},
        )
        if status >= 300:
            print(f"  ! PATCH failed (status={status}): {payload}", file=sys.stderr)
            errors += 1
        time.sleep(args.pace)

    print(
        f"\nProcessed {len(plans)} issue(s); proposed changes on "
        f"{changes_proposed}; errors: {errors}."
    )
    if errors:
        return 1
    if changes_proposed and not args.apply:
        return 2  # dry-run signal for CI
    return 0


if __name__ == "__main__":
    sys.exit(main())
