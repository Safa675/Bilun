"""Route behaviour of the §4.2.13 / §4.2.16 drug indication A2 pilot rules.

The batch's rule, manifest and golden checks are the ``4213_4216`` row of
``test_drug_indication_clauses.py``. Other test modules import ``_claim`` and
``_drug_line``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ClaimHeader, DrugClaimLine
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line

pytestmark = pytest.mark.unit


def _claim(*, primary_icd10: str) -> ClaimHeader:
    return ClaimHeader(
        claim_id="C-A2",
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
        scenario_tag="test-4213-4216",
    )


def _drug_line(
    *,
    drug_name: str,
    report_present: bool | None,
    report_duration_months: int | None = None,
) -> DrugClaimLine:
    return DrugClaimLine(
        drug_claim_line_id="D-A2",
        prescription_id="RX-A2",
        claim_id="C-A2",
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
    )


def test_entekavir_without_route_discriminators_is_ambiguous() -> None:
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(drug_name="BARACLUDE 0.5 MG (ENTEKAVIR)", report_present=False),
        claim=_claim(primary_icd10="B18.1"),
        diagnoses=[],
    )
    assert hit is not None
    assert hit["violation_kind"] == "ambiguous_route"
    assert hit["rule_id"] is None
    assert hit["selected_rule_id"] is None


def test_entekavir_report_does_not_invent_a_route() -> None:
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(drug_name="BARACLUDE 0.5 MG (ENTEKAVIR)", report_present=True),
        claim=_claim(primary_icd10="B18.1"),
        diagnoses=[],
    )
    assert hit is not None
    assert hit["violation_kind"] == "ambiguous_route"
    assert hit["selected_rule_id"] is None


def test_entekavir_wrong_icd_is_indication_mismatch() -> None:
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(drug_name="BARACLUDE 0.5 MG (ENTEKAVIR)", report_present=True),
        claim=_claim(primary_icd10="J45.9"),
        diagnoses=[],
    )
    assert hit is not None
    assert hit["violation_kind"] == "indication_mismatch"


def test_glecaprevir_missing_board_report_is_error() -> None:
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(drug_name="MAVYRET (GLEKAPREVIR/PIBRENTASVIR)", report_present=False),
        claim=_claim(primary_icd10="B18.2"),
        diagnoses=[],
    )
    assert hit is not None
    assert hit["rule_id"] == "4.2.13.hcv_glecaprevir_pibrentasvir_board"
    assert hit["violation_kind"] == "missing_board_report"


def test_cystic_fibrosis_formula_with_report_passes() -> None:
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(drug_name="MODULEN KF (KISTIK FIBROZIS MAMASI)", report_present=True),
        claim=_claim(primary_icd10="E84.9"),
        diagnoses=[],
    )
    assert hit is None


def test_celiac_formula_missing_report_is_error() -> None:
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(drug_name="GLUTENSIZ UN KARISIMI (CELYAK)", report_present=False),
        claim=_claim(primary_icd10="K90.0"),
        diagnoses=[],
    )
    assert hit is not None
    assert hit["rule_id"] == "4.2.16.celiac_gluten_free_report"
    assert hit["violation_kind"] == "missing_board_report"
