"""Golden tests for §4.2.13 hepatitis Tier B switch/renewal batch rules."""

from __future__ import annotations

from tests.unit._helpers.brittle_guards import soft_floor

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from scripts.sut.prose.manifest_index import encoded_like_clause_ids
from tests.unit._helpers.gate_b_cites import (
    cite_in_sources,
    cites_covered_by_encoded,
    resolve_gate_b_cites_to_clause_ids,
)
from scripts.sut.rule_sources import load_legacy_drug_batch
from src.bilun.domain.claims.models import ClaimHeader, DrugClaimLine
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line

BATCH_4213_TIER_B_RULES = load_legacy_drug_batch("BATCH_4213_TIER_B_RULES")
pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[4]
_GOLDEN = _REPO / "data/gazette/prose_rules/golden/drug_indication_4.2.13_tier_b.json"
_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4213_4216_manifest.json"

_TIER_B_RULE_IDS = frozenset(str(r["rule_id"]) for r in BATCH_4213_TIER_B_RULES)
_TIER_B_GATE_B_SOURCES = frozenset(
    clause_id
    for rule in BATCH_4213_TIER_B_RULES
    for clause_id in (rule.get("gate_b_sources") or [])
)

def _tier_b_rule(rule_id: str) -> dict:
    clean_rules = [
        {k: v for k, v in rule.items() if k != "encode_batch"} for rule in BATCH_4213_TIER_B_RULES
    ]
    return next(r for r in clean_rules if r["rule_id"] == rule_id)

def _claim(*, primary_icd10: str) -> ClaimHeader:
    return ClaimHeader(
        claim_id="C-TierB",
        patient_id="P1",
        episode_id="E1",
        claim_type="ayakta",
        facility_tier="3",
        provider_type="kamu",
        department="gastroenteroloji",
        admission_date=date(2026, 1, 1),
        discharge_date=date(2026, 1, 1),
        claim_start_date=date(2026, 1, 1),
        claim_end_date=date(2026, 1, 1),
        primary_icd10=primary_icd10,
        package_candidate=False,
        expected_total_billed_try=Decimal("0"),
        expected_total_payable_try=Decimal("0"),
        expected_denial_reason="",
        scenario_tag="test-4213-tier-b",
    )

def _drug_line(
    *,
    drug_name: str,
    report_present: bool | None,
    report_duration_months: int | None = None,
    prescriber_specialty: str | None = None,
) -> DrugClaimLine:
    return DrugClaimLine(
        drug_claim_line_id="D-TierB",
        prescription_id="RX-TierB",
        claim_id="C-TierB",
        patient_id="P1",
        episode_id="E1",
        drug_claim_date=date(2026, 1, 2),
        drug_name=drug_name,
        drug_code="",
        barkod="",
        equivalence_group="",
        quantity=1,
        unit_price_try=Decimal("1000"),
        billed_amount_try=Decimal("1000"),
        expected_payable_try=Decimal("720"),
        discount_tier_expected=Decimal("0.28"),
        denial_reason_expected="",
        rule_trace_expected="",
        drug_specialty_board_report_present=report_present,
        drug_report_duration_months=report_duration_months,
        prescriber_specialty=prescriber_specialty,
    )

def test_tier_b_batch_rule_count() -> None:
    soft_floor(len(BATCH_4213_TIER_B_RULES), 4, label='BATCH_4213_TIER_B_RULES')


def test_tier_b_gate_b_sources_count() -> None:
    assert _TIER_B_GATE_B_SOURCES
    assert all(rule.get("gate_b_sources") for rule in BATCH_4213_TIER_B_RULES)

def test_tier_b_oral_switch_in_force_sources() -> None:
    oral_switch = [
        r for r in BATCH_4213_TIER_B_RULES if str(r["rule_id"]) in {
            "4.2.13.hbv_oral_antiviral_switch_adult_report",
            "4.2.13.hbv_oral_antiviral_switch_pediatric_report",
        }
    ]
    sources = {
        clause_id
        for rule in oral_switch
        for clause_id in (rule.get("gate_b_sources") or [])
    }
    assert cite_in_sources("C004638", sources)
    assert cite_in_sources("C004647", sources)
    assert resolve_gate_b_cites_to_clause_ids(sources) >= frozenset({"C004638", "C004647"})

def test_tier_b_encoded_clause_ids_in_manifest() -> None:
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    covered = encoded_like_clause_ids(manifest)
    assert cites_covered_by_encoded(_TIER_B_GATE_B_SOURCES, covered)

@pytest.mark.parametrize(
    ("sample",),
    [(s,) for s in json.loads(_GOLDEN.read_text(encoding="utf-8"))["samples"]],
)
def test_tier_b_golden_samples(sample: dict) -> None:
    rule_id = sample["rule_id"]
    assert rule_id in _TIER_B_RULE_IDS
    gate_b_source = sample.get("gate_b_source")
    if gate_b_source:
        rule = _tier_b_rule(rule_id)
        assert cite_in_sources(gate_b_source, rule.get("gate_b_sources") or []), sample
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(
            drug_name=sample["drug_name"],
            report_present=sample.get("report_present"),
            report_duration_months=sample.get("report_duration_months"),
            prescriber_specialty=sample.get("prescriber_specialty"),
        ),
        claim=_claim(primary_icd10=sample["primary_icd10"]),
        diagnoses=(),
        rules=[_tier_b_rule(rule_id)],
    )
    expected = sample.get("expect_violation")
    if expected is None:
        assert hit is None, sample
    else:
        assert hit is not None, sample
        assert hit["violation_kind"] == expected, sample
        if expected in {"indication_mismatch", "ambiguous_route"}:
            assert hit["rule_id"] is None, sample
            assert rule_id in hit["eligible_route_rule_ids"], sample
        else:
            assert hit["rule_id"] == rule_id, sample
