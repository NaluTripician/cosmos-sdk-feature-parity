"""
Scrape the azure_data_cosmos public API from docs.rs and Cargo features from
the azure-sdk-for-rust repo.

The Rust CHANGELOG frequently omits features — per feedback from Ashley
(Rust SDK lead), the public API surface on docs.rs is an additional signal we
use alongside the changelog to keep `data/features.yaml` accurate. This
scraper captures:

  * the set of public items (modules, structs, enums, traits, methods) as
    exposed on https://docs.rs/azure_data_cosmos/latest/azure_data_cosmos/
  * the Cargo `[features]` table from
    Azure/azure-sdk-for-rust/sdk/cosmos/azure_data_cosmos/Cargo.toml

Outputs (under data/scraped/):
  * rust_public_api_latest.json          — newest snapshot (overwritten)
  * rust_public_api_<YYYY-MM-DD>.json    — historical snapshot
  * rust_public_api_drift.md             — added/removed items + features
                                            (written only when drift detected;
                                            removed when clean)

The curated `data/features.yaml` is NEVER auto-mutated — drift is surfaced as
a signal for a human to re-audit.

Usage:
    python scripts/scrape_public_api_rust.py

Environment:
    GITHUB_TOKEN - optional; increases GitHub API rate limit for Cargo.toml fetch.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

from bs4 import BeautifulSoup

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
DATA_DIR = REPO_ROOT / "data"
SCRAPED_DIR = DATA_DIR / "scraped"

DOCS_RS_BASE = "https://docs.rs/azure_data_cosmos/latest/azure_data_cosmos/"
CARGO_TOML_URL = (
    "https://raw.githubusercontent.com/Azure/azure-sdk-for-rust/main/"
    "sdk/cosmos/azure_data_cosmos/Cargo.toml"
)

USER_AGENT = "cosmos-sdk-feature-parity-bot/1.0 (+github.com/NaluTripician)"
REQUEST_TIMEOUT = 30

# Rustdoc "all.html" item kind anchors map to these kinds. We keep the set
# narrow (the items that correlate with user-visible features).
ITEM_KIND_SECTIONS = {
    "modules": "module",
    "structs": "struct",
    "enums": "enum",
    "traits": "trait",
    "functions": "function",
    "macros": "macro",
    "types": "type",
    "constants": "constant",
}


# ---------------------------------------------------------------------------
# Network helpers
# ---------------------------------------------------------------------------

def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    return s


def fetch_text(url: str, session: requests.Session) -> str | None:
    """GET url, follow redirects, return text or None on any failure."""
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        print(f"  WARN fetch failed: {url} — {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# docs.rs parsing
# ---------------------------------------------------------------------------

def detect_version(landing_html: str, final_url: str | None = None) -> str | None:
    """Pick a version string out of the rustdoc landing page."""
    # rustdoc embeds the version in the sidebar header like:
    #   <h2 class="location"><a href="index.html">Crate azure_data_cosmos</a></h2>
    #   <div class="sidebar-elems">…<span class="version">0.28.0</span>…
    m = re.search(r'<span class="version">([^<]+)</span>', landing_html)
    if m:
        return m.group(1).strip()
    # Fallback: URL like https://docs.rs/azure_data_cosmos/0.28.0/...
    if final_url:
        m = re.search(r"/azure_data_cosmos/([^/]+)/", final_url)
        if m and m.group(1) != "latest":
            return m.group(1)
    return None


def parse_all_html(html: str) -> list[dict]:
    """Parse rustdoc's all.html; return list of {kind, path} entries."""
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict] = []

    # all.html groups items under <h3 id="structs">Structs</h3> (etc.) followed
    # by a <ul class="all-items"> of <a> elements whose text is the item path.
    for header in soup.find_all(["h3", "h2"]):
        section_id = (header.get("id") or "").lower()
        kind = ITEM_KIND_SECTIONS.get(section_id)
        if not kind:
            continue
        ul = header.find_next_sibling("ul")
        if not ul:
            continue
        for a in ul.find_all("a"):
            text = (a.get_text() or "").strip()
            if not text:
                continue
            # all.html lists paths relative to the crate root (e.g.
            # "constants::FOO" or just "CosmosClient"). Normalize to the
            # fully-qualified form the spec asks for.
            if not text.startswith("azure_data_cosmos"):
                text = f"azure_data_cosmos::{text}"
            items.append({"kind": kind, "path": text})

    return items


def parse_landing_items(html: str) -> list[dict]:
    """Fallback parser: pull items from the main crate landing page."""
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict] = []

    # Rustdoc sections on a module page: <h2 id="structs" class="small-section-header">
    for header in soup.find_all("h2"):
        section_id = (header.get("id") or "").lower()
        kind = ITEM_KIND_SECTIONS.get(section_id)
        if not kind:
            continue
        # Items follow in a <ul> or <dl> of <a class="struct">, etc.
        container = header.find_next(["ul", "dl", "table"])
        if not container:
            continue
        for a in container.find_all("a"):
            name = (a.get_text() or "").strip()
            if not name or not re.match(r"^[A-Za-z_][\w:]*$", name):
                continue
            path = f"azure_data_cosmos::{name}"
            items.append({"kind": kind, "path": path})

    return items


def fetch_struct_methods(
    item_path: str, session: requests.Session, base_url: str
) -> list[dict]:
    """
    For a given struct/enum/trait path like "azure_data_cosmos::CosmosClient",
    fetch its rustdoc page and extract method names.
    """
    # azure_data_cosmos::Foo::Bar -> struct.Bar.html under the parent module.
    parts = item_path.split("::")
    if len(parts) < 2:
        return []
    name = parts[-1]
    # Build URL relative to base (which ends with azure_data_cosmos/).
    # For items directly on the crate, the page lives at struct.<Name>.html.
    module_parts = parts[1:-1]
    module_prefix = "/".join(module_parts) + "/" if module_parts else ""
    methods: list[dict] = []
    for kind_prefix in ("struct", "enum", "trait"):
        url = urljoin(base_url, f"{module_prefix}{kind_prefix}.{name}.html")
        html = fetch_text(url, session)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        for section in soup.find_all("section", class_=re.compile(r"\bmethod\b")):
            mid = section.get("id") or ""
            m = re.match(r"method\.([A-Za-z_][\w]*)", mid)
            if m:
                methods.append(
                    {"kind": "method", "path": f"{item_path}::{m.group(1)}"}
                )
        # Also look for <a class="fn" href="#method.foo"> in the summary list
        for a in soup.select("a.fn[href^='#method.']"):
            href = a.get("href", "")
            m = re.match(r"#method\.([A-Za-z_][\w]*)", href)
            if m:
                methods.append(
                    {"kind": "method", "path": f"{item_path}::{m.group(1)}"}
                )
        if methods:
            break
    # Deduplicate preserving order.
    seen: set[str] = set()
    deduped: list[dict] = []
    for m in methods:
        if m["path"] in seen:
            continue
        seen.add(m["path"])
        deduped.append(m)
    return deduped


def scrape_docs_rs(session: requests.Session) -> tuple[list[dict], str | None, str]:
    """
    Return (public_items, version, resolved_base_url). On unreachable docs.rs
    returns ([], None, DOCS_RS_BASE).
    """
    print(f"Fetching {DOCS_RS_BASE} ...")
    try:
        landing_resp = session.get(
            DOCS_RS_BASE, timeout=REQUEST_TIMEOUT, allow_redirects=True
        )
        landing_resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  ERROR docs.rs unreachable: {e}", file=sys.stderr)
        return [], None, DOCS_RS_BASE

    final_url = landing_resp.url
    if not final_url.endswith("/"):
        final_url = final_url.rsplit("/", 1)[0] + "/"
    landing_html = landing_resp.text
    version = detect_version(landing_html, final_url)
    print(f"  resolved version: {version or 'unknown'} (base: {final_url})")

    # Prefer all.html for a complete item list.
    all_url = urljoin(final_url, "all.html")
    all_html = fetch_text(all_url, session)
    if all_html:
        items = parse_all_html(all_html)
        print(f"  parsed {len(items)} items from all.html")
    else:
        items = parse_landing_items(landing_html)
        print(f"  parsed {len(items)} items from landing page (fallback)")

    # Enrich with methods for top-level structs/enums/traits directly on the crate
    # (nested modules are skipped to keep the request count bounded).
    top_level_holders = [
        it for it in items if it["kind"] in {"struct", "enum", "trait"}
        and it["path"].count("::") == 1
    ]
    print(f"  fetching methods for {len(top_level_holders)} top-level item page(s)...")
    method_items: list[dict] = []
    for it in top_level_holders:
        methods = fetch_struct_methods(it["path"], session, final_url)
        method_items.extend(methods)

    items.extend(method_items)

    # Deduplicate on (kind, path).
    seen: set[tuple[str, str]] = set()
    unique: list[dict] = []
    for it in items:
        key = (it["kind"], it["path"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(it)

    unique.sort(key=lambda it: (it["kind"], it["path"]))
    return unique, version, final_url


# ---------------------------------------------------------------------------
# Cargo.toml parsing
# ---------------------------------------------------------------------------

def fetch_cargo_features(session: requests.Session) -> list[str]:
    """Fetch Cargo.toml and extract keys from the [features] table."""
    headers: dict[str, str] = {}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
    print(f"Fetching {CARGO_TOML_URL} ...")
    try:
        resp = session.get(
            CARGO_TOML_URL, headers=headers, timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        resp.raise_for_status()
        data = tomllib.loads(resp.text)
    except requests.RequestException as e:
        print(f"  ERROR Cargo.toml unreachable: {e}", file=sys.stderr)
        return []
    except tomllib.TOMLDecodeError as e:
        print(f"  ERROR Cargo.toml parse: {e}", file=sys.stderr)
        return []

    features = list((data.get("features") or {}).keys())
    features.sort()
    print(f"  found {len(features)} Cargo feature(s)")
    return features


# ---------------------------------------------------------------------------
# Drift detection + output
# ---------------------------------------------------------------------------

def load_previous(latest_path: Path) -> dict | None:
    if latest_path.exists():
        try:
            with open(latest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return None
    return None


def compute_drift(prev: dict | None, curr: dict) -> tuple[list[str], list[str], list[str], list[str]]:
    """Return (added_items, removed_items, added_features, removed_features)."""
    if not prev:
        return [], [], [], []
    prev_items = {f"{it['kind']} {it['path']}" for it in prev.get("public_items", [])}
    curr_items = {f"{it['kind']} {it['path']}" for it in curr.get("public_items", [])}
    prev_feat = set(prev.get("cargo_features", []))
    curr_feat = set(curr.get("cargo_features", []))
    return (
        sorted(curr_items - prev_items),
        sorted(prev_items - curr_items),
        sorted(curr_feat - prev_feat),
        sorted(prev_feat - curr_feat),
    )


def write_drift_report(
    path: Path,
    added_items: list[str],
    removed_items: list[str],
    added_feat: list[str],
    removed_feat: list[str],
    version: str | None,
) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [
        f"# Rust public-API drift detected — {today}",
        "",
        f"Source: `docs.rs/azure_data_cosmos` (version: `{version or 'unknown'}`) "
        f"and `sdk/cosmos/azure_data_cosmos/Cargo.toml`.",
        "",
        "The azure_data_cosmos public surface changed since the last scrape. "
        "Treat this as a signal to re-audit `data/features.yaml` — the Rust "
        "CHANGELOG is known to miss features, and public API additions are a "
        "strong hint that a new feature shipped.",
        "",
    ]
    if added_feat:
        lines.append("## Cargo features added")
        lines.extend(f"- `{f}`" for f in added_feat)
        lines.append("")
    if removed_feat:
        lines.append("## Cargo features removed")
        lines.extend(f"- `{f}`" for f in removed_feat)
        lines.append("")
    if added_items:
        lines.append(f"## Public items added ({len(added_items)})")
        lines.extend(f"- `{it}`" for it in added_items)
        lines.append("")
    if removed_items:
        lines.append(f"## Public items removed ({len(removed_items)})")
        lines.extend(f"- `{it}`" for it in removed_items)
        lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> int:
    SCRAPED_DIR.mkdir(parents=True, exist_ok=True)

    session = _session()
    public_items: list[dict] = []
    version: str | None = None
    resolved_base = DOCS_RS_BASE
    cargo_features: list[str] = []

    # Each sub-scrape is wrapped in try/except so one failure doesn't kill the
    # other. We always emit the JSON so drift detection has a well-formed
    # previous snapshot on the next run.
    try:
        public_items, version, resolved_base = scrape_docs_rs(session)
    except Exception as e:  # pragma: no cover — defensive
        print(f"ERROR docs.rs scrape failed: {e}", file=sys.stderr)

    try:
        cargo_features = fetch_cargo_features(session)
    except Exception as e:  # pragma: no cover — defensive
        print(f"ERROR Cargo features fetch failed: {e}", file=sys.stderr)

    output = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "source": "docs.rs/azure_data_cosmos",
        "source_url": resolved_base,
        "cargo_toml_url": CARGO_TOML_URL,
        "version": version,
        "cargo_features": cargo_features,
        "public_items": public_items,
    }

    latest_path = SCRAPED_DIR / "rust_public_api_latest.json"
    previous = load_previous(latest_path)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dated_path = SCRAPED_DIR / f"rust_public_api_{today}.json"
    drift_path = SCRAPED_DIR / "rust_public_api_drift.md"

    with open(dated_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved: {dated_path}")
    print(f"Saved: {latest_path}")

    # Only compute drift if the current scrape actually has content — a stub
    # snapshot (e.g. docs.rs unreachable) shouldn't masquerade as "everything
    # removed".
    if public_items and cargo_features:
        added_items, removed_items, added_feat, removed_feat = compute_drift(
            previous, output
        )
        if added_items or removed_items or added_feat or removed_feat:
            write_drift_report(
                drift_path, added_items, removed_items,
                added_feat, removed_feat, version,
            )
            print(f"Saved drift report: {drift_path}")
            print(
                f"  +{len(added_items)} / -{len(removed_items)} items, "
                f"+{len(added_feat)} / -{len(removed_feat)} features"
            )
        else:
            if drift_path.exists():
                drift_path.unlink()
            print("No drift detected.")
    else:
        print(
            "Stub snapshot written (docs.rs and/or Cargo.toml unreachable); "
            "skipping drift comparison.",
            file=sys.stderr,
        )

    print("\n=== Summary ===")
    print(f"  version:        {version or 'unknown'}")
    print(f"  public_items:   {len(public_items)}")
    print(f"  cargo_features: {len(cargo_features)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
