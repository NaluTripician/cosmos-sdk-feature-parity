"""
Validate data/features.yaml against the expected schema, including the
optional per-feature `assessment` block.

The `assessment` block is OPTIONAL. When present, it must have the shape:

    assessment:
      notes_for_reviewer: <string>            # optional
      public_api_symbols:                      # optional
        <sdk_id>: [<string>, ...]              # must be non-empty if present
      detection_hints:                         # optional
        <sdk_id>: [<string>, ...]              # must be non-empty if present
      changelog_keywords: [<string>, ...]      # optional, must be non-empty if present

where <sdk_id> is one of: dotnet, java, python, go, rust.

Empty lists are treated as validation errors (equivalent to a missing
field — if the author has nothing to say, they should omit the key).

Exits 0 on success, 1 on any validation error.

Usage:
    python scripts/validate_features_schema.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
FEATURES_PATH = REPO_ROOT / "data" / "features.yaml"

VALID_SDK_IDS = {"dotnet", "java", "python", "go", "rust"}
VALID_STATUSES = {
    "ga", "preview", "in_progress", "planned",
    "not_started", "removed", "n_a",
}

ASSESSMENT_OPTIONAL_KEYS = {
    "notes_for_reviewer",
    "public_api_symbols",
    "detection_hints",
    "changelog_keywords",
}


def _err(errors: list[str], feature_id: str, msg: str) -> None:
    errors.append(f"[{feature_id}] {msg}")


def _validate_sdk_keyed_list_of_strings(
    errors: list[str], feature_id: str, field: str, value: object,
) -> None:
    if not isinstance(value, dict):
        _err(errors, feature_id, f"assessment.{field} must be a mapping")
        return
    if not value:
        _err(errors, feature_id,
             f"assessment.{field} must not be empty; omit the key instead")
        return
    for sdk_id, items in value.items():
        if sdk_id not in VALID_SDK_IDS:
            _err(errors, feature_id,
                 f"assessment.{field} has unknown sdk '{sdk_id}'")
            continue
        if not isinstance(items, list) or not all(
            isinstance(x, str) for x in items
        ):
            _err(errors, feature_id,
                 f"assessment.{field}.{sdk_id} must be a list of strings")
            continue
        if len(items) == 0:
            _err(errors, feature_id,
                 f"assessment.{field}.{sdk_id} must not be an empty list; "
                 f"omit the key instead")


def validate_assessment(
    errors: list[str], feature_id: str, assessment: object,
) -> None:
    if not isinstance(assessment, dict):
        _err(errors, feature_id, "assessment must be a mapping")
        return

    unknown = set(assessment.keys()) - ASSESSMENT_OPTIONAL_KEYS
    if unknown:
        _err(errors, feature_id,
             f"assessment has unknown key(s): {sorted(unknown)}")

    if "notes_for_reviewer" in assessment and not isinstance(
        assessment["notes_for_reviewer"], str
    ):
        _err(errors, feature_id,
             "assessment.notes_for_reviewer must be a string")

    if "public_api_symbols" in assessment:
        _validate_sdk_keyed_list_of_strings(
            errors, feature_id, "public_api_symbols",
            assessment["public_api_symbols"],
        )

    if "detection_hints" in assessment:
        _validate_sdk_keyed_list_of_strings(
            errors, feature_id, "detection_hints",
            assessment["detection_hints"],
        )

    if "changelog_keywords" in assessment:
        kws = assessment["changelog_keywords"]
        if not isinstance(kws, list) or not all(isinstance(x, str) for x in kws):
            _err(errors, feature_id,
                 "assessment.changelog_keywords must be a list of strings")
        elif len(kws) == 0:
            _err(errors, feature_id,
                 "assessment.changelog_keywords must not be an empty list; "
                 "omit the key instead")


def validate_feature(errors: list[str], feature: object) -> None:
    if not isinstance(feature, dict):
        errors.append(f"feature entry is not a mapping: {feature!r}")
        return

    feature_id = feature.get("id", "<missing id>")
    if "id" not in feature or not isinstance(feature["id"], str):
        _err(errors, str(feature_id), "feature must have a string 'id'")
    if "name" not in feature or not isinstance(feature["name"], str):
        _err(errors, feature_id, "feature must have a string 'name'")

    sdks = feature.get("sdks")
    if not isinstance(sdks, dict):
        _err(errors, feature_id, "feature must have an 'sdks' mapping")
    else:
        for sdk_id, cell in sdks.items():
            if sdk_id not in VALID_SDK_IDS:
                _err(errors, feature_id, f"unknown sdk id '{sdk_id}'")
            if not isinstance(cell, dict):
                _err(errors, feature_id, f"sdks.{sdk_id} must be a mapping")
                continue
            status = cell.get("status")
            if status not in VALID_STATUSES:
                _err(errors, feature_id,
                     f"sdks.{sdk_id}.status '{status}' is not a valid status")

    if "assessment" in feature:
        validate_assessment(errors, feature_id, feature["assessment"])


def main() -> int:
    with open(FEATURES_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    errors: list[str] = []

    if not isinstance(data, dict) or "categories" not in data:
        errors.append("features.yaml must be a mapping with a top-level 'categories' list")
    else:
        cats = data["categories"]
        if not isinstance(cats, list):
            errors.append("'categories' must be a list")
        else:
            for cat in cats:
                if not isinstance(cat, dict):
                    errors.append(f"category entry is not a mapping: {cat!r}")
                    continue
                for feature in cat.get("features", []) or []:
                    validate_feature(errors, feature)

    if errors:
        print("features.yaml validation FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    total = sum(
        len(c.get("features", []) or [])
        for c in (data.get("categories") or [])
    )
    with_assessment = sum(
        1
        for c in (data.get("categories") or [])
        for f in (c.get("features", []) or [])
        if isinstance(f, dict) and "assessment" in f
    )
    print(
        f"features.yaml OK: {total} features, "
        f"{with_assessment} with assessment block."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
