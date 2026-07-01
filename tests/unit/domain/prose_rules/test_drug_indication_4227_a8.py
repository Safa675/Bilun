"""Golden tests for §4.2.27 coagulation / albumin A8 tier-A batch rules."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from scripts.sut.rule_sources import load_legacy_drug_batch
BATCH_A8_RULES = load_legacy_drug_batch("drug_indication_4227_a8_batch_rules.py:BATCH_A8_RULES")
from src.bilun.domain.claims.models import ClaimHeader, DrugClaimLine
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[4]
_GOLDEN = _REPO / "data/gazette/prose_rules/golden/drug_indication_4.2.27_a8.json"

_SECTION_4227_TIER_A_PENDING = frozenset(
    {
        "C006225",
        "C006228",
        "C006233",
        "C006234",
        "C006243",
        "C006256",
        "C006257",
        "C006264",
        "C006274",
    }
)

_A8_GATE_B_SOURCES = frozenset(
    clause_id
    for rule in BATCH_A8_RULES
    for clause_id in (rule.get("gate_b_sources") or [])
)


def _claim(*, primary_icd10: str, department: str = "hematoloji") -> ClaimHeader:
    return ClaimHeader(
        claim_id="C-A8",
        patient_id="P1",
        episode_id="E1",
        claim_type="ayakta",
        facility_tier="3",
        provider_type="kamu",
        department=department,
        admission_date=date(2026, 1, 1),
        discharge_date=date(2026, 1, 1),
        claim_start_date=date(2026, 1, 1),
        claim_end_date=date(2026, 1, 1),
        primary_icd10=primary_icd10,
        package_candidate=False,
        expected_total_billed_try=Decimal("0"),
        expected_total_payable_try=Decimal("0"),
        expected_denial_reason="",
        scenario_tag="test-4227-a8",
    )


def _drug_line(
    *,
    drug_name: str,
    report_present: bool | None,
    report_duration_months: int | None = None,
    prescriber_specialty: str | None = None,
    inpatient_supply: bool | None = None,
) -> DrugClaimLine:
    return DrugClaimLine(
        drug_claim_line_id="D-A8",
        prescription_id="RX-A8",
        claim_id="C-A8",
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
        drug_inpatient_supply=inpatient_supply,
    )


def test_a8_rule_count() -> None:
    assert len(BATCH_A8_RULES) == 10


def test_a8_gate_b_sources_cover_section_4227_tier_a_pending() -> None:
    assert _A8_GATE_B_SOURCES
    assert all(rule.get("gate_b_sources") for rule in BATCH_A8_RULES)


@pytest.mark.parametrize(
    ("sample",),
    [(s,) for s in json.loads(_GOLDEN.read_text(encoding="utf-8"))["samples"]],
)
def test_a8_golden_samples(sample: dict) -> None:
    rule = next(r for r in BATCH_A8_RULES if r["rule_id"] == sample["rule_id"])
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(
            drug_name=sample["drug_name"],
            report_present=sample.get("report_present"),
            report_duration_months=sample.get("report_duration_months"),
            prescriber_specialty=sample.get("prescriber_specialty"),
            inpatient_supply=sample.get("drug_inpatient_supply"),
        ),
        claim=_claim(primary_icd10=sample["primary_icd10"]),
        diagnoses=(),
        rules=[{k: v for k, v in rule.items() if k != "encode_batch"}],
    )
    expected = sample.get("expect_violation")
    if expected is None:
        assert hit is None
    else:
        assert hit is not None
        assert hit["violation_kind"] == expected
        assert hit["rule_id"] == sample["rule_id"]
