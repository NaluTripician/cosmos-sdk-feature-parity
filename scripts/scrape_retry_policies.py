"""
Backward-compatible wrapper around the generic scraper.

This used to be a standalone scraper; it is now a thin wrapper that invokes
`scrape_source_refs.py` with retry-policy-specific arguments. Prefer calling
`scrape_source_refs.py` directly in new workflows.
"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from scrape_source_refs import main as generic_main  # noqa: E402


if __name__ == "__main__":
    sys.argv = [
        sys.argv[0],
        "--data", "data/retries.yaml",
        "--output", "retry_policies",
        "--label", "retry-policy",
    ]
    sys.exit(generic_main())
