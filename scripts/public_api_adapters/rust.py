"""Stub adapter for the Rust azure_data_cosmos SDK.

The full docs.rs scraper lives on the sibling branch ``ft/scrape-docs-rs``.
See also ``scripts/scrape_public_api_rust.py`` on that branch — once merged,
its output shape must match this adapter contract so downstream tooling
(drift diffs, artifact consumers) keeps working unchanged.

This stub intentionally performs no network I/O so the two branches don't
conflict on identical scraper code; the richer implementation should replace
this file wholesale on merge.
"""

from __future__ import annotations

DOCS_RS_URL = "https://docs.rs/azure_data_cosmos/latest/azure_data_cosmos/"


def scrape(sdk_config: dict) -> dict:
    return {
        "source_url": DOCS_RS_URL,
        "version": sdk_config.get("latest_stable"),
        "public_items": [],
        "error": (
            "rust adapter is a stub on this branch; see ft/scrape-docs-rs for "
            "the docs.rs implementation"
        ),
    }
