"""Only reviewed organ source gaps may retain neutral rules without encoded cites."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import polars as pl
import pytest
import yaml

from scripts.sut import compile_rules
from scripts.sut.prose.clause_identity import (
    NonEncodeEligibleCiteError,
    UnknownClauseCiteError,
    assert_gate_b_sources_resolvable,
    encoded_clause_ids_from_rules,
)
from scripts.sut.rule_sources import validate_rule_set_payload


FAMILY = "treatment_pricing_2_4"
REVIEW_RULE_IDS = (
    "2.4.2.A.(2).non_covered_donor_organ_tissue_no_pay",
    "2.4.2.A.(4).domestic_organ_transfer_per_2_6",
    "2.4.2.A.(5).cadaver_donor_procurement_p911146_ek2c",
)
ACTIVE_REF = "2.4.2.A.(1)#11111111"
MISSING_REF = "2.4.2.A.(4)#dd4afd03"
HEADING_REF = "2.4.2.A#22222222"


def corpus() -> pl.DataFrame:
    return pl.DataFrame({
        "clause_id": ["C000001", "C000002"],
        "clause_coordinate": ["2.4.2.A.(1)", "2.4.2.A"],
        "content_hash": ["11111111", "22222222"],
        "clause_type": ["fikra", "section_heading"],
        "is_in_force": [True, True],
        "clause_number": [1, None],
        "clause_letter": [None, None],
    })


def review_rule(rule_id: str = REVIEW_RULE_IDS[0]) -> dict:
    return {
        "rule_id": rule_id,
        "sut_section": "2.4.2.A",
        "source_review_required": True,
        "verification_status": "ai_generated_pending_review",
        "gate_b_sources": [],
        "condition": {"is_organ_or_tissue_donor": True},
        "action": {"billable": False},
    }


def payload(rule: dict, family: str = FAMILY) -> dict:
    return {
        "rule_set_id": family,
        "title": "Existing source gap requires review",
        "effective_date": "2026-10-04",
        "rules": [rule],
    }


def validate_boundary(rule: dict, boundary: str, family: str = FAMILY) -> None:
    if boundary == "payload":
        validate_rule_set_payload(payload(rule, family), family)
    else:
        assert_gate_b_sources_resolvable([rule], corpus(), rule_set_id=family)


@pytest.mark.parametrize("rule_id", REVIEW_RULE_IDS)
def test_three_supported_pending_rules_have_no_encoded_source(rule_id):
    rule = review_rule(rule_id)
    validate_rule_set_payload(payload(rule), FAMILY)
    assert_gate_b_sources_resolvable([rule], corpus(), rule_set_id=FAMILY)
    assert encoded_clause_ids_from_rules([rule], corpus()) == set()


@pytest.mark.parametrize("boundary", ["payload", "assert"])
@pytest.mark.parametrize("marker", [1, "true", None, []])
def test_review_marker_must_be_boolean_at_each_validation_boundary(boundary, marker):
    rule = review_rule()
    rule["source_review_required"] = marker
    with pytest.raises(ValueError):
        validate_boundary(rule, boundary)


@pytest.mark.parametrize("boundary", ["payload", "assert"])
@pytest.mark.parametrize("sources", [[ACTIVE_REF], [MISSING_REF], None, ()])
def test_review_rule_cannot_encode_even_a_valid_source(boundary, sources):
    rule = review_rule()
    rule["gate_b_sources"] = sources
    with pytest.raises(ValueError):
        validate_boundary(rule, boundary)


@pytest.mark.parametrize("boundary", ["payload", "assert"])
@pytest.mark.parametrize("status", [None, "verified", "AI_GENERATED_PENDING_REVIEW"])
def test_review_rule_requires_explicit_pending_verification(boundary, status):
    rule = review_rule()
    if status is None:
        del rule["verification_status"]
    else:
        rule["verification_status"] = status
    with pytest.raises(ValueError):
        validate_boundary(rule, boundary)


@pytest.mark.parametrize("boundary", ["payload", "assert"])
@pytest.mark.parametrize("rule_id,family", [
    ("2.4.2.A.(1).organ_tissue_transplant_recipient_donor_covered", FAMILY),
    ("new_unreviewed_rule", FAMILY),
    (REVIEW_RULE_IDS[0], "drug_indication_prose"),
    (REVIEW_RULE_IDS[0], "material_bundling_prose"),
    (REVIEW_RULE_IDS[0], ""),
])
def test_review_exception_is_limited_to_three_guarded_organ_rules(boundary, rule_id, family):
    with pytest.raises(ValueError):
        validate_boundary(review_rule(rule_id), boundary, family)


@pytest.mark.parametrize("marker", [False, "absent"])
@pytest.mark.parametrize("ref,error", [
    (MISSING_REF, UnknownClauseCiteError),
    (HEADING_REF, NonEncodeEligibleCiteError),
])
def test_ordinary_sources_still_require_current_encode_eligible_identity(marker, ref, error):
    rule = review_rule()
    if marker == "absent":
        del rule["source_review_required"]
    else:
        rule["source_review_required"] = marker
    rule["gate_b_sources"] = [ref]
    with pytest.raises(error):
        assert_gate_b_sources_resolvable([rule], corpus(), rule_set_id=FAMILY)


@pytest.mark.parametrize("marker", [False, "absent"])
def test_ordinary_treatment_rule_cannot_use_empty_encoded_source_list(marker):
    rule = review_rule()
    if marker == "absent":
        del rule["source_review_required"]
    else:
        rule["source_review_required"] = marker
    with pytest.raises(ValueError):
        validate_rule_set_payload(payload(rule), FAMILY)


@pytest.mark.parametrize("marker", [False, "absent"])
def test_ordinary_current_treatment_source_stays_encoded(marker):
    rule = review_rule()
    if marker == "absent":
        del rule["source_review_required"]
    else:
        rule["source_review_required"] = marker
    rule["gate_b_sources"] = [ACTIVE_REF]
    validate_rule_set_payload(payload(rule), FAMILY)
    assert_gate_b_sources_resolvable([rule], corpus(), rule_set_id=FAMILY)
    assert encoded_clause_ids_from_rules([rule], corpus()) == {"C000001"}


def test_review_marker_does_not_skip_context_source_validation():
    rule = review_rule()
    rule["source_context_refs"] = [MISSING_REF]
    with pytest.raises(UnknownClauseCiteError):
        assert_gate_b_sources_resolvable([rule], corpus(), rule_set_id=FAMILY)


def test_existing_context_only_source_contract_remains_supported():
    rule = {"rule_id": "structural", "source_context_refs": [HEADING_REF]}
    assert_gate_b_sources_resolvable([rule], corpus())
    assert encoded_clause_ids_from_rules([rule], corpus()) == set()


def test_fresh_compiler_drops_committed_cites_when_yaml_requires_neutral_review(tmp_path):
    rule = review_rule()
    committed = deepcopy(rule)
    committed.pop("source_review_required")
    committed["gate_b_sources"] = [MISSING_REF]
    rules_path = tmp_path / "treatment_pricing_2_4.json"
    rules_path.write_text(json.dumps(payload(committed)), encoding="utf-8")
    yaml_path = tmp_path / "2.4.2.A.yaml"
    yaml_path.write_text(yaml.safe_dump({"rules": [rule]}), encoding="utf-8")
    target = next(target for target in compile_rules.all_targets() if target.name == FAMILY)
    temporary_target = replace(
        target, rule_json=rules_path, yaml_sources=[yaml_path],
        manifest_path=None, golden_path=None,
    )
    compile_rules.compile_target(temporary_target)
    compiled = json.loads(rules_path.read_text(encoding="utf-8"))["rules"]
    assert compiled == [rule]
    assert encoded_clause_ids_from_rules(compiled, corpus()) == set()


def test_existing_union_merge_cannot_reattach_encoded_cites_to_review_rule():
    old = review_rule()
    old.pop("source_review_required")
    old["gate_b_sources"] = [MISSING_REF]
    merged, _, _ = compile_rules._dedup_union_overwrite([old], [review_rule()])
    assert merged[0]["source_review_required"] is True
    assert merged[0]["gate_b_sources"] == [MISSING_REF]
    with pytest.raises(ValueError):
        validate_rule_set_payload(payload(merged[0]), FAMILY)
    with pytest.raises(ValueError):
        assert_gate_b_sources_resolvable(merged, corpus(), rule_set_id=FAMILY)


def test_actual_compiled_documentary_rows_have_no_executable_locators():
    from src.bilun.domain.billing.broad_rule_catalog import load_broad_rule_catalog

    root = Path(__file__).resolve().parents[3]
    authored = json.loads((root / "data/gazette/prose_rules/treatment_pricing_2_4.json").read_text())
    rows = [row for row in authored["rules"] if row.get("source_review_required") is True]
    assert {row["rule_id"] for row in rows} == set(REVIEW_RULE_IDS)
    for row in rows:
        assert row["gate_b_sources"] == []
        assert row["verification_status"] == "ai_generated_pending_review"
        assert "Historical documentary source" in row["source_scope_note"]
    frame = pl.read_parquet(root / "data/gazette/sut_clauses.parquet")
    assert encoded_clause_ids_from_rules(rows, frame) == set()
    catalog = load_broad_rule_catalog()
    assert len(catalog) == 496
    assert all(row.source_locators == () for row in catalog if row.rule_id in REVIEW_RULE_IDS)
