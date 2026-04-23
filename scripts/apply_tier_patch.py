"""Apply a tier-edit patch (exported from the site) to data/features.yaml.

The site's "Edit tiers" mode exports a JSON file shaped like:

    {
      "generated_at": "...",
      "changes": [
        {"feature_id": "change_feed_processor", "sdk_id": "rust", "tier": "post_ga"},
        {"feature_id": "binary_encoding",       "sdk_id": "java", "tier": null}
      ]
    }

A null/empty `tier` removes the key from that cell.

The script edits features.yaml line-by-line so existing formatting
(comments, indentation, flow-style spacing, quoting) is preserved
byte-for-byte outside the touched cells. It supports both flow-style
one-liners, e.g.:

    dotnet: { status: "ga", since: "3.0.0" }

and block-style cells, e.g.:

    rust:
      status: "not_started"
      notes: "…"

Usage:
    python scripts/apply_tier_patch.py tier-patch.json
    python scripts/apply_tier_patch.py tier-patch.json --dry-run

Exit codes:
  0  applied (or dry-run clean)
  1  bad patch / feature or sdk not found / invalid tier / parse failure
  2  nothing to do (all requested changes already match)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
FEATURES_PATH = REPO_ROOT / "data" / "features.yaml"

VALID_TIERS = {"ga_blocker", "post_ga", "nice_to_have"}
VALID_SDKS = {"dotnet", "java", "python", "go", "rust"}


def _validate_via_pyyaml(text: str) -> tuple[dict | None, str | None]:
    try:
        return yaml.safe_load(text) or {}, None
    except yaml.YAMLError as e:
        return None, f"YAML parse error: {e}"


def _find_cell_meta(doc: dict, feature_id: str, sdk_id: str) -> tuple[dict | None, str | None]:
    for cat in doc.get("categories") or []:
        for feat in cat.get("features") or []:
            if feat.get("id") == feature_id:
                sdks = feat.get("sdks") or {}
                if sdk_id not in sdks:
                    return None, f"feature '{feature_id}' has no '{sdk_id}' cell"
                return sdks[sdk_id] or {}, None
    return None, f"feature '{feature_id}' not found"


# --- Line-based targeting --------------------------------------------------

# Matches `  - id: binary_encoding` at any indent.
_FEAT_ID_RE = re.compile(r"^(\s+)- id:\s*([A-Za-z0-9_]+)\s*$")
# Matches the `    sdks:` line at ANY indent, capturing its indent.
_SDKS_KEY_RE = re.compile(r"^(\s+)sdks:\s*$")


def _find_sdks_block(lines: list[str], feature_id: str) -> tuple[int, int, int] | None:
    """Return (sdks_line_idx, sdks_indent, sdks_end_exclusive) for the feature, or None."""
    # First find the feature's `- id: <feature_id>` line.
    feat_idx = None
    feat_indent_len = None
    for i, line in enumerate(lines):
        m = _FEAT_ID_RE.match(line)
        if m and m.group(2) == feature_id:
            feat_idx = i
            feat_indent_len = len(m.group(1))
            break
    if feat_idx is None:
        return None
    # From feat_idx, the sdks: block lives inside this feature's block —
    # meaning lines that are indented MORE than feat_indent_len, until we hit
    # another feature or dedent.
    sdks_idx = None
    sdks_indent_len = None
    for j in range(feat_idx + 1, len(lines)):
        line = lines[j]
        if not line.strip():
            continue
        stripped_indent = len(line) - len(line.lstrip(" "))
        # Left the feature (new feature or category) — abort.
        if stripped_indent <= feat_indent_len and line.lstrip().startswith(("- ", "- id:")):
            break
        if stripped_indent <= feat_indent_len:
            # left the feature
            break
        m = _SDKS_KEY_RE.match(line)
        if m and stripped_indent > feat_indent_len:
            sdks_idx = j
            sdks_indent_len = len(m.group(1))
            break
    if sdks_idx is None:
        return None
    # Find the end of the sdks block: first line whose indent is <= sdks_indent_len.
    end = len(lines)
    for j in range(sdks_idx + 1, len(lines)):
        line = lines[j]
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent <= sdks_indent_len:
            end = j
            break
    return sdks_idx, sdks_indent_len, end


def _apply_to_sdk_cell(
    lines: list[str], sdk_key_idx: int, sdks_indent_len: int, new_tier: str | None,
) -> tuple[list[str], str]:
    """Apply the edit at the given SDK key line. Returns (new_lines, note)."""
    line = lines[sdk_key_idx]
    stripped = line.lstrip(" ")
    key_indent_len = len(line) - len(stripped)
    # Flow-style: `dotnet: { status: "ga", since: "3.0.0" }`
    flow_match = re.match(r'^(\s*)([A-Za-z0-9_]+):\s*\{(.*)\}\s*$', line)
    if flow_match:
        leading = flow_match.group(1)
        key = flow_match.group(2)
        body = flow_match.group(3).strip()
        entries = [e.strip() for e in body.split(",") if e.strip()] if body else []
        # Drop any existing tier entry.
        entries = [e for e in entries if not re.match(r'^tier\s*:', e)]
        if new_tier is not None:
            entries.append(f'tier: "{new_tier}"')
        if entries:
            new_body = " " + ", ".join(entries) + " "
        else:
            new_body = ""
        lines[sdk_key_idx] = f"{leading}{key}:" + " {" + new_body.strip(" ") + "}\n" if new_body == "" else f"{leading}{key}: {{{new_body}}}\n"
        return lines, "flow-style rewritten"
    # Block-style: the SDK key opens a multi-line block. Find its child range.
    child_indent_len = None
    child_start = sdk_key_idx + 1
    child_end = child_start
    tier_line_idx = None
    status_line_idx = None
    # Determine the block's end.
    # Children are lines indented > key_indent_len, up to next sibling / dedent.
    for j in range(sdk_key_idx + 1, len(lines)):
        line_j = lines[j]
        if not line_j.strip():
            continue
        indent_j = len(line_j) - len(line_j.lstrip(" "))
        if indent_j <= key_indent_len:
            child_end = j
            break
        if child_indent_len is None:
            child_indent_len = indent_j
        if indent_j == child_indent_len:
            if re.match(rf'^\s{{{child_indent_len}}}tier\s*:', line_j):
                tier_line_idx = j
            if re.match(rf'^\s{{{child_indent_len}}}status\s*:', line_j):
                status_line_idx = j
        child_end = j + 1
    if child_indent_len is None:
        # Empty block (shouldn't happen) — fall back to appending a child.
        child_indent_len = key_indent_len + 2
    indent_str = " " * child_indent_len
    if tier_line_idx is not None:
        if new_tier is None:
            # Remove the tier line entirely.
            del lines[tier_line_idx]
            return lines, "block-style tier removed"
        lines[tier_line_idx] = f'{indent_str}tier: "{new_tier}"\n'
        return lines, "block-style tier replaced"
    # No existing tier key.
    if new_tier is None:
        return lines, "noop (no tier present and none requested)"
    insert_at = (status_line_idx + 1) if status_line_idx is not None else (sdk_key_idx + 1)
    lines.insert(insert_at, f'{indent_str}tier: "{new_tier}"\n')
    return lines, "block-style tier inserted"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("patch", help="Path to JSON patch exported from the site.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print actions but don't write.")
    args = parser.parse_args()

    patch_path = Path(args.patch)
    if not patch_path.exists():
        print(f"ERROR: patch file not found: {patch_path}", file=sys.stderr)
        return 1
    try:
        patch = json.loads(patch_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON in patch: {e}", file=sys.stderr)
        return 1
    changes = patch.get("changes")
    if not isinstance(changes, list) or not changes:
        print("ERROR: patch has no 'changes' array", file=sys.stderr)
        return 1

    text = FEATURES_PATH.read_text(encoding="utf-8")
    doc, err = _validate_via_pyyaml(text)
    if err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 1
    lines = text.splitlines(keepends=True)

    applied: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    for idx, change in enumerate(changes):
        if not isinstance(change, dict):
            errors.append(f"changes[{idx}] is not an object")
            continue
        feat_id = change.get("feature_id")
        sdk_id = change.get("sdk_id")
        new_tier = change.get("tier")
        if not isinstance(feat_id, str) or not isinstance(sdk_id, str):
            errors.append(f"changes[{idx}]: feature_id/sdk_id must be strings")
            continue
        if sdk_id not in VALID_SDKS:
            errors.append(f"changes[{idx}]: unknown sdk '{sdk_id}'")
            continue
        if new_tier is not None and new_tier != "":
            if new_tier not in VALID_TIERS:
                errors.append(
                    f"changes[{idx}] ({feat_id}/{sdk_id}): invalid tier "
                    f"'{new_tier}' (expected {sorted(VALID_TIERS)} or null)"
                )
                continue
        else:
            new_tier = None

        cell, err = _find_cell_meta(doc, feat_id, sdk_id)
        if err:
            errors.append(f"changes[{idx}]: {err}")
            continue
        current = cell.get("tier") if isinstance(cell, dict) else None
        if current == new_tier:
            skipped.append(f"{feat_id}/{sdk_id}: already {current!r}")
            continue

        # Locate sdks block, then the sdk key line.
        found = _find_sdks_block(lines, feat_id)
        if not found:
            errors.append(f"{feat_id}/{sdk_id}: couldn't locate sdks block in YAML")
            continue
        sdks_idx, sdks_indent_len, sdks_end = found
        sdk_key_indent_len = sdks_indent_len + 2
        sdk_key_re = re.compile(rf'^\s{{{sdk_key_indent_len}}}{re.escape(sdk_id)}\s*:')
        sdk_key_idx = None
        for j in range(sdks_idx + 1, sdks_end):
            if sdk_key_re.match(lines[j]):
                sdk_key_idx = j
                break
        if sdk_key_idx is None:
            errors.append(f"{feat_id}/{sdk_id}: couldn't locate sdk key line in YAML")
            continue
        lines, note = _apply_to_sdk_cell(lines, sdk_key_idx, sdks_indent_len, new_tier)
        applied.append(f"{feat_id}/{sdk_id}: {current!r} -> {new_tier!r}  [{note}]")

    if errors:
        print("ERRORS:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    if not applied:
        print("Nothing to do:")
        for s in skipped:
            print(f"  . {s}")
        return 2

    print("Changes:")
    for a in applied:
        print(f"  + {a}")
    for s in skipped:
        print(f"  . {s}")

    if args.dry_run:
        print("\n(dry run — no files modified)")
        return 0

    new_text = "".join(lines)
    # Sanity check: re-parse to make sure we didn't corrupt the file.
    _, reparse_err = _validate_via_pyyaml(new_text)
    if reparse_err:
        print(
            f"\nABORTED: resulting YAML failed to parse ({reparse_err}). "
            f"No changes written.",
            file=sys.stderr,
        )
        return 1
    FEATURES_PATH.write_text(new_text, encoding="utf-8")
    print(f"\nWrote {FEATURES_PATH}. Run validator + build to verify:")
    print("  python scripts/validate_features_schema.py")
    print("  cd site && npm run build")
    return 0


if __name__ == "__main__":
    sys.exit(main())
