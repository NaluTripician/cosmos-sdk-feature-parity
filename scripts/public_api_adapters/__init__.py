"""Per-SDK public-API adapters for scrape_public_api.py.

Each adapter exposes a ``scrape(sdk_config: dict) -> dict`` function that
returns a payload with the following shape::

    {
        "source_url": "https://...",
        "version": "x.y.z" | None,
        "public_items": [ {"kind": "class|method|...", "path": "..."} ],
        "error": "<message>"  # optional, present only on failure
    }

Adapters must never raise on network errors; they should catch and return
an ``error`` field so the orchestrator can still write a valid JSON stub.
"""

from . import dotnet, go, java, python, rust

ADAPTERS = {
    "dotnet": dotnet.scrape,
    "java": java.scrape,
    "python": python.scrape,
    "go": go.scrape,
    "rust": rust.scrape,
}

__all__ = ["ADAPTERS"]
