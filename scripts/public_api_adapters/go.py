"""Scrape the azcosmos Go public API surface from pkg.go.dev."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ._common import dedupe_items, http_get

PKG_URL = "https://pkg.go.dev/github.com/Azure/azure-sdk-for-go/sdk/data/azcosmos"


def _extract_version(soup: BeautifulSoup, sdk_config: dict) -> str | None:
    # pkg.go.dev shows the version in a <span class="go-Main-headerVersion"> or
    # similar. Fall back to regex against the page text.
    header = soup.find(attrs={"data-test-id": "UnitHeader-version"})
    if header:
        text = header.get_text(" ", strip=True)
        m = re.search(r"v?(\d+\.\d+\.\d+(?:-[\w.]+)?)", text)
        if m:
            return m.group(1)
    return sdk_config.get("latest_stable")


def scrape(sdk_config: dict) -> dict:
    try:
        resp = http_get(PKG_URL)
    except Exception as exc:  # noqa: BLE001
        return {
            "source_url": PKG_URL,
            "version": sdk_config.get("latest_stable"),
            "public_items": [],
            "error": f"pkg.go.dev fetch failed: {exc}",
        }

    soup = BeautifulSoup(resp.text, "html.parser")
    items: list[dict] = []

    # pkg.go.dev renders the Index section as a <ul> of anchors whose hrefs are
    # fragments like "#Client" or "#NewClient". The surrounding <li> text
    # starts with the declaration keyword (type/func/const/var).
    for anchor in soup.select("a[href^='#']"):
        href = anchor["href"]
        name = href[1:]
        if not name or not re.match(r"^[A-Z][\w.]*$", name):
            # Only exported symbols, which in Go start uppercase.
            continue
        # Walk up to the enclosing list item / declaration line.
        parent = anchor.find_parent(["li", "div"])
        text = parent.get_text(" ", strip=True) if parent else anchor.get_text(strip=True)
        lowered = text.lower()
        if lowered.startswith("type "):
            kind = "type"
        elif lowered.startswith("func "):
            # Method receivers render as "func (c *Client) Foo(...)".
            kind = "method" if "(" in text.split("func ", 1)[1].split(" ", 1)[0] else "func"
        elif lowered.startswith("const "):
            kind = "const"
        elif lowered.startswith("var "):
            kind = "var"
        else:
            continue
        items.append({"kind": kind, "path": f"azcosmos.{name}"})

    # Also capture method/field names referenced in type doc sections via
    # <h4 class="Documentation-typeMethodHeader"> (pkg.go.dev markup).
    for h in soup.select("h4, h3"):
        cls = " ".join(h.get("class", []))
        header_text = h.get_text(" ", strip=True)
        if "typeMethodHeader" in cls or re.match(r"^func \(", header_text):
            m = re.search(r"\)\s*([A-Z]\w*)\s*\(", header_text)
            recv = re.search(r"\(\s*\*?(\w+)\s*\)", header_text)
            if m and recv:
                items.append(
                    {"kind": "method", "path": f"azcosmos.{recv.group(1)}.{m.group(1)}"}
                )

    version = _extract_version(soup, sdk_config)
    return {
        "source_url": PKG_URL,
        "version": version,
        "public_items": dedupe_items(items),
    }
