"""Golden tests for §4.2.35 / §4.2.37 neuropathic pain + acromegaly A5 pilot rules."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from scripts.sut.rule_sources import load_legacy_drug_batch
BATCH_A5_RULES = load_legacy_drug_batch("drug_indication_4235_4237_batch_rules.py:BATCH_A5_RULES")
from src.bilun.domain.claims.models import ClaimHeader, DrugClaimLine
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[4]
_GOLDEN = _REPO / "data/gazette/prose_rules/golden/drug_indication_4.2.35_4.2.37_a5.json"
_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4235_4237_manifest.json"


def _claim(*, primary_icd10: str) -> ClaimHeader:
    return ClaimHeader(
        claim_id="C-A5",
        patient_id="P1",
        episode_id="E1",
        claim_type="ayakta",
        facility_tier="3",
        provider_type="kamu",
        department="endokrinoloji",
        admission_date=date(2026, 1, 1),
        discharge_date=date(2026, 1, 1),
        claim_start_date=date(2026, 1, 1),
        claim_end_date=date(2026, 1, 1),
        primary_icd10=primary_icd10,
        package_candidate=False,
        expected_total_billed_try=Decimal("0"),
        expected_total_payable_try=Decimal("0"),
        expected_denial_reason="",
        scenario_tag="test-4235-4237",
    )


def _drug_line(
    *,
    drug_name: str,
    report_present: bool | None,
    report_duration_months: int | None = None,
    prescriber_specialty: str | None = None,
) -> DrugClaimLine:
    return DrugClaimLine(
        drug_claim_line_id="D-A5",
        prescription_id="RX-A5",
        claim_id="C-A5",
        patient_id="P1",
        episode_id="E1",
        drug_claim_date=date(2026, 1, 2),
        drug_name=drug_name,
        drug_code="",
        barkod="",
        equivalence_group="",
        quantity=1,
        unit_price_try=Decimal("800"),
        billed_amount_try=Decimal("800"),
        expected_payable_try=Decimal("576"),
        discount_tier_expected=Decimal("0.28"),
        denial_reason_expected="",
        rule_trace_expected="",
        drug_specialty_board_report_present=report_present,
        drug_report_duration_months=report_duration_months,
        prescriber_specialty=prescriber_specialty,
    )


def test_a5_batch_has_five_rules() -> None:
    assert len(BATCH_A5_RULES) == 5
    rule_ids = {str(rule["rule_id"]) for rule in BATCH_A5_RULES}
    assert "4.2.35.pregabalin_fibromyalgia_board_6mo" in rule_ids
    assert "4.2.37.pegvisomant_endocrine_prescriber" in rule_ids


def test_a5_manifest_traces_encoded_clauses() -> None:
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    encoded = set(manifest.get("encoded_clause_ids") or [])
    assert manifest["encoded_clause_count"] == len(encoded)
    assert encoded == set(manifest.get("gate_b_sources_encoded") or [])
    assert "C006717" in encoded
    assert manifest["section_id"] == "4.2.35,4.2.37"


@pytest.mark.parametrize(
    "sample",
    json.loads(_GOLDEN.read_text(encoding="utf-8"))["samples"]
    if _GOLDEN.is_file()
    else [],
    ids=lambda s: s.get("rule_id", "sample"),
)
def test_a5_golden_samples(sample: dict) -> None:
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(
            drug_name=sample["drug_name"],
            report_present=sample.get("report_present"),
            report_duration_months=sample.get("report_duration_months"),
            prescriber_specialty=sample.get("prescriber_specialty"),
        ),
        claim=_claim(primary_icd10=sample["primary_icd10"]),
        diagnoses=(),
        rules=BATCH_A5_RULES,
    )
    expected = sample.get("expect_violation")
    if expected is None:
        assert hit is None
    else:
        assert hit is not None
        assert hit["violation_kind"] == expected
        assert hit["rule_id"] == sample["rule_id"]
