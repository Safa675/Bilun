"""Unit tests for Nivolumab melanoma (C43) and renal cell carcinoma (C64) expansions."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from src.bilun.domain.claims.models import ClaimHeader, DrugClaimLine
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[4]
_RULES_PATH = _REPO / "data/gazette/prose_rules/drug_indication_prose.json"

_NEW_RULE_IDS = {
    "nivolumab_melanoma_board",
    "nivolumab_renal_cell_carcinoma_board",
}


def _new_nivolumab_rules() -> list[dict]:
    """Load only the two new nivolumab expansion rules from the canonical JSON."""
    data = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    return [rule for rule in data["rules"] if rule["rule_id"] in _NEW_RULE_IDS]


def _claim(*, primary_icd10: str) -> ClaimHeader:
    return ClaimHeader(
        claim_id="C-NivoExp",
        patient_id="P1",
        episode_id="E1",
        claim_type="ayakta",
        facility_tier="3",
        provider_type="kamu",
        department="tıbbi onkoloji",
        admission_date=date(2026, 1, 1),
        discharge_date=date(2026, 1, 1),
        claim_start_date=date(2026, 1, 1),
        claim_end_date=date(2026, 1, 1),
        primary_icd10=primary_icd10,
        package_candidate=False,
        expected_total_billed_try=Decimal("0"),
        expected_total_payable_try=Decimal("0"),
        expected_denial_reason="",
        scenario_tag="test-nivolumab-expansion",
    )


def _drug_line(*, drug_name: str, report_present: bool | None) -> DrugClaimLine:
    return DrugClaimLine(
        drug_claim_line_id="D-NivoExp",
        prescription_id="RX-NivoExp",
        claim_id="C-NivoExp",
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
        drug_report_duration_months=None,
        prescriber_specialty=None,
    )


def test_new_rules_present_in_corpus() -> None:
    """Both new rules are encoded in the canonical drug indication corpus."""
    rules = _new_nivolumab_rules()
    found_ids = {rule["rule_id"] for rule in rules}
    assert found_ids == _NEW_RULE_IDS


def test_melanoma_c43_matches_melanoma_rule() -> None:
    """A C43 melanoma diagnosis with a missing board report hits the melanoma rule."""
    rules = _new_nivolumab_rules()
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(drug_name="nivolumab", report_present=False),
        claim=_claim(primary_icd10="C43.9"),
        diagnoses=(),
        rules=rules,
    )
    assert hit is not None
    assert hit["rule_id"] == "nivolumab_melanoma_board"
    assert hit["violation_kind"] == "missing_board_report"


def test_melanoma_c43_clean_when_report_present() -> None:
    """A C43 melanoma diagnosis with a present board report produces no violation."""
    rules = _new_nivolumab_rules()
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(drug_name="nivolumab", report_present=True),
        claim=_claim(primary_icd10="C43.51"),
        diagnoses=(),
        rules=rules,
    )
    assert hit is None


def test_renal_c64_matches_renal_rule() -> None:
    """A C64 renal cell carcinoma diagnosis with a missing board report hits the renal rule."""
    rules = _new_nivolumab_rules()
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(drug_name="nivolumab", report_present=False),
        claim=_claim(primary_icd10="C64.9"),
        diagnoses=(),
        rules=rules,
    )
    assert hit is not None
    assert hit["rule_id"] == "nivolumab_renal_cell_carcinoma_board"
    assert hit["violation_kind"] == "missing_board_report"


def test_c99_not_covered_returns_indication_mismatch() -> None:
    """C99 (malignant neoplasm of male genital organs, unspecified) is not covered by
    either new rule; the matcher falls back to the drug-name pool and flags the
    diagnosis as an indication_mismatch rather than a missing board report."""
    rules = _new_nivolumab_rules()
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(drug_name="nivolumab", report_present=False),
        claim=_claim(primary_icd10="C99"),
        diagnoses=(),
        rules=rules,
    )
    assert hit is not None
    assert hit["violation_kind"] == "indication_mismatch"
    assert hit["rule_id"] is None
    assert hit["selected_rule_id"] is None
    assert set(hit["eligible_route_rule_ids"]) == _NEW_RULE_IDS
