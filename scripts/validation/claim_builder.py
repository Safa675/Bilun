"""Build Bilun claim objects from ILAY prescription rows.

Mirrors the pattern in tests/unit/domain/prose_rules/test_drug_indication_4201_a3.py
but constructs claims from real prescription data instead of hand-written fixtures.

The drug_indication engine reads only these fields:
  ClaimHeader: claim_id, primary_icd10
  DrugClaimLine: drug_claim_line_id, claim_id, drug_name, drug_specialty_board_report_present,
                 drug_report_duration_months, drug_inpatient_supply, prescriber_specialty,
                 annual_application_count, is_loading_phase, biomarkers, prior_therapies

All money/quantity/barkod fields are placeholders (zeros/empties) — the matcher ignores them.
The Tier-B clinical fields default to None, which triggers the realistic "needs_*_verification"
review path (the honest-skip pattern) rather than hard errors.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.bilun.domain.claims.models import ClaimHeader, DrugClaimLine


def build_claim(
    *,
    claim_id: str,
    patient_id: str,
    primary_icd10: str,
    department: str = "bilinmiyor",
    claim_type: str = "ayakta",
) -> ClaimHeader:
    """Build a minimal ClaimHeader the drug_indication engine can consume.

    Only ``claim_id`` and ``primary_icd10`` are read by the engine. All other
    fields are placeholders required by the dataclass.
    """
    return ClaimHeader(
        claim_id=claim_id,
        patient_id=patient_id,
        episode_id=f"E-{claim_id}",
        claim_type=claim_type,
        facility_tier="3",
        provider_type="ozel",
        department=department,
        admission_date=date(2020, 1, 1),
        discharge_date=date(2020, 1, 1),
        claim_start_date=date(2020, 1, 1),
        claim_end_date=date(2020, 1, 1),
        primary_icd10=primary_icd10,
        package_candidate=False,
        expected_total_billed_try=Decimal("0"),
        expected_total_payable_try=Decimal("0"),
        expected_denial_reason="",
        scenario_tag="ilay-validation",
    )


def build_drug_line(
    *,
    drug_claim_line_id: str,
    claim_id: str,
    patient_id: str,
    drug_name: str,
    drug_claim_date: date | None = None,
    prescriber_specialty: str | None = None,
) -> DrugClaimLine:
    """Build a minimal DrugClaimLine with all Tier-B clinical fields = None.

    The None defaults intentionally trigger the "needs_*_verification" review
    path — ILAY data does not carry board-report / biomarker / prior-therapy
    information, so we cannot assert those checks. This is the realistic
    state of a hospital claim before HIM review.

    ``prescriber_specialty`` is the only Tier-B field with a real value when
    provided — used by the specialty-scope validation harness (option B),
    which sets it from ILAY's SERVISADI column. Item 1 leaves it as None.
    """
    return DrugClaimLine(
        drug_claim_line_id=drug_claim_line_id,
        prescription_id=f"RX-{drug_claim_line_id}",
        claim_id=claim_id,
        patient_id=patient_id,
        episode_id=f"E-{claim_id}",
        drug_claim_date=drug_claim_date or date(2020, 1, 1),
        drug_name=drug_name,
        drug_code="",
        barkod="",
        equivalence_group="",
        quantity=1,
        unit_price_try=Decimal("0"),
        billed_amount_try=Decimal("0"),
        expected_payable_try=Decimal("0"),
        discount_tier_expected=Decimal("0"),
        denial_reason_expected="",
        rule_trace_expected="",
        prescriber_specialty=prescriber_specialty,
        # Other Tier-B fields default to None → realistic "unknown" state
    )
