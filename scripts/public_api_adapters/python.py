"""Scrape the azure.cosmos Python public API surface.

Primary signal: the PyPI JSON API for the ``azure-cosmos`` package, which
gives us the latest version reliably. For the actual symbol listing we parse
the Sphinx-generated ``genindex.html`` on the Azure SDK docs site.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ._common import dedupe_items, http_get

PYPI_URL = "https://pypi.org/pypi/azure-cosmos/json"
DOCS_BASE = "https://azuresdkdocs.z19.web.core.windows.net/python/azure-cosmos/latest"
GENINDEX_URL = f"{DOCS_BASE}/genindex.html"
MODULE_URL = f"{DOCS_BASE}/azure.cosmos.html"


def _latest_version(sdk_config: dict) -> str | None:
    try:
        data = http_get(PYPI_URL).json()
        return data.get("info", {}).get("version")
    except Exception:  # noqa: BLE001
        return sdk_config.get("latest_stable")


def _parse_symbol(text: str) -> tuple[str, str] | None:
    """Parse a Sphinx index entry like 'Container (class in azure.cosmos)'."""
    m = re.match(
        r"^(?P<name>[A-Za-z_][\w.]*)\s*\((?P<kind>[^)]+?)\s+in\s+(?P<mod>azure\.cosmos[\w.]*)\)",
        text.strip(),
    )
    if not m:
        return None
    kind = m.group("kind").strip().lower().split()[0]
    full = f"{m.group('mod')}.{m.group('name')}"
    return kind, full


def scrape(sdk_config: dict) -> dict:
    version = _latest_version(sdk_config)
    try:
        resp = http_get(GENINDEX_URL)
    except Exception as exc:  # noqa: BLE001
        return {
            "source_url": GENINDEX_URL,
            "version": version,
            "public_items": [],
            "error": f"genindex fetch failed: {exc}",
        }

    soup = BeautifulSoup(resp.text, "html.parser")
    items: list[dict] = []

    # Sphinx genindex renders entries as <li>Name (class in module)<ul>...</ul></li>.
    for li in soup.find_all("li"):
        # Take only the direct text of this li, not nested subentries, to avoid dupes.
        direct = "".join(
            c if isinstance(c, str) else c.get_text() for c in li.contents if getattr(c, "name", None) != "ul"
        )
        parsed = _parse_symbol(direct)
        if parsed:
            kind, path = parsed
            items.append({"kind": kind, "path": path})

    return {
        "source_url": GENINDEX_URL,
        "version": version,
        "public_items": dedupe_items(items),
    }
