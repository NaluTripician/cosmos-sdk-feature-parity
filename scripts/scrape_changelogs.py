"""
Scrape changelogs from all Cosmos DB SDK repositories via GitHub API.

Fetches CHANGELOG.md files, parses version entries, and extracts
recent features and changes. Outputs a JSON summary to data/scraped/.

Usage:
    python scripts/scrape_changelogs.py

Environment:
    GITHUB_TOKEN - GitHub personal access token (optional, increases rate limit)
"""

import json
import os
import re
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


def load_sdk_config() -> dict:
    """Load SDK configuration from sdks.yaml."""
    with open(DATA_DIR / "sdks.yaml", "r") as f:
        return yaml.safe_load(f)["sdks"]


def load_assessment_keywords() -> dict[str, list[str]]:
    """
    Build feature_id -> [changelog_keyword, ...] from features.yaml's optional
    per-feature `assessment.changelog_keywords` block.

    Returns an empty dict if features.yaml has no assessment blocks, which
    preserves the legacy FEATURE_PATTERNS-only behavior.
    """
    features_path = DATA_DIR / "features.yaml"
    if not features_path.exists():
        return {}
    with open(features_path, "r") as f:
        data = yaml.safe_load(f) or {}
    index: dict[str, list[str]] = {}
    for cat in data.get("categories", []) or []:
        for feat in cat.get("features", []) or []:
            if not isinstance(feat, dict):
                continue
            kws = (feat.get("assessment") or {}).get("changelog_keywords") or []
            if kws and isinstance(kws, list):
                fid = feat.get("id")
                if isinstance(fid, str):
                    index[fid] = [k for k in kws if isinstance(k, str)]
    return index


def github_headers() -> dict:
    """Build GitHub API headers with optional auth."""
    headers = {
        "Accept": "application/vnd.github.v3.raw",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def fetch_changelog(repo: str, path: str) -> str:
    """Fetch raw changelog content from GitHub."""
    url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
    resp = requests.get(url, headers=github_headers(), timeout=30)
    resp.raise_for_status()
    return resp.text


def fetch_commit_count(repo: str, path: str, since: str) -> int:
    """Count commits touching a path since a given date."""
    url = f"{GITHUB_API}/repos/{repo}/commits"
    headers = github_headers()
    headers["Accept"] = "application/vnd.github.v3+json"
    params = {"path": path, "since": since, "per_page": 100}
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    return len(resp.json())


def fetch_latest_commit_date(repo: str, path: str) -> str | None:
    """Get the date of the most recent commit touching a path."""
    url = f"{GITHUB_API}/repos/{repo}/commits"
    headers = github_headers()
    headers["Accept"] = "application/vnd.github.v3+json"
    params = {"path": path, "per_page": 1}
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    commits = resp.json()
    if commits:
        return commits[0]["commit"]["committer"]["date"]
    return None


def parse_versions(changelog_text: str) -> list[dict]:
    """
    Parse a changelog into structured version entries.
    
    Handles format variations across SDKs:
    - ## X.Y.Z (YYYY-MM-DD)
    - ### X.Y.Z (YYYY-MM-DD)
    - ### <a name="X.Y.Z"/> [X.Y.Z](...) - YYYY-M-D  (.NET style)
    """
    versions = []

    # Split into version sections
    # Match headers like: ## 4.79.0 (2026-03-27) or ### [3.58.0](...) - 2026-3-19
    version_pattern = re.compile(
        r'^#{2,3}\s+'
        r'(?:<a\s+name="[^"]*"\s*/>\s*)?'       # optional <a name="..."/>
        r'(?:\[)?'                                 # optional [
        r'(\d+\.\d+\.\d+(?:-[\w.]+)?)'            # version number (capture group 1)
        r'(?:\](?:\([^)]*\))?)?'                   # optional ](url)
        r'\s*[-–]?\s*'                             # optional separator
        r'(?:\()?(\d{4}-\d{1,2}-\d{1,2})?(?:\))?', # optional date (capture group 2)
        re.MULTILINE
    )

    matches = list(version_pattern.finditer(changelog_text))

    for i, match in enumerate(matches):
        version = match.group(1)
        date_str = match.group(2)

        # Extract the content between this match and the next
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(changelog_text)
        content = changelog_text[start:end].strip()

        # Extract features from "Features Added" or "Added" sections
        features = extract_features(content)

        versions.append({
            "version": version,
            "date": date_str,
            "is_preview": bool(re.search(r'(preview|beta|alpha|rc)', version, re.IGNORECASE)),
            "features": features,
            "raw_length": len(content),
        })

    return versions


def extract_features(content: str) -> list[str]:
    """Extract feature descriptions from a version's content block."""
    features = []

    # Find the "Features Added" or "Added" section
    section_pattern = re.compile(
        r'(?:#{3,4}\s*(?:Features?\s*Added|Added)\s*\n)(.*?)(?=#{3,4}|\Z)',
        re.DOTALL | re.IGNORECASE
    )

    for section_match in section_pattern.finditer(content):
        section_text = section_match.group(1)
        # Extract bullet points
        bullet_pattern = re.compile(r'^\s*[-*]\s+(.+?)(?=\n\s*[-*]|\n\n|\Z)', re.MULTILINE | re.DOTALL)
        for bullet in bullet_pattern.finditer(section_text):
            feature_text = bullet.group(1).strip()
            # Clean up: remove PR links and extra whitespace
            feature_text = re.sub(r'\s*[-–]\s*See\s+\[PR\s+\d+\].*$', '', feature_text)
            feature_text = re.sub(r'\s*See\s+\[PR\s+\d+\].*$', '', feature_text)
            feature_text = re.sub(r'\s+', ' ', feature_text).strip()
            if feature_text and len(feature_text) > 10:
                features.append(feature_text)

    return features


def detect_feature_keywords(
    text: str,
    assessment_keywords: dict[str, list[str]] | None = None,
) -> list[str]:
    """Detect known feature keywords in text. Returns matching feature IDs.

    Uses the legacy built-in FEATURE_PATTERNS plus, when provided, per-feature
    `assessment.changelog_keywords` from features.yaml as an additional
    (stronger, SDK-owner-curated) signal. Backward compatible: if
    `assessment_keywords` is None/empty, behavior is unchanged.
    """
    FEATURE_PATTERNS = {
        "cross_region_hedging": [r"hedg(?:ing|e)", r"availability.?strategy"],
        "ppaf": [r"per.?partition.?(?:automatic)?.?failover", r"PPAF"],
        "per_partition_circuit_breaker": [r"circuit.?breaker"],
        "vector_search_index": [r"vector.?(?:search|embedding|index)"],
        "full_text_search_index": [r"full.?text.?(?:search|index|policy)"],
        "hybrid_search": [r"hybrid.?search"],
        "semantic_reranking": [r"semantic.?rerank"],
        "patch_item": [r"patch.?item", r"PatchItem", r"PatchDocument"],
        "transactional_batch": [r"transactional.?batch", r"batch.?support"],
        "change_feed_processor": [r"change.?feed.?processor"],
        "change_feed_pull": [r"change.?feed(?!.*processor)"],
        "read_many": [r"read.?many", r"ReadManyItems", r"read_items"],
        "bulk_operations": [r"bulk.?(?:operation|executor|import|insert)"],
        "hierarchical_partition_keys": [r"hierarchical.?partition", r"HPK"],
        "throughput_control": [r"throughput.?control"],
        "throughput_buckets": [r"throughput.?bucket"],
        "priority_throttling": [r"priority.?(?:based)?.?throttl"],
        "opentelemetry": [r"open.?telemetry", r"OTel"],
        "thin_client": [r"thin.?client", r"gateway.?v2"],
        "fault_injection": [r"fault.?injection"],
        "query_advisor": [r"query.?advisor", r"QueryAdvice"],
        "n_region_sync_commit": [r"n.?region.?synchronous", r"N-Region"],
        "float16_vector": [r"float.?16", r"Float16"],
        "quantizer_type": [r"quantizer.?type"],
        "feed_ranges": [r"feed.?range"],
        "excluded_regions": [r"excluded.?(?:region|location)"],
    }

    matches = []
    for feature_id, patterns in FEATURE_PATTERNS.items():
        for p in patterns:
            if re.search(p, text, re.IGNORECASE):
                matches.append(feature_id)
                break

    # Additional signal: substring match against curated per-feature
    # assessment.changelog_keywords from features.yaml.
    if assessment_keywords:
        lowered = text.lower()
        for feature_id, keywords in assessment_keywords.items():
            if feature_id in matches:
                continue
            for kw in keywords:
                if kw and kw.lower() in lowered:
                    matches.append(feature_id)
                    break
    return matches


def scrape_all_sdks() -> dict:
    """Scrape changelogs and commit activity for all SDKs."""
    sdks_config = load_sdk_config()
    assessment_keywords = load_assessment_keywords()
    now = datetime.now(timezone.utc)
    thirty_days_ago = (now - __import__("datetime").timedelta(days=30)).isoformat()
    seven_days_ago = (now - __import__("datetime").timedelta(days=7)).isoformat()

    results = {}

    for sdk_id, sdk in sdks_config.items():
        print(f"Scraping {sdk['name']} SDK ({sdk['repo']})...")
        try:
            # Fetch and parse changelog
            changelog = fetch_changelog(sdk["repo"], sdk["changelog_path"])
            versions = parse_versions(changelog)

            # Get commit activity
            # Use the directory of the changelog as the path to check
            changelog_dir = str(Path(sdk["changelog_path"]).parent)
            if changelog_dir == ".":
                changelog_dir = ""

            commits_7d = fetch_commit_count(sdk["repo"], changelog_dir, seven_days_ago)
            commits_30d = fetch_commit_count(sdk["repo"], changelog_dir, thirty_days_ago)
            latest_commit = fetch_latest_commit_date(sdk["repo"], changelog_dir)

            # Detect features in recent versions (last 5)
            recent_features = {}
            for v in versions[:5]:
                for feature_text in v.get("features", []):
                    detected = detect_feature_keywords(
                        feature_text, assessment_keywords
                    )
                    for feat_id in detected:
                        if feat_id not in recent_features:
                            recent_features[feat_id] = {
                                "version": v["version"],
                                "date": v["date"],
                                "text": feature_text[:200],
                            }

            results[sdk_id] = {
                "name": sdk["name"],
                "repo": sdk["repo"],
                "latest_stable": next(
                    (v["version"] for v in versions if not v["is_preview"]),
                    sdk.get("latest_stable", "unknown"),
                ),
                "latest_preview": next(
                    (v["version"] for v in versions if v["is_preview"]),
                    sdk.get("latest_preview", "unknown"),
                ),
                "total_versions": len(versions),
                "commits_last_7d": commits_7d,
                "commits_last_30d": commits_30d,
                "latest_commit_date": latest_commit,
                "recent_features_detected": recent_features,
                "recent_versions": [
                    {"version": v["version"], "date": v["date"], "feature_count": len(v["features"])}
                    for v in versions[:10]
                ],
            }

        except Exception as e:
            print(f"  ERROR scraping {sdk['name']}: {e}", file=sys.stderr)
            results[sdk_id] = {"name": sdk["name"], "error": str(e)}

    return results


def main():
    """Main entry point."""
    SCRAPED_DIR.mkdir(parents=True, exist_ok=True)

    print("Starting changelog scrape...")
    results = scrape_all_sdks()

    # Save timestamped result
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    output = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "sdks": results,
    }

    output_path = SCRAPED_DIR / f"{timestamp}.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Saved scraped data to {output_path}")

    # Also save as latest.json for the dashboard
    latest_path = SCRAPED_DIR / "latest.json"
    with open(latest_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Saved latest data to {latest_path}")

    # Print summary
    print("\n=== Scrape Summary ===")
    for sdk_id, data in results.items():
        if "error" in data:
            print(f"  {data['name']}: ERROR - {data['error']}")
        else:
            print(
                f"  {data['name']}: v{data['latest_stable']} "
                f"({data['commits_last_30d']} commits/30d, "
                f"{len(data['recent_features_detected'])} features detected)"
            )


if __name__ == "__main__":
    main()
