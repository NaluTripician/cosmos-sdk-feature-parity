"""Scrape the Microsoft.Azure.Cosmos .NET public API surface.

Primary signal: the Microsoft Learn API browser JSON endpoint, which returns
a structured listing of every type in the ``Microsoft.Azure.Cosmos`` namespace.
Falls back to scraping the overview HTML page if the JSON endpoint fails.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from ._common import dedupe_items, http_get

NAMESPACE = "microsoft.azure.cosmos"
API_BROWSER_URL = (
    "https://learn.microsoft.com/api/apibrowser/dotnet/api/"
    f"{NAMESPACE}?api-version=0.2"
)
OVERVIEW_URL = f"https://learn.microsoft.com/en-us/dotnet/api/{NAMESPACE}"


def _scrape_api_browser(sdk_config: dict) -> dict:
    data = http_get(API_BROWSER_URL).json()
    items: list[dict] = []
    # API browser returns {"items": [{"name": "Container", "kind": "class", ...}, ...]}
    for entry in data.get("items", []) or []:
        name = entry.get("name")
        kind = (entry.get("kind") or entry.get("type") or "type").lower()
        if not name:
            continue
        items.append({"kind": kind, "path": f"Microsoft.Azure.Cosmos.{name}"})
    return {
        "source_url": API_BROWSER_URL,
        "version": sdk_config.get("latest_stable"),
        "public_items": dedupe_items(items),
    }


def _scrape_overview_html(sdk_config: dict) -> dict:
    resp = http_get(OVERVIEW_URL)
    soup = BeautifulSoup(resp.text, "html.parser")
    items: list[dict] = []

    # Each kind section ("Classes", "Structs", "Interfaces", "Enums", "Delegates")
    # is rendered as an <h2> followed by a <table> of links to member pages.
    KIND_MAP = {
        "classes": "class",
        "structs": "struct",
        "interfaces": "interface",
        "enums": "enum",
        "delegates": "delegate",
    }
    for header in soup.find_all(["h2", "h3"]):
        label = KIND_MAP.get(header.get_text(strip=True).lower())
        if not label:
            continue
        table = header.find_next("table")
        if not table:
            continue
        for row in table.select("tbody tr"):
            # Only the first cell is the type name; the second is its description
            # (which may also contain xref links we don't want).
            first_cell = row.find(["td", "th"])
            if not first_cell:
                continue
            link = first_cell.find("a", href=True)
            if not link:
                continue
            href = link["href"].lower()
            if NAMESPACE + "." not in href:
                continue
            name = link.get_text(strip=True)
            if not name or "(" in name or " " in name:
                continue
            items.append({"kind": label, "path": f"Microsoft.Azure.Cosmos.{name}"})

    return {
        "source_url": OVERVIEW_URL,
        "version": sdk_config.get("latest_stable"),
        "public_items": dedupe_items(items),
    }


def scrape(sdk_config: dict) -> dict:
    try:
        result = _scrape_api_browser(sdk_config)
        if result["public_items"]:
            return result
    except Exception as exc:  # noqa: BLE001
        api_err = f"api-browser failed: {exc}"
    else:
        api_err = "api-browser returned no items"

    try:
        return _scrape_overview_html(sdk_config)
    except Exception as exc:  # noqa: BLE001
        return {
            "source_url": OVERVIEW_URL,
            "version": sdk_config.get("latest_stable"),
            "public_items": [],
            "error": f"{api_err}; html fallback failed: {exc}",
        }
