"""Unit tests for anestezi puanı (anesthesia group billing) detector.

Covers the surgical-procedure-puan → anesthesia-group lookup defined in
SUT §2.4.4.A and EK-2B section "5. ANESTEZİ VE REANİMASYON".
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.billing.claim_anestezi_puani import (
    AnesteziPuaniReview,
    EXACTNESS_STATUS_EXACT,
    EXACTNESS_STATUS_MISSING_INPUTS,
    recommend_anestezi_puani_from_claims,
)
from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.anestezi_puani import (
    detect_anestezi_puani_opportunities,
)

pytestmark = pytest.mark.unit

# Verified against the EK-2B asof_2026-01-31 snapshot:
#   610130 (Appendektomi)               puan = 3397.78 → A1 group (550130, 8942.14)
#   530390 (Subkütan enjeksiyon)        puan =   22.46 → E  group (550190, 372.93)
#   620462 (Labioplasti)                puan = 5053.36 → beyond table (>5000), skip
_KATSAYI = 0.593


def _make_claim_header(
    *,
    claim_id: str = "C1",
    claim_type: str = "yatis",
    admission: date | None = date(2026, 7, 10),
    discharge: date | None = date(2026, 7, 13),
) -> ClaimHeader:
    return ClaimHeader(
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        claim_type=claim_type,
        facility_tier="devlet",
        provider_type="sozlesmeli",
        department="genel",
        admission_date=admission,
        discharge_date=discharge,
        claim_start_date=admission or date.today(),
        claim_end_date=discharge or date.today(),
        primary_icd10="K35.8",
        package_candidate=False,
        expected_total_billed_try=Decimal("1000"),
        expected_total_payable_try=Decimal("900"),
        expected_denial_reason="",
        scenario_tag="test",
    )


def _make_proc_line(
    *,
    procedure_line_id: str = "PL1",
    claim_id: str = "C1",
    procedure_code: str = "610130",
    procedure_category: str = "islem",
) -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id=procedure_line_id,
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        procedure_date=date(2026, 7, 10),
        procedure_code=procedure_code,
        procedure_name="test procedure",
        procedure_category=procedure_category,
        quantity=1,
        unit_price_try=Decimal("1000"),
        billed_amount_try=Decimal("1000"),
        expected_payable_try=Decimal("1000"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )


# ── Group resolution cases ───────────────────────────────────────────────────


def test_a1_group_appendektomi() -> None:
    """Appendektomi (610130, puan 3397.78) → A1 group (550130, 8942.14)."""
    claim = _make_claim_header()
    line = _make_proc_line(procedure_code="610130")
    opps = detect_anestezi_puani_opportunities(
        [claim], [line], claim_ids_with_procs={"C1"}
    )

    assert len(opps) == 1
    opp = opps[0]
    assert opp["anestezi_group"] == "A1"
    assert opp["anestezi_code"] == "550130"
    assert opp["anestezi_puan"] == pytest.approx(8942.14)
    assert opp["procedure_puan"] == pytest.approx(3397.78, abs=0.01)
    # 8942.14 × 0.593 = 5302.69
    assert opp["expected_try"] == pytest.approx(8942.14 * _KATSAYI, abs=0.01)
    assert opp["rule_id"] == "anestezi_puani_group_lookup"
    assert opp["included_in_sgk_total"] is True
    assert opp["sut_section_id"] == "2.4.4.A"


def test_e_group_low_puan_procedure() -> None:
    """Subkütan enjeksiyon (530390, puan 22.46) → E group (550190, 372.93)."""
    claim = _make_claim_header()
    line = _make_proc_line(
        procedure_line_id="PL2", procedure_code="530390"
    )
    opps = detect_anestezi_puani_opportunities(
        [claim], [line], claim_ids_with_procs={"C1"}
    )

    assert len(opps) == 1
    opp = opps[0]
    assert opp["anestezi_group"] == "E"
    assert opp["anestezi_code"] == "550190"
    assert opp["anestezi_puan"] == pytest.approx(372.93)
    assert opp["procedure_puan"] == pytest.approx(22.46, abs=0.01)
    # 372.93 × 0.593 = 221.17
    assert opp["expected_try"] == pytest.approx(372.93 * _KATSAYI, abs=0.01)


# ── Skip cases ───────────────────────────────────────────────────────────────


def test_outpatient_skipped() -> None:
    """Outpatient claim → no anesthesia opportunity (anesthesia is inpatient-only)."""
    claim = _make_claim_header(claim_type="ayakta")
    line = _make_proc_line(procedure_code="610130")
    opps = detect_anestezi_puani_opportunities(
        [claim], [line], claim_ids_with_procs={"C1"}
    )
    assert opps == []


def test_puan_beyond_table_skipped() -> None:
    """Procedure with puan > 5000 → skip (beyond standard group table)."""
    claim = _make_claim_header()
    # 620462 (Labioplasti) puan = 5053.36 → above 5000 table ceiling
    line = _make_proc_line(
        procedure_line_id="PL3", procedure_code="620462"
    )
    opps = detect_anestezi_puani_opportunities(
        [claim], [line], claim_ids_with_procs={"C1"}
    )
    assert opps == []


def test_package_procedure_skipped() -> None:
    """Paket-category procedure line → bundled, no separate anesthesia opportunity."""
    claim = _make_claim_header()
    line = _make_proc_line(
        procedure_line_id="PL4", procedure_code="610130", procedure_category="paket"
    )
    opps = detect_anestezi_puani_opportunities(
        [claim], [line], claim_ids_with_procs={"C1"}
    )
    assert opps == []


def test_claim_without_procs_filtered() -> None:
    """Claim not in claim_ids_with_procs → skipped."""
    claim = _make_claim_header()
    line = _make_proc_line(procedure_code="610130")
    opps = detect_anestezi_puani_opportunities(
        [claim], [line], claim_ids_with_procs={"OTHER"}
    )
    assert opps == []


def test_unknown_procedure_skipped() -> None:
    """Procedure code not in catalog (no puan) → skip."""
    claim = _make_claim_header()
    line = _make_proc_line(
        procedure_line_id="PL5", procedure_code="9999999"
    )
    opps = detect_anestezi_puani_opportunities(
        [claim], [line], claim_ids_with_procs={"C1"}
    )
    assert opps == []


# ── Billing wrapper ──────────────────────────────────────────────────────────


def _ctx(claim: ClaimHeader, *lines: ProcedureClaimLine) -> PatientClaimContext:
    return PatientClaimContext(
        patient_id=claim.patient_id,
        claims=(claim,),
        procedure_lines=tuple(lines),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )


def test_wrapper_missing_inputs_when_no_procedure_lines() -> None:
    """Wrapper returns MISSING_INPUTS when no procedure lines are present."""
    claim = _make_claim_header()
    ctx = PatientClaimContext(
        patient_id=claim.patient_id,
        claims=(claim,),
        procedure_lines=(),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )
    review = recommend_anestezi_puani_from_claims(ctx)
    assert isinstance(review, AnesteziPuaniReview)
    assert review.exactness_status == EXACTNESS_STATUS_MISSING_INPUTS
    assert review.opportunities == []
    assert review.confirmed_anestezi_try == 0.0
    assert review.required_inputs_missing  # non-empty


def test_wrapper_exact_with_appendektomi() -> None:
    """Wrapper with an inpatient appendektomi line → EXACT, one opportunity."""
    claim = _make_claim_header()
    line = _make_proc_line(procedure_code="610130")
    ctx = _ctx(claim, line)
    review = recommend_anestezi_puani_from_claims(ctx)
    assert review.exactness_status == EXACTNESS_STATUS_EXACT
    assert len(review.opportunities) == 1
    # confirmed_anestezi_try sums included expected_try values
    assert review.confirmed_anestezi_try == pytest.approx(
        8942.14 * _KATSAYI, abs=0.01
    )
