"""Scrape the com.azure.cosmos Java public API surface from Azure SDK javadocs."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ._common import dedupe_items, http_get

BASE_URL = "https://azuresdkdocs.z19.web.core.windows.net/java/azure-cosmos/latest"
ALLCLASSES_CANDIDATES = (
    f"{BASE_URL}/allclasses-index.html",
    f"{BASE_URL}/allclasses.html",
    f"{BASE_URL}/com/azure/cosmos/package-summary.html",
)
INDEX_URL = f"{BASE_URL}/index.html"


def _extract_version(soup: BeautifulSoup, sdk_config: dict) -> str | None:
    # Javadoc pages often carry a "azure-cosmos X.Y.Z" title or header.
    title = soup.title.get_text(strip=True) if soup.title else ""
    match = re.search(r"(\d+\.\d+\.\d+(?:[-.][\w.]+)?)", title)
    if match:
        return match.group(1)
    return sdk_config.get("latest_stable")


def scrape(sdk_config: dict) -> dict:
    last_err: str | None = None
    for url in ALLCLASSES_CANDIDATES:
        try:
            resp = http_get(url)
        except Exception as exc:  # noqa: BLE001
            last_err = f"{url}: {exc}"
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        items: list[dict] = []

        for link in soup.find_all("a", href=True):
            href = link["href"]
            # Class pages live at com/azure/cosmos/.../ClassName.html
            if "com/azure/cosmos" not in href or not href.endswith(".html"):
                continue
            if "package-summary" in href or "package-tree" in href:
                continue
            # Normalize: strip leading ../ and .html
            path_part = re.sub(r"^\.\./+", "", href).split("#", 1)[0]
            path_part = path_part[: -len(".html")]
            dotted = path_part.replace("/", ".")
            if not dotted.startswith("com.azure.cosmos"):
                continue
            name = dotted.rsplit(".", 1)[-1]
            # Heuristic kind: Javadoc marks interfaces with italics title attr; we
            # fall back to a generic "type" if unknown.
            title = (link.get("title") or "").lower()
            if "interface" in title:
                kind = "interface"
            elif "enum" in title:
                kind = "enum"
            elif "annotation" in title:
                kind = "annotation"
            elif "exception" in title or "error" in title or name.endswith("Exception"):
                kind = "exception"
            else:
                kind = "class"
            items.append({"kind": kind, "path": dotted})

        if items:
            version = _extract_version(soup, sdk_config)
            return {
                "source_url": url,
                "version": version,
                "public_items": dedupe_items(items),
            }
        last_err = f"{url}: no com.azure.cosmos links found"

    return {
        "source_url": ALLCLASSES_CANDIDATES[0],
        "version": sdk_config.get("latest_stable"),
        "public_items": [],
        "error": last_err or "unknown failure",
    }
