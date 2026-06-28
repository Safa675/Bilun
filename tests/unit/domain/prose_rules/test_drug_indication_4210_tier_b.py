"""Golden tests for §4.2.10 LSD Tier B continuation/evaluation batch rules."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from scripts.sut.prose.drug_indication_4210_tier_b_batch_rules import BATCH_4210_TIER_B_RULES
from src.bilun.domain.claims.models import ClaimHeader, DrugClaimLine
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[4]
_GOLDEN = _REPO / "data/gazette/prose_rules/golden/drug_indication_4.2.10_tier_b.json"
_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4210_manifest.json"

_TIER_B_RULE_IDS = frozenset(str(r["rule_id"]) for r in BATCH_4210_TIER_B_RULES)
_TIER_B_GATE_B_SOURCES = frozenset(
    clause_id
    for rule in BATCH_4210_TIER_B_RULES
    for clause_id in (rule.get("gate_b_sources") or [])
)


def _tier_b_rule(rule_id: str) -> dict:
    clean_rules = [
        {k: v for k, v in rule.items() if k != "encode_batch"} for rule in BATCH_4210_TIER_B_RULES
    ]
    return next(r for r in clean_rules if r["rule_id"] == rule_id)


def _claim(*, primary_icd10: str) -> ClaimHeader:
    return ClaimHeader(
        claim_id="C-4210-TierB",
        patient_id="P1",
        episode_id="E1",
        claim_type="ayakta",
        facility_tier="3",
        provider_type="kamu",
        department="metabolizma",
        admission_date=date(2026, 1, 1),
        discharge_date=date(2026, 1, 1),
        claim_start_date=date(2026, 1, 1),
        claim_end_date=date(2026, 1, 1),
        primary_icd10=primary_icd10,
        package_candidate=False,
        expected_total_billed_try=Decimal("0"),
        expected_total_payable_try=Decimal("0"),
        expected_denial_reason="",
        scenario_tag="test-4210-tier-b",
    )


def _drug_line(
    *,
    drug_name: str,
    report_present: bool | None,
    report_duration_months: int | None = None,
    prescriber_specialty: str | None = None,
) -> DrugClaimLine:
    return DrugClaimLine(
        drug_claim_line_id="D-4210-TierB",
        prescription_id="RX-4210-TierB",
        claim_id="C-4210-TierB",
        patient_id="P1",
        episode_id="E1",
        drug_claim_date=date(2026, 1, 2),
        drug_name=drug_name,
        drug_code="",
        barkod="",
        equivalence_group="",
        quantity=1,
        unit_price_try=Decimal("10000"),
        billed_amount_try=Decimal("10000"),
        expected_payable_try=Decimal("7200"),
        discount_tier_expected=Decimal("0.28"),
        denial_reason_expected="",
        rule_trace_expected="",
        drug_specialty_board_report_present=report_present,
        drug_report_duration_months=report_duration_months,
        prescriber_specialty=prescriber_specialty,
    )


def test_tier_b_batch_rule_count() -> None:
    assert len(BATCH_4210_TIER_B_RULES) == 2


def test_tier_b_gate_b_sources_count() -> None:
    assert _TIER_B_GATE_B_SOURCES == {"C004235", "C004357"}


def test_tier_b_gate_b_sources_encoded_in_manifest() -> None:
    if not _MANIFEST.is_file():
        pytest.skip("manifest not exported yet — run merge_drug_indication_4210_tier_b.py")
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    encoded = frozenset(manifest.get("encoded_clause_ids") or [])
    assert _TIER_B_GATE_B_SOURCES <= encoded
    assert manifest.get("tier_b_pending_count") == 0


def test_tier_b_manifest_trace_completeness() -> None:
    if not _MANIFEST.is_file():
        pytest.skip("manifest not exported yet — run merge_drug_indication_4210_tier_b.py")
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    total = manifest["section_clause_total"]
    traced = (
        manifest["encoded_clause_count"]
        + manifest["tier_c_deferred_count"]
        + manifest["tier_a_pending_count"]
        + manifest["tier_b_pending_count"]
    )
    assert traced == total
    assert manifest["tier_c_deferred_count"] == 116
    for trace in manifest["clause_traces"]:
        if trace["manifest_status"] == "tier_c_deferred":
            assert trace.get("defer_reason")


@pytest.mark.parametrize(
    ("sample",),
    [(s,) for s in json.loads(_GOLDEN.read_text(encoding="utf-8"))["samples"]],
)
def test_tier_b_golden_samples(sample: dict) -> None:
    rule_id = sample["rule_id"]
    assert rule_id in _TIER_B_RULE_IDS
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
        assert hit["rule_id"] == rule_id, sample
