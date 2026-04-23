"""Rust azure_data_cosmos public-API adapter.

Delegates the actual HTTP/HTML work to the richer scraper at
``scripts/scrape_public_api_rust.py`` (merged from ``ft/scrape-docs-rs``) so
the docs.rs parsing lives in exactly one place. This adapter keeps its
output shape compatible with the per-SDK contract used by
``scripts/scrape_public_api.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import requests

from ._common import USER_AGENT, dedupe_items

# scrape_public_api_rust.py is a sibling module in scripts/ — ensure scripts/
# is on sys.path so ``import scrape_public_api_rust`` resolves whether this
# adapter is loaded via the ``scripts/scrape_public_api.py`` entrypoint or as
# ``scripts.public_api_adapters.rust``.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import scrape_public_api_rust as _rust_scraper  # noqa: E402

DOCS_RS_URL = _rust_scraper.DOCS_RS_BASE
REQUEST_TIMEOUT = getattr(_rust_scraper, "REQUEST_TIMEOUT", 30)


def scrape(sdk_config: dict) -> dict:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    try:
        public_items, version, resolved_base = _rust_scraper.scrape_docs_rs(session)
    except Exception as exc:  # noqa: BLE001 - adapters must not raise
        return {
            "source_url": DOCS_RS_URL,
            "version": sdk_config.get("latest_stable"),
            "public_items": [],
            "error": f"docs.rs scrape raised unexpectedly: {exc!r}",
        }

    if not public_items:
        return {
            "source_url": resolved_base or DOCS_RS_URL,
            "version": version or sdk_config.get("latest_stable"),
            "public_items": [],
            "error": "docs.rs returned no public items (transient?)",
        }

    return {
        "source_url": resolved_base or DOCS_RS_URL,
        "version": version or sdk_config.get("latest_stable"),
        "public_items": dedupe_items(public_items),
    }
