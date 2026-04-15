"""
Generate a historical snapshot from features.yaml and scraped data.

Combines the curated feature parity matrix with automated scrape results
into a timestamped JSON snapshot for the dashboard's historical view.

Usage:
    python scripts/generate_snapshot.py
"""

import json
import os
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


def compute_parity_stats(features_data: dict) -> dict:
    """Compute parity statistics from the feature matrix."""
    sdk_ids = ["dotnet", "java", "python", "go", "rust"]
    stats = {sdk: {"ga": 0, "preview": 0, "in_progress": 0, "not_started": 0, "n_a": 0, "total": 0} for sdk in sdk_ids}

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

    # Compute parity percentage (GA + preview vs total applicable)
    for sdk_id in sdk_ids:
        applicable = stats[sdk_id]["total"] - stats[sdk_id].get("n_a", 0)
        implemented = stats[sdk_id]["ga"] + stats[sdk_id]["preview"]
        stats[sdk_id]["parity_pct"] = round(
            (implemented / applicable * 100) if applicable > 0 else 0, 1
        )

    return {"per_sdk": stats, "total_features": total_features}


def generate_snapshot():
    """Generate and save a snapshot."""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    features = load_features()
    sdks = load_sdks()
    scrape = load_latest_scrape()
    parity_stats = compute_parity_stats(features)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": timestamp,
        "parity_stats": parity_stats,
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
