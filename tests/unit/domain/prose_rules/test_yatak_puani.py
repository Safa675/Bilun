"""Unit tests for yatak puanı (bed-day billing) detector."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

pytestmark = pytest.mark.unit


def _make_claim_header(
    *,
    claim_id: str = "C1",
    claim_type: str = "yatis",
    admission: date | None = date(2026, 7, 10),
    discharge: date | None = date(2026, 7, 13),
):
    from src.bilun.domain.claims.models import ClaimHeader

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
        primary_icd10="Z00.0",
        package_candidate=False,
        expected_total_billed_try=Decimal("1000"),
        expected_total_payable_try=Decimal("900"),
        expected_denial_reason="",
        scenario_tag="test",
    )


def test_inpatient_4day_stay() -> None:
    """Inpatient claim Jul 10→13 → 4 bed-days (inclusive LOS)."""
    from src.bilun.domain.prose_rules.yatak_puani import detect_yatak_puani_opportunities

    header = _make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 13))
    opps = detect_yatak_puani_opportunities([header], claim_ids_with_procs={"C1"})

    assert len(opps) == 1
    opp = opps[0]
    assert opp["bed_days"] == 4
    assert opp["daily_rate_try"] == pytest.approx(222.36, abs=0.01)
    # 4 × 222.36 = 889.44
    assert opp["expected_yatak_try"] == pytest.approx(889.44, abs=0.01)
    assert opp["rule_id"] == "yatak_puani_510010"
    assert opp["included_in_sgk_total"] is True


def test_same_day_stay_flags_gunduz() -> None:
    """Same-day admission/discharge → 1 day billable + gündüz flag."""
    from src.bilun.domain.prose_rules.yatak_puani import detect_yatak_puani_opportunities

    header = _make_claim_header(
        admission=date(2026, 7, 10), discharge=date(2026, 7, 10)
    )
    opps = detect_yatak_puani_opportunities([header], claim_ids_with_procs={"C1"})

    assert len(opps) == 1
    opp = opps[0]
    assert opp["bed_days"] == 1
    assert opp["same_day_stay"] is True
    assert "510120" in opp["detail"]


def test_outpatient_skipped() -> None:
    """Outpatient claim → no opportunity."""
    from src.bilun.domain.prose_rules.yatak_puani import detect_yatak_puani_opportunities

    header = _make_claim_header(claim_type="ayakta")
    opps = detect_yatak_puani_opportunities([header], claim_ids_with_procs={"C1"})
    assert opps == []


def test_null_dates_skipped() -> None:
    """Null admission or discharge → no opportunity."""
    from src.bilun.domain.prose_rules.yatak_puani import detect_yatak_puani_opportunities

    header = _make_claim_header(admission=None, discharge=date(2026, 7, 13))
    assert detect_yatak_puani_opportunities([header], claim_ids_with_procs={"C1"}) == []

    header2 = _make_claim_header(admission=date(2026, 7, 10), discharge=None)
    assert detect_yatak_puani_opportunities([header2], claim_ids_with_procs={"C1"}) == []


def test_claim_without_procs_skipped() -> None:
    """Claim not in claim_ids_with_procs → skipped."""
    from src.bilun.domain.prose_rules.yatak_puani import detect_yatak_puani_opportunities

    header = _make_claim_header()
    # C1 NOT in the set
    opps = detect_yatak_puani_opportunities([header], claim_ids_with_procs={"OTHER"})
    assert opps == []


def test_historical_2023_claim_uses_2023_bed_tariff() -> None:
    """2023 inpatient claim resolves the 2023 510010 tariff (82.36 TRY), not 2026."""
    from src.bilun.domain.prose_rules.yatak_puani import detect_yatak_puani_opportunities

    header = _make_claim_header(
        admission=date(2023, 6, 10), discharge=date(2023, 6, 13)
    )
    opps = detect_yatak_puani_opportunities([header], claim_ids_with_procs={"C1"})
    assert len(opps) == 1
    assert opps[0]["daily_rate_try"] == pytest.approx(82.36, abs=0.01)
    assert opps[0]["expected_yatak_try"] == pytest.approx(4 * 82.36, abs=0.01)


def test_confirmed_yatak_and_actions_use_recoverable_gap() -> None:
    """confirmed_yatak_try and collect_billing_actions use recoverable_uplift_try and skip zero-gap rows (#233)."""
    from decimal import Decimal

    from src.bilun.domain.billing.billing_actions import collect_billing_actions
    from src.bilun.domain.billing.types import (
        BillingActionReport,
        IcuPuaniReview,
        YatakPuaniReview,
    )
    from src.bilun.domain.claims.models import ProcedureClaimLine
    from src.bilun.domain.prose_rules.yatak_puani import detect_yatak_puani_opportunities

    header = _make_claim_header(
        claim_id="F-SENTETIK-HASTA-0001-005",
        admission=date(2026, 7, 10),
        discharge=date(2026, 7, 13),
    )

    def _bed_line(billed: str) -> ProcedureClaimLine:
        return ProcedureClaimLine(
            procedure_line_id="L-BED",
            claim_id=header.claim_id,
            patient_id="P1",
            episode_id="E1",
            procedure_date=date(2026, 7, 10),
            procedure_code="510010",
            procedure_name="Standart yatak",
            procedure_category="yatak",
            quantity=1,
            unit_price_try=Decimal(billed),
            billed_amount_try=Decimal(billed),
            expected_payable_try=Decimal(billed),
            is_package_included=False,
            package_code="",
            surcharge_applicable=False,
            copay_rate_applicable=False,
            denial_reason_expected="",
            rule_trace_expected="",
        )

    # Partial billing: 889.44 expected, 693.76 billed -> 195.68 recoverable
    partial_opps = detect_yatak_puani_opportunities([header], [_bed_line("693.76")])
    partial_review = YatakPuaniReview(opportunities=partial_opps, exactness_status="exact")
    assert partial_review.confirmed_yatak_try == pytest.approx(195.68, abs=0.01)
    partial_actions = collect_billing_actions(
        BillingActionReport(patient_id="P1", yatak_puani=partial_review)
    )
    yatak_actions = [a for a in partial_actions if a["surface"] == "yatak_puani"]
    assert len(yatak_actions) == 1
    assert yatak_actions[0]["sgk_uplift_try"] == pytest.approx(195.68, abs=0.01)

    # Full billing: 889.44 billed against 889.44 expected -> 0.0 recoverable, no action
    full_opps = detect_yatak_puani_opportunities([header], [_bed_line("889.44")])
    full_review = YatakPuaniReview(opportunities=full_opps, exactness_status="exact")
    assert full_review.confirmed_yatak_try == 0.0
    full_actions = collect_billing_actions(
        BillingActionReport(patient_id="P1", yatak_puani=full_review)
    )
    assert [a for a in full_actions if a["surface"] == "yatak_puani"] == []

    # Fully billed ICU stay: recoverable_uplift_try == 0.0 does not fall back to total_try
    icu_review = IcuPuaniReview(
        opportunities=[
            {
                "claim_id": "C-ICU",
                "total_try": 5000.0,
                "actual_billed_try": 5000.0,
                "recoverable_uplift_try": 0.0,
                "included_in_sgk_total": True,
            }
        ],
        exactness_status="exact",
    )
    assert icu_review.confirmed_icu_try == 0.0


def test_package_window_bundles_stay_inside_and_bills_excess_days() -> None:
    """SUT §2.2.2.B-1(1), (3)-(4): EK-2/C package window bundles days through window end and bills only post-window days (#259)."""
    from src.bilun.domain.claims.models import ProcedureClaimLine
    from src.bilun.domain.prose_rules.yatak_puani import detect_yatak_puani_opportunities

    def _pkg_line(claim_id: str, code: str, proc_date: date) -> ProcedureClaimLine:
        return ProcedureClaimLine(
            procedure_line_id=f"PKG-{claim_id}",
            claim_id=claim_id,
            patient_id="P1",
            episode_id="E1",
            procedure_date=proc_date,
            procedure_code=code,
            procedure_name="Paket işlem",
            procedure_category="paket",
            quantity=1,
            unit_price_try=Decimal("5000.00"),
            billed_amount_try=Decimal("5000.00"),
            expected_payable_try=Decimal("5000.00"),
            is_package_included=True,
            package_code=f"P{code}",
            surcharge_applicable=False,
            copay_rate_applicable=False,
            denial_reason_expected="",
            rule_trace_expected="",
        )

    # Stay inside Group C (8-day) window: Jul 10 → Jul 15 (6 gross days), surgery Jul 11 (window through Jul 18) -> 0 billable days
    inside_claim = _make_claim_header(
        claim_id="C-IN",
        admission=date(2026, 7, 10),
        discharge=date(2026, 7, 15),
    )
    inside_opps = detect_yatak_puani_opportunities(
        [inside_claim],
        [_pkg_line("C-IN", "610130", date(2026, 7, 11))],
    )
    assert len(inside_opps) == 1
    assert inside_opps[0]["gross_bed_days"] == 6
    assert inside_opps[0]["bundled_days"] == 6
    assert inside_opps[0]["bed_days"] == 0
    assert inside_opps[0]["expected_yatak_try"] == 0.0

    # Stay exceeding Group C (8-day) window: Jul 10 → Jul 20 (11 gross days), surgery Jul 11 (window through Jul 18) -> 2 post-window days (Jul 19, Jul 20)
    excess_claim = _make_claim_header(
        claim_id="C-OUT",
        admission=date(2026, 7, 10),
        discharge=date(2026, 7, 20),
    )
    excess_opps = detect_yatak_puani_opportunities(
        [excess_claim],
        [_pkg_line("C-OUT", "610130", date(2026, 7, 11))],
    )
    assert len(excess_opps) == 1
    assert excess_opps[0]["gross_bed_days"] == 11
    assert excess_opps[0]["bundled_days"] == 9
    assert excess_opps[0]["bed_days"] == 2
    assert excess_opps[0]["expected_yatak_try"] == pytest.approx(2 * 222.36, abs=0.01)


