"""Unit, mutation, and arithmetic tests for ``population_anchors.yaml``."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from scripts.synthetic.reference.population_anchors import (
    DEFAULT_POPULATION_ANCHORS_PATH,
    load_population_anchors,
    validate_population_anchors,
)

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def anchors_doc() -> dict[str, Any]:
    """Load the committed population anchors document once per module."""
    return load_population_anchors()


@pytest.fixture(scope="module")
def anchors_by_id(anchors_doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Index committed anchors by id."""
    return {row["id"]: row for row in anchors_doc["anchors"]}


def _collect_numbers(obj: Any) -> list[float]:
    """Recursively collect all int/float values inside a nested structure."""
    nums: list[float] = []
    if isinstance(obj, bool):
        return nums
    if isinstance(obj, (int, float)):
        nums.append(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            nums.extend(_collect_numbers(v))
    elif isinstance(obj, list):
        for item in obj:
            nums.extend(_collect_numbers(item))
    return nums


def test_committed_file_exists_and_validates(anchors_doc: dict[str, Any]) -> None:
    assert DEFAULT_POPULATION_ANCHORS_PATH.is_file()
    errors = validate_population_anchors(anchors_doc)
    assert errors == []


def test_rule1_mutation_top_level_keys_and_input_counts(anchors_doc: dict[str, Any]) -> None:
    # Missing top-level key / extra top-level key
    mut_keys = copy.deepcopy(anchors_doc)
    mut_keys["extra_key"] = True
    errors_keys = validate_population_anchors(mut_keys)
    assert any("Rule 1" in e and "Top-level keys" in e for e in errors_keys)

    # meta.inputs row count mismatch with merged_from entries
    mut_counts = copy.deepcopy(anchors_doc)
    mut_counts["meta"]["inputs"][0]["rows"] += 5
    errors_counts = validate_population_anchors(mut_counts)
    assert any("Rule 1" in e and "does not equal total merged_from entries" in e for e in errors_counts)


def test_rule2_mutation_required_fields_and_domains(anchors_doc: dict[str, Any]) -> None:
    # Duplicate id
    mut_dup = copy.deepcopy(anchors_doc)
    mut_dup["anchors"][1]["id"] = mut_dup["anchors"][0]["id"]
    assert any("Rule 2" in e and "Duplicate anchor id" in e for e in validate_population_anchors(mut_dup))

    # Non-snake_case id
    mut_id = copy.deepcopy(anchors_doc)
    mut_id["anchors"][0]["id"] = "Invalid-ID-Format"
    assert any("Rule 2" in e and "non-snake_case id" in e for e in validate_population_anchors(mut_id))

    # Invalid quantity
    mut_q = copy.deepcopy(anchors_doc)
    mut_q["anchors"][0]["quantity"] = "Q9"
    assert any("Rule 2" in e and "invalid quantity" in e for e in validate_population_anchors(mut_q))

    # Empty value
    mut_val = copy.deepcopy(anchors_doc)
    mut_val["anchors"][0]["value"] = {}
    assert any("Rule 2" in e and "'value'" in e for e in validate_population_anchors(mut_val))

    # Invalid year
    mut_year = copy.deepcopy(anchors_doc)
    mut_year["anchors"][0]["year"] = []
    assert any("Rule 2" in e and "invalid 'year'" in e for e in validate_population_anchors(mut_year))

    # Non-https source.url
    mut_url = copy.deepcopy(anchors_doc)
    mut_url["anchors"][0]["source"]["url"] = "http://example.com/insecure"
    assert any("Rule 2" in e and "https://" in e for e in validate_population_anchors(mut_url))

    # Invalid use_for
    mut_use = copy.deepcopy(anchors_doc)
    mut_use["anchors"][0]["use_for"] = "not_a_valid_use_for"
    assert any("Rule 2" in e and "invalid 'use_for'" in e for e in validate_population_anchors(mut_use))

    # Invalid role
    mut_role = copy.deepcopy(anchors_doc)
    mut_role["anchors"][0]["role"] = "secondary"
    assert any("Rule 2" in e and "invalid 'role'" in e for e in validate_population_anchors(mut_role))


@pytest.mark.parametrize(
    ("defect_name", "expected_field"),
    [
        ("empty_description", "description"),
        ("empty_unit", "unit"),
        ("empty_scope", "scope"),
        ("empty_caveat", "caveat"),
        ("empty_source_publisher", "source.publisher"),
        ("empty_source_title", "source.title"),
        ("empty_source_locator", "source.locator"),
        ("missing_source", "source"),
        ("invalid_obtained_via", "obtained_via"),
        ("invalid_confidence", "confidence"),
        ("empty_merged_from", "merged_from"),
        ("merged_from_no_colon", "merged_from"),
    ],
)
def test_rule2_mutation_additional_subchecks(
    anchors_doc: dict[str, Any],
    defect_name: str,
    expected_field: str,
) -> None:
    mut = copy.deepcopy(anchors_doc)
    first = mut["anchors"][0]
    if defect_name == "empty_description":
        first["description"] = ""
    elif defect_name == "empty_unit":
        first["unit"] = ""
    elif defect_name == "empty_scope":
        first["scope"] = ""
    elif defect_name == "empty_caveat":
        first["caveat"] = ""
    elif defect_name == "empty_source_publisher":
        first["source"]["publisher"] = ""
    elif defect_name == "empty_source_title":
        first["source"]["title"] = ""
    elif defect_name == "empty_source_locator":
        first["source"]["locator"] = ""
    elif defect_name == "missing_source":
        first.pop("source", None)
    elif defect_name == "invalid_obtained_via":
        first["obtained_via"] = "guessed"
    elif defect_name == "invalid_confidence":
        first["confidence"] = "certain"
    elif defect_name == "empty_merged_from":
        first["merged_from"] = []
    elif defect_name == "merged_from_no_colon":
        first["merged_from"] = ["anchors_moh_yearbook_without_colon"]

    errors = validate_population_anchors(mut)
    assert any("Rule 2" in e and expected_field in e for e in errors), (
        f"Expected Rule 2 error naming {expected_field!r} for {defect_name}, got: {errors}"
    )



def test_rule3_mutation_search_summary_only_requires_low_confidence(
    anchors_doc: dict[str, Any],
) -> None:
    mut = copy.deepcopy(anchors_doc)
    target = next(
        row for row in mut["anchors"] if row["obtained_via"] == "search_summary_only"
    )
    target["confidence"] = "medium"
    errors = validate_population_anchors(mut)
    assert any("Rule 3" in e and target["id"] in e for e in errors)


def test_rule4_mutation_derived_in_description_requires_derived_true(
    anchors_doc: dict[str, Any],
) -> None:
    mut = copy.deepcopy(anchors_doc)
    target = next(
        row for row in mut["anchors"] if "derived" in row["description"].lower()
    )
    target.pop("derived", None)
    errors = validate_population_anchors(mut)
    assert any("Rule 4" in e and target["id"] in e for e in errors)


def test_rule5_mutation_superseded_and_supporting_links(anchors_doc: dict[str, Any]) -> None:
    # superseded row pointing to another superseded row
    mut_sup = copy.deepcopy(anchors_doc)
    superseded_rows = [r for r in mut_sup["anchors"] if r["role"] == "superseded"]
    assert len(superseded_rows) >= 2
    superseded_rows[0]["superseded_by"] = superseded_rows[1]["id"]
    errors_sup = validate_population_anchors(mut_sup)
    assert any("Rule 5" in e and "role is also 'superseded'" in e for e in errors_sup)

    # supporting row pointing to non-existent anchor
    mut_support = copy.deepcopy(anchors_doc)
    supporting_row = next(r for r in mut_support["anchors"] if r["role"] == "supporting")
    supporting_row["supports"] = "non_existent_anchor_id"
    errors_support = validate_population_anchors(mut_support)
    assert any("Rule 5" in e and "does not name an existing anchor" in e for e in errors_support)


def test_rule6_mutation_conflicts_with_symmetry_and_existence(
    anchors_doc: dict[str, Any],
) -> None:
    # Asymmetric conflict
    mut_asym = copy.deepcopy(anchors_doc)
    row_with_conflict = next(r for r in mut_asym["anchors"] if r.get("conflicts_with"))
    partner_id = row_with_conflict["conflicts_with"][0]
    partner_row = next(r for r in mut_asym["anchors"] if r["id"] == partner_id)
    partner_row["conflicts_with"] = [
        cid for cid in partner_row["conflicts_with"] if cid != row_with_conflict["id"]
    ]
    if not partner_row["conflicts_with"]:
        partner_row.pop("conflicts_with", None)
    errors_asym = validate_population_anchors(mut_asym)
    assert any("Rule 6" in e and "Asymmetric 'conflicts_with'" in e for e in errors_asym)

    # Non-existent conflict target
    mut_missing = copy.deepcopy(anchors_doc)
    mut_missing["anchors"][0]["conflicts_with"] = ["ghost_anchor_id"]
    errors_missing = validate_population_anchors(mut_missing)
    assert any("Rule 6" in e and "unknown anchor" in e for e in errors_missing)


def test_rule7_mutation_duplicate_merged_from(anchors_doc: dict[str, Any]) -> None:
    mut = copy.deepcopy(anchors_doc)
    duplicate_entry = mut["anchors"][0]["merged_from"][0]
    mut["anchors"][1]["merged_from"].append(duplicate_entry)
    # Adjust meta.inputs[0]["rows"] by +1 so Rule 1 stays satisfied and Rule 7 is isolated
    mut["meta"]["inputs"][0]["rows"] += 1
    errors = validate_population_anchors(mut)
    assert any("Rule 7" in e and duplicate_entry in e for e in errors)


def test_arithmetic_private_hospital_alos_equals_bed_days_over_inpatients(
    anchors_by_id: dict[str, dict[str, Any]],
) -> None:
    tbl825 = anchors_by_id["siy24_tbl825_counts_by_sector_2024"]["value"]
    private_bed_days = tbl825["bed_days"]["private"]
    private_inpatients = tbl825["inpatients"]["private"]
    computed_private_alos = private_bed_days / private_inpatients

    derived_alos_2024 = anchors_by_id["siy24_alos_derived_by_sector_2002_2024"]["value"][
        "private"
    ][2024]
    assert abs(computed_private_alos - derived_alos_2024) <= 0.01

    published_alos_2024 = anchors_by_id["siy24_alos_published_by_sector_2024"]["value"]["private"]
    assert round(computed_private_alos, 1) == published_alos_2024

    # Also verify across all years in Tablo 8.3 and Tablo 8.10
    inpatients_series = anchors_by_id["siy24_inpatients_by_sector_2002_2024"]["value"]
    bed_days_series = anchors_by_id["siy24_bed_days_by_sector_2002_2024"]["value"]
    derived_series = anchors_by_id["siy24_alos_derived_by_sector_2002_2024"]["value"]["private"]
    for year, expected_alos in derived_series.items():
        ratio = bed_days_series[year]["private"] / inpatients_series[year]["private"]
        assert abs(ratio - expected_alos) <= 0.01


def test_arithmetic_tablo_825_sector_inpatients_sum_to_total(
    anchors_by_id: dict[str, dict[str, Any]],
) -> None:
    inpatients = anchors_by_id["siy24_tbl825_counts_by_sector_2024"]["value"]["inpatients"]
    sector_sum = inpatients["moh"] + inpatients["university"] + inpatients["private"]
    assert sector_sum == inpatients["total"]


def test_arithmetic_operation_groups_abc_sum_to_private_total(
    anchors_by_id: dict[str, dict[str, Any]],
) -> None:
    ops_private = anchors_by_id["siy24_tbl86_operations_by_group_and_sector_2024"]["value"][
        "private"
    ]
    abc_private_sum = ops_private["A"] + ops_private["B"] + ops_private["C"]
    assert abc_private_sum == ops_private["total"]


def test_arithmetic_private_icu_bed_types_sum_to_private_total(
    anchors_by_id: dict[str, dict[str, Any]],
) -> None:
    icu_private = anchors_by_id["siy24_tbl73_icu_beds_by_type_and_sector_2024"]["value"]["private"]
    private_icu_sum = icu_private["adult"] + icu_private["child"] + icu_private["newborn"]
    assert private_icu_sum == icu_private["total"]


def test_no_anchor_gives_turkiye_alos_of_4_7_days(
    anchors_doc: dict[str, Any],
    anchors_by_id: dict[str, dict[str, Any]],
) -> None:
    claim_row = anchors_by_id["alos_claim_check_tr_vs_mex_oecd_2023"]
    assert claim_row["value"]["mexico_all_inpatient_total_2023"] == pytest.approx(4.7)
    for key, val in claim_row["value"].items():
        if key.startswith("turkiye"):
            assert val == pytest.approx(4.2)
            assert val != pytest.approx(4.7)

    # Check that no Q1 anchor gives Türkiye (all hospitals / total) an average stay of 4.7 days
    national_keys = {
        "total",
        "total_all_sectors",
        "curative_care_total",
        "all_inpatient_care_total_function",
        "turkiye_curative_care_total_2023",
        "turkiye_all_inpatient_total_2023",
        "turkiye_curative_care_total_2024",
    }
    for row in anchors_doc["anchors"]:
        if row["quantity"] != "Q1":
            continue
        val = row["value"]
        if isinstance(val, (int, float)):
            assert float(val) != pytest.approx(4.7), (
                f"Q1 anchor {row['id']} gives scalar ALOS of 4.7."
            )
        elif isinstance(val, dict):
            for k, subval in val.items():
                if k in national_keys or str(k).startswith("turkiye"):
                    for num in _collect_numbers(subval):
                        assert num != pytest.approx(4.7), (
                            f"Q1 anchor {row['id']}[{k!r}] gives Türkiye ALOS of 4.7."
                        )


