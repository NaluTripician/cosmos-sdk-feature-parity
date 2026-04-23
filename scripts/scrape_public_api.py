"""Scrape the public API surface of every Cosmos DB SDK.

Dispatches to per-SDK adapters under ``scripts/public_api_adapters/`` and
writes structured artifacts to ``data/scraped/``:

* ``<sdk>_public_api_latest.json`` — most recent snapshot (overwritten)
* ``<sdk>_public_api_<YYYY-MM-DD>.json`` — dated historical snapshot
* ``<sdk>_public_api_drift.md`` — written only when public_items change
  between runs (added/removed symbols)

The script is a **signal** for human reviewers — curated ``data/features.yaml``
is NEVER auto-mutated. This exists because CHANGELOGs miss features in every
SDK (per feedback from the Rust SDK team, generalized to all SDKs).

Usage::

    python scripts/scrape_public_api.py            # all SDKs
    python scripts/scrape_public_api.py --sdk go   # single SDK
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
DATA_DIR = REPO_ROOT / "data"
SCRAPED_DIR = DATA_DIR / "scraped"

# Import after path-relative constants so tests can monkeypatch if needed.
sys.path.insert(0, str(SCRIPT_DIR))
from public_api_adapters import ADAPTERS  # noqa: E402


def load_sdk_config() -> dict:
    with open(DATA_DIR / "sdks.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["sdks"]


def load_previous(sdk_id: str) -> dict | None:
    path = SCRAPED_DIR / f"{sdk_id}_public_api_latest.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return None


def _items_set(payload: dict) -> set[tuple[str, str]]:
    return {
        (i.get("kind", ""), i.get("path", ""))
        for i in payload.get("public_items", [])
    }


def write_drift_report(sdk_id: str, prev: dict, curr: dict) -> Path | None:
    prev_items = _items_set(prev)
    curr_items = _items_set(curr)
    added = sorted(curr_items - prev_items)
    removed = sorted(prev_items - curr_items)
    if not added and not removed:
        return None

    path = SCRAPED_DIR / f"{sdk_id}_public_api_drift.md"
    lines = [
        f"# {sdk_id} public-API drift",
        "",
        f"- previous scrape: `{prev.get('scraped_at', 'unknown')}` "
        f"(version `{prev.get('version')}`)",
        f"- current scrape:  `{curr.get('scraped_at', 'unknown')}` "
        f"(version `{curr.get('version')}`)",
        f"- source: {curr.get('source_url')}",
        "",
        "This report is a **signal only**. `data/features.yaml` must be",
        "updated manually after a human review of these changes.",
        "",
    ]
    if added:
        lines.append(f"## Added ({len(added)})")
        lines.append("")
        lines.extend(f"- `{kind}` `{p}`" for kind, p in added)
        lines.append("")
    if removed:
        lines.append(f"## Removed ({len(removed)})")
        lines.append("")
        lines.extend(f"- `{kind}` `{p}`" for kind, p in removed)
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def scrape_one(sdk_id: str, sdk_config: dict) -> dict:
    adapter = ADAPTERS.get(sdk_id)
    if adapter is None:
        return {
            "source_url": None,
            "version": sdk_config.get("latest_stable"),
            "public_items": [],
            "error": f"no adapter registered for sdk '{sdk_id}'",
        }
    try:
        return adapter(sdk_config)
    except Exception as exc:  # noqa: BLE001 - adapters should catch, but be defensive
        return {
            "source_url": None,
            "version": sdk_config.get("latest_stable"),
            "public_items": [],
            "error": f"adapter raised unexpectedly: {exc!r}",
        }


def run(sdk_ids: list[str]) -> int:
    SCRAPED_DIR.mkdir(parents=True, exist_ok=True)
    sdks = load_sdk_config()
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    iso_now = now.isoformat()

    failures = 0
    for sdk_id in sdk_ids:
        if sdk_id not in sdks:
            print(f"  {sdk_id}: unknown SDK, skipping", file=sys.stderr)
            failures += 1
            continue
        print(f"Scraping {sdk_id} public API...")
        payload = scrape_one(sdk_id, sdks[sdk_id])
        payload = {
            "scraped_at": iso_now,
            "sdk": sdk_id,
            "source_url": payload.get("source_url"),
            "version": payload.get("version"),
            "public_items": payload.get("public_items", []),
            **({"error": payload["error"]} if payload.get("error") else {}),
        }

        prev = load_previous(sdk_id)

        latest_path = SCRAPED_DIR / f"{sdk_id}_public_api_latest.json"
        dated_path = SCRAPED_DIR / f"{sdk_id}_public_api_{today}.json"
        for path in (latest_path, dated_path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, sort_keys=False)

        count = len(payload["public_items"])
        err = payload.get("error")
        status = f"{count} public items" if count else "NO ITEMS"
        if err:
            status += f" ({err})"
            failures += 1
        print(f"  {sdk_id}: {status} -> {latest_path.name}")

        if prev is not None and count:
            drift_path = write_drift_report(sdk_id, prev, payload)
            if drift_path is not None:
                print(f"  {sdk_id}: drift detected -> {drift_path.name}")

    return 0 if failures == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--sdk",
        action="append",
        help="SDK id to scrape (repeatable); defaults to all configured SDKs.",
    )
    args = parser.parse_args()

    all_ids = list(load_sdk_config().keys())
    ids = args.sdk or all_ids
    return run(ids)


if __name__ == "__main__":
    sys.exit(main())
