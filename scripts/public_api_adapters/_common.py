"""Shared helpers for public-API adapters."""

from __future__ import annotations

import requests

DEFAULT_TIMEOUT = 30
USER_AGENT = (
    "cosmos-sdk-feature-parity-scraper/1.0 "
    "(+https://github.com/NaluTripician/cosmos-sdk-feature-parity)"
)


def http_get(url: str, *, timeout: int = DEFAULT_TIMEOUT, **kwargs) -> requests.Response:
    """GET with a consistent UA + timeout; raises on non-2xx."""
    headers = kwargs.pop("headers", {}) or {}
    headers.setdefault("User-Agent", USER_AGENT)
    resp = requests.get(url, headers=headers, timeout=timeout, **kwargs)
    resp.raise_for_status()
    return resp


def dedupe_items(items: list[dict]) -> list[dict]:
    """Deterministically dedupe a list of {kind, path} dicts."""
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for it in items:
        key = (it.get("kind", ""), it.get("path", ""))
        if key in seen or not key[1]:
            continue
        seen.add(key)
        out.append(it)
    out.sort(key=lambda i: (i.get("kind", ""), i.get("path", "")))
    return out
