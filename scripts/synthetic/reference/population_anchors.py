"""Loader and schema/provenance validator for public-statistics population anchors.

Validates ``data/synthetic/reference/population_anchors.yaml`` against the
seven structural, provenance, and cross-reference rules required by the
synthetic v3 cohort calibration plan.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_POPULATION_ANCHORS_PATH = (
    REPO_ROOT / "data" / "synthetic" / "reference" / "population_anchors.yaml"
)

VALID_QUANTITIES = frozenset(f"Q{i}" for i in range(1, 9))
VALID_OBTAINED_VIA = frozenset({"read_table", "read_text", "search_summary_only"})
VALID_CONFIDENCE = frozenset({"high", "medium", "low"})
VALID_USE_FOR = frozenset(
    {
        "age_mix",
        "care_setting_mix",
        "department_share",
        "icu_rate",
        "los_range",
        "money_check",
        "pathway_selection",
        "sex_mix",
    }
)
VALID_ROLES = frozenset({"primary", "supporting", "superseded"})
REQUIRED_SOURCE_KEYS = ("publisher", "title", "url", "locator")

# Starts with lowercase letter; underscore-separated alphanumeric tokens
# (allows uppercase acronyms such as _ABC in siy24_group_definition_operations_ABC).
SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-zA-Z0-9]+)+$")
DERIVED_WORD_RE = re.compile(r"\bderived\b", re.IGNORECASE)


def load_population_anchors(path: Path | str | None = None) -> dict[str, Any]:
    """Load the population anchors YAML file via ``yaml.safe_load``."""
    target = Path(path) if path is not None else DEFAULT_POPULATION_ANCHORS_PATH
    with target.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Expected top-level mapping in {target}, got {type(data).__name__}")
    return data


def _is_non_empty_str(val: Any) -> bool:
    return isinstance(val, str) and bool(val.strip())


def _is_valid_int(val: Any) -> bool:
    return isinstance(val, int) and not isinstance(val, bool)


def _is_valid_year(val: Any) -> bool:
    if _is_valid_int(val):
        return True
    if _is_non_empty_str(val):
        return True
    if isinstance(val, list) and len(val) > 0 and all(_is_valid_int(item) for item in val):
        return True
    return False


def _is_valid_value(val: Any) -> bool:
    if val is None or isinstance(val, bool):
        return False
    if isinstance(val, str):
        return bool(val.strip())
    if isinstance(val, (list, dict)):
        return len(val) > 0
    return isinstance(val, (int, float))


def _is_valid_merged_from(val: Any) -> bool:
    if not isinstance(val, list) or len(val) == 0:
        return False
    for item in val:
        if not _is_non_empty_str(item) or ":" not in item:
            return False
        parts = item.split(":")
        if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
            return False
    return True


def validate_population_anchors(doc: dict[str, Any]) -> list[str]:
    """Validate a parsed population_anchors document and return error strings.

    Returns an empty list when all seven rules pass.
    """
    errors: list[str] = []

    if not isinstance(doc, dict):
        return ["Rule 1: Document must be a top-level mapping."]

    # Rule 1: top-level keys `meta` and `anchors`; `meta.inputs` row counts add up
    # to the number of `merged_from` entries.
    top_keys = set(doc.keys())
    if top_keys != {"meta", "anchors"}:
        errors.append(
            f"Rule 1: Top-level keys must be exactly {{'meta', 'anchors'}}, got {sorted(top_keys)}."
        )

    meta = doc.get("meta")
    anchors = doc.get("anchors")
    if not isinstance(meta, dict):
        errors.append("Rule 1: 'meta' must be a mapping.")
    if not isinstance(anchors, list) or len(anchors) == 0:
        errors.append("Rule 1: 'anchors' must be a non-empty list.")
        return errors

    inputs_list = meta.get("inputs") if isinstance(meta, dict) else None
    if not isinstance(inputs_list, list) or len(inputs_list) == 0:
        errors.append("Rule 1: 'meta.inputs' must be a non-empty list of {file, rows} mappings.")
    else:
        expected_total = 0
        inputs_valid = True
        for idx, item in enumerate(inputs_list):
            if (
                not isinstance(item, dict)
                or not _is_non_empty_str(item.get("file"))
                or not _is_valid_int(item.get("rows"))
            ):
                errors.append(
                    f"Rule 1: 'meta.inputs[{idx}]' must have non-empty 'file' and integer 'rows'."
                )
                inputs_valid = False
            else:
                expected_total += item["rows"]

        actual_merged_from_count = sum(
            len(row.get("merged_from", []))
            for row in anchors
            if isinstance(row, dict) and isinstance(row.get("merged_from"), list)
        )
        if inputs_valid and expected_total != actual_merged_from_count:
            errors.append(
                f"Rule 1: Sum of meta.inputs.rows ({expected_total}) does not equal "
                f"total merged_from entries ({actual_merged_from_count})."
            )

    # First pass to index anchor IDs and track duplicates
    id_counts: Counter[str] = Counter()
    anchors_by_id: dict[str, dict[str, Any]] = {}
    for row in anchors:
        if isinstance(row, dict) and _is_non_empty_str(row.get("id")):
            rid = row["id"]
            id_counts[rid] += 1
            if rid not in anchors_by_id:
                anchors_by_id[rid] = row

    for dup_id, count in id_counts.items():
        if count > 1:
            errors.append(f"Rule 2: Duplicate anchor id '{dup_id}' appears {count} times.")

    all_merged_from: list[str] = []

    for idx, row in enumerate(anchors):
        if not isinstance(row, dict):
            errors.append(f"Rule 2: Anchor at index {idx} is not a mapping.")
            continue

        rid = row.get("id")
        label = f"anchor '{rid}'" if _is_non_empty_str(rid) else f"anchor[{idx}]"

        # Rule 2: required fields and value domains
        if not _is_non_empty_str(rid) or not SNAKE_CASE_RE.match(rid):
            errors.append(f"Rule 2: {label} has invalid or non-snake_case id {rid!r}.")

        if row.get("quantity") not in VALID_QUANTITIES:
            errors.append(
                f"Rule 2: {label} has invalid quantity {row.get('quantity')!r} (expected Q1..Q8)."
            )

        if not _is_non_empty_str(row.get("description")):
            errors.append(f"Rule 2: {label} requires a non-empty string 'description'.")

        if not _is_valid_value(row.get("value")):
            errors.append(f"Rule 2: {label} requires a non-None, non-empty 'value'.")

        if not _is_non_empty_str(row.get("unit")):
            errors.append(f"Rule 2: {label} requires a non-empty string 'unit'.")

        if not _is_valid_year(row.get("year")):
            errors.append(
                f"Rule 2: {label} has invalid 'year' {row.get('year')!r} "
                "(expected int, non-empty list of ints, or non-empty str)."
            )

        if not _is_non_empty_str(row.get("scope")):
            errors.append(f"Rule 2: {label} requires a non-empty string 'scope'.")

        if not _is_non_empty_str(row.get("caveat")):
            errors.append(f"Rule 2: {label} requires a non-empty string 'caveat'.")

        src = row.get("source")
        if not isinstance(src, dict):
            errors.append(f"Rule 2: {label} requires a mapping 'source'.")
        else:
            for skey in REQUIRED_SOURCE_KEYS:
                if not _is_non_empty_str(src.get(skey)):
                    errors.append(f"Rule 2: {label} requires non-empty string 'source.{skey}'.")
            url_val = src.get("url")
            if _is_non_empty_str(url_val) and not url_val.startswith("https://"):
                errors.append(
                    f"Rule 2: {label} 'source.url' must start with 'https://', got {url_val!r}."
                )

        obtained_via = row.get("obtained_via")
        if obtained_via not in VALID_OBTAINED_VIA:
            errors.append(
                f"Rule 2: {label} has invalid 'obtained_via' {obtained_via!r}."
            )

        confidence = row.get("confidence")
        if confidence not in VALID_CONFIDENCE:
            errors.append(
                f"Rule 2: {label} has invalid 'confidence' {confidence!r}."
            )

        use_for = row.get("use_for")
        if use_for not in VALID_USE_FOR:
            errors.append(
                f"Rule 2: {label} has invalid 'use_for' {use_for!r}."
            )

        merged_from = row.get("merged_from")
        if not _is_valid_merged_from(merged_from):
            errors.append(
                f"Rule 2: {label} requires 'merged_from' to be a non-empty list of 'stem:id' strings."
            )
        else:
            all_merged_from.extend(merged_from)

        role = row.get("role")
        if role not in VALID_ROLES:
            errors.append(
                f"Rule 2: {label} has invalid 'role' {role!r} (expected primary, supporting, or superseded)."
            )

        # Rule 3: obtained_via `search_summary_only` requires confidence `low`.
        if obtained_via == "search_summary_only" and confidence != "low":
            errors.append(
                f"Rule 3: {label} has obtained_via='search_summary_only' "
                f"but confidence={confidence!r} (must be 'low')."
            )

        # Rule 4: description containing the word DERIVED (case-insensitive) requires `derived: true`.
        desc = row.get("description")
        if _is_non_empty_str(desc) and DERIVED_WORD_RE.search(desc):
            if row.get("derived") is not True:
                errors.append(
                    f"Rule 4: {label} description contains 'DERIVED' but lacks 'derived: true'."
                )

        # Rule 5: role `superseded` requires `superseded_by` naming an existing anchor
        # whose role is not superseded; role `supporting` requires `supports` naming an existing anchor.
        if role == "superseded":
            sup_by = row.get("superseded_by")
            if not _is_non_empty_str(sup_by) or sup_by not in anchors_by_id:
                errors.append(
                    f"Rule 5: {label} has role='superseded' but 'superseded_by' {sup_by!r} "
                    "does not name an existing anchor."
                )
            elif anchors_by_id[sup_by].get("role") == "superseded":
                errors.append(
                    f"Rule 5: {label} is superseded_by '{sup_by}', whose role is also 'superseded'."
                )
        elif role == "supporting":
            supports_id = row.get("supports")
            if not _is_non_empty_str(supports_id) or supports_id not in anchors_by_id:
                errors.append(
                    f"Rule 5: {label} has role='supporting' but 'supports' {supports_id!r} "
                    "does not name an existing anchor."
                )

        # Rule 6: `conflicts_with` ids exist and the relation is symmetric.
        if "conflicts_with" in row:
            c_list = row.get("conflicts_with")
            if not isinstance(c_list, list) or len(c_list) == 0:
                errors.append(
                    f"Rule 6: {label} 'conflicts_with' must be a non-empty list of anchor ids."
                )
            else:
                for other_id in c_list:
                    if not _is_non_empty_str(other_id) or other_id not in anchors_by_id:
                        errors.append(
                            f"Rule 6: {label} 'conflicts_with' references unknown anchor {other_id!r}."
                        )
                    else:
                        other_conflicts = anchors_by_id[other_id].get("conflicts_with")
                        if not isinstance(other_conflicts, list) or rid not in other_conflicts:
                            errors.append(
                                f"Rule 6: Asymmetric 'conflicts_with': {label} lists '{other_id}', "
                                f"but '{other_id}' does not list '{rid}'."
                            )

    # Rule 7: no `merged_from` entry appears twice in the file.
    merged_counts = Counter(all_merged_from)
    for entry, count in merged_counts.items():
        if count > 1:
            errors.append(
                f"Rule 7: merged_from entry '{entry}' appears {count} times across anchors."
            )

    return errors


__all__ = [
    "DEFAULT_POPULATION_ANCHORS_PATH",
    "load_population_anchors",
    "validate_population_anchors",
]
