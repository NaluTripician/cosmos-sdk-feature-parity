"""
Generate a historical snapshot from features.yaml and scraped data.

Combines the curated feature parity matrix with automated scrape results
into a timestamped JSON snapshot for the dashboard's historical view.

Usage:
    python scripts/generate_snapshot.py
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
DATA_DIR = REPO_ROOT / "data"
HISTORY_DIR = DATA_DIR / "history"
SCRAPED_DIR = DATA_DIR / "scraped"


def load_features() -> dict:
    """Load the curated features.yaml."""
    with open(DATA_DIR / "features.yaml", "r") as f:
        return yaml.safe_load(f)


def load_sdks() -> dict:
    """Load SDK metadata from sdks.yaml."""
    with open(DATA_DIR / "sdks.yaml", "r") as f:
        return yaml.safe_load(f)["sdks"]


def load_latest_scrape() -> dict | None:
    """Load the latest scrape results if available."""
    latest_path = SCRAPED_DIR / "latest.json"
    if latest_path.exists():
        with open(latest_path, "r") as f:
            return json.load(f)
    return None


def build_assessment_keyword_index(features_data: dict) -> dict[str, list[str]]:
    """
    Build a map of feature_id -> [changelog_keyword, ...] from each feature's
    optional `assessment.changelog_keywords` block.

    Features without an `assessment` block are omitted, preserving the legacy
    regex-based keyword detection in scrape_changelogs.py.
    """
    index: dict[str, list[str]] = {}
    for category in features_data.get("categories", []) or []:
        for feature in category.get("features", []) or []:
            if not isinstance(feature, dict):
                continue
            assessment = feature.get("assessment") or {}
            keywords = assessment.get("changelog_keywords") or []
            if keywords and isinstance(keywords, list):
                index[feature["id"]] = [k for k in keywords if isinstance(k, str)]
    return index


def match_features_by_assessment(
    text: str, keyword_index: dict[str, list[str]],
) -> list[str]:
    """
    Return feature ids whose `assessment.changelog_keywords` appear in `text`
    (case-insensitive substring match). This is an additional, stronger signal
    on top of the legacy regex-based detection in scrape_changelogs.py.
    """
    lowered = text.lower()
    hits: list[str] = []
    for feature_id, keywords in keyword_index.items():
        for kw in keywords:
            if kw.lower() in lowered:
                hits.append(feature_id)
                break
    return hits


def compute_parity_stats(features_data: dict) -> dict:
    """Compute parity statistics from the feature matrix."""
    sdk_ids = ["dotnet", "java", "python", "go", "rust"]
    stats = {sdk: {"ga": 0, "preview": 0, "in_progress": 0, "not_started": 0, "n_a": 0, "total": 0} for sdk in sdk_ids}
    # Count cells with orthogonal availability nuance (opt-in gated or internal-only).
    opt_in_counts = {sdk: 0 for sdk in sdk_ids}
    internal_only_counts = {sdk: 0 for sdk in sdk_ids}

    total_features = 0
    for category in features_data.get("categories", []):
        for feature in category.get("features", []):
            total_features += 1
            for sdk_id in sdk_ids:
                sdk_status = feature.get("sdks", {}).get(sdk_id, {})
                status = sdk_status.get("status", "not_started")
                if status in ("ga", "preview", "in_progress", "planned", "not_started", "removed", "n_a"):
                    category_key = status if status in stats[sdk_id] else "not_started"
                    stats[sdk_id][category_key] = stats[sdk_id].get(category_key, 0) + 1
                stats[sdk_id]["total"] = total_features
                if sdk_status.get("requires_opt_in"):
                    opt_in_counts[sdk_id] += 1
                if sdk_status.get("public_api") is False:
                    internal_only_counts[sdk_id] += 1

    # Compute parity percentage (GA + preview vs total applicable)
    for sdk_id in sdk_ids:
        applicable = stats[sdk_id]["total"] - stats[sdk_id].get("n_a", 0)
        implemented = stats[sdk_id]["ga"] + stats[sdk_id]["preview"]
        stats[sdk_id]["parity_pct"] = round(
            (implemented / applicable * 100) if applicable > 0 else 0, 1
        )
        stats[sdk_id]["opt_in_gated"] = opt_in_counts[sdk_id]
        stats[sdk_id]["internal_only"] = internal_only_counts[sdk_id]

    return {"per_sdk": stats, "total_features": total_features}


def collect_nuanced_cells(features_data: dict) -> list:
    """Return cells that carry orthogonal availability fields (requires_opt_in / public_api)."""
    sdk_ids = ["dotnet", "java", "python", "go", "rust"]
    nuanced = []
    for category in features_data.get("categories", []):
        for feature in category.get("features", []):
            for sdk_id in sdk_ids:
                cell = feature.get("sdks", {}).get(sdk_id, {}) or {}
                if cell.get("requires_opt_in") or cell.get("public_api") is False:
                    entry = {
                        "feature_id": feature.get("id"),
                        "feature_name": feature.get("name"),
                        "sdk": sdk_id,
                        "status": cell.get("status"),
                    }
                    if cell.get("requires_opt_in"):
                        entry["requires_opt_in"] = cell["requires_opt_in"]
                    if cell.get("opt_in_name"):
                        entry["opt_in_name"] = cell["opt_in_name"]
                    if cell.get("public_api") is False:
                        entry["public_api"] = False
                    nuanced.append(entry)
    return nuanced


def generate_snapshot():
    """Generate and save a snapshot."""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    features = load_features()
    sdks = load_sdks()
    scrape = load_latest_scrape()
    parity_stats = compute_parity_stats(features)
    nuanced_cells = collect_nuanced_cells(features)
    assessment_keywords = build_assessment_keyword_index(features)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": timestamp,
        "parity_stats": parity_stats,
        "nuanced_cells": nuanced_cells,
        "sdk_versions": {
            sdk_id: {
                "latest_stable": sdk.get("latest_stable"),
                "latest_preview": sdk.get("latest_preview"),
            }
            for sdk_id, sdk in sdks.items()
        },
    }

    # Add scrape data if available
    if scrape:
        snapshot["scrape_data"] = {
            sdk_id: {
                "commits_last_7d": data.get("commits_last_7d"),
                "commits_last_30d": data.get("commits_last_30d"),
                "latest_commit_date": data.get("latest_commit_date"),
            }
            for sdk_id, data in scrape.get("sdks", {}).items()
            if "error" not in data
        }

        # Stronger signal: re-match each SDK's recent changelog texts against
        # per-feature `assessment.changelog_keywords`. Features without an
        # assessment block are simply absent from the index, preserving the
        # legacy regex detection already stored on the scrape under
        # `recent_features_detected`.
        if assessment_keywords:
            assessment_hits: dict[str, dict[str, list[str]]] = {}
            for sdk_id, data in scrape.get("sdks", {}).items():
                if "error" in data:
                    continue
                per_feature: dict[str, list[str]] = {}
                for feature_text_info in (
                    data.get("recent_features_detected") or {}
                ).values():
                    text = feature_text_info.get("text", "") if isinstance(
                        feature_text_info, dict
                    ) else ""
                    if not text:
                        continue
                    for feat_id in match_features_by_assessment(
                        text, assessment_keywords
                    ):
                        per_feature.setdefault(feat_id, []).append(text[:200])
                if per_feature:
                    assessment_hits[sdk_id] = per_feature
            if assessment_hits:
                snapshot["assessment_keyword_hits"] = assessment_hits

    # Save timestamped snapshot
    output_path = HISTORY_DIR / f"{timestamp}.json"
    with open(output_path, "w") as f:
        json.dump(snapshot, f, indent=2)
    print(f"Saved snapshot to {output_path}")

    # Save as latest for dashboard
    latest_path = HISTORY_DIR / "latest.json"
    with open(latest_path, "w") as f:
        json.dump(snapshot, f, indent=2)
    print(f"Saved latest snapshot to {latest_path}")

    # Print parity summary
    print("\n=== Feature Parity Summary ===")
    print(f"Total features tracked: {parity_stats['total_features']}")
    for sdk_id in ["dotnet", "java", "python", "go", "rust"]:
        s = parity_stats["per_sdk"][sdk_id]
        bar_len = int(s["parity_pct"] / 5)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        name = sdks[sdk_id]["name"].ljust(8)
        print(f"  {name} {bar} {s['parity_pct']:5.1f}%  (GA:{s['ga']} Preview:{s['preview']} Missing:{s['not_started']})")


if __name__ == "__main__":
    generate_snapshot()
