"""Shared fixture builders for drug-indication golden tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.bilun.domain.claims.models import ClaimHeader, DrugClaimLine


def build_claim(
    *,
    claim_id: str,
    primary_icd10: str,
    department: str,
    scenario_tag: str,
    claim_type: str = "ayakta",
    facility_tier: str = "3",
) -> ClaimHeader:
    return ClaimHeader(
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        claim_type=claim_type,
        facility_tier=facility_tier,
        provider_type="kamu",
        department=department,
        admission_date=date(2026, 1, 1),
        discharge_date=date(2026, 1, 1),
        claim_start_date=date(2026, 1, 1),
        claim_end_date=date(2026, 1, 1),
        primary_icd10=primary_icd10,
        expected_total_billed_try=Decimal("0"),
        expected_total_payable_try=Decimal("0"),
        expected_denial_reason="",
        scenario_tag=scenario_tag,
    )


def build_drug_line(
    *,
    drug_claim_line_id: str,
    prescription_id: str,
    claim_id: str,
    drug_name: str,
    unit_price_try: Decimal,
    billed_amount_try: Decimal,
    expected_payable_try: Decimal,
    report_present: bool | None,
    report_duration_months: int | None = None,
    prescriber_specialty: str | None = None,
    inpatient_supply: bool | None = None,
    annual_application_count: int | None = None,
    is_loading_phase: bool | None = None,
    biomarkers: tuple[dict[str, str], ...] | None = None,
    prior_therapies: tuple[dict[str, str], ...] | None = None,
) -> DrugClaimLine:
    return DrugClaimLine(
        drug_claim_line_id=drug_claim_line_id,
        prescription_id=prescription_id,
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        drug_claim_date=date(2026, 1, 2),
        drug_name=drug_name,
        drug_code="",
        barkod="",
        equivalence_group="",
        quantity=1,
        unit_price_try=unit_price_try,
        billed_amount_try=billed_amount_try,
        expected_payable_try=expected_payable_try,
        discount_tier_expected=Decimal("0.28"),
        denial_reason_expected="",
        rule_trace_expected="",
        drug_specialty_board_report_present=report_present,
        drug_report_duration_months=report_duration_months,
        prescriber_specialty=prescriber_specialty,
        drug_inpatient_supply=inpatient_supply,
        annual_application_count=annual_application_count,
        is_loading_phase=is_loading_phase,
        biomarkers=biomarkers,
        prior_therapies=prior_therapies,
    )
