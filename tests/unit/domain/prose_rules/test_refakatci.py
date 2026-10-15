"""Unit tests for refakatçi (companion bed, 510121) detector."""

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


def _make_procedure_line(
    *,
    claim_id: str = "C1",
    code: str = "510010",
    line_id: str = "L1",
    billed_amount_try: Decimal = Decimal("0"),
):
    from src.bilun.domain.claims.models import ProcedureClaimLine

    return ProcedureClaimLine(
        procedure_line_id=line_id,
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        procedure_date=date(2026, 7, 10),
        procedure_code=code,
        procedure_name="test",
        procedure_category="test",
        quantity=1,
        unit_price_try=billed_amount_try,
        billed_amount_try=billed_amount_try,
        expected_payable_try=billed_amount_try,
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )


def test_3day_inpatient_stay_companion_opportunity() -> None:
    """Inpatient claim Jul 10→13 → 3 companion days × 124.95 × 0.593."""
    from src.bilun.domain.prose_rules.refakatci import (
        detect_refakatci_opportunities,
    )

    header = _make_claim_header(
        admission=date(2026, 7, 10), discharge=date(2026, 7, 13)
    )
    procs = [_make_procedure_line(code="510010")]
    opps = detect_refakatci_opportunities([header], procs)

    assert len(opps) == 1
    opp = opps[0]
    assert opp["days"] == 3
    assert opp["puan"] == pytest.approx(124.95, abs=0.01)
    # 3 × 124.95 × 0.593 = 222.29
    assert opp["expected_try"] == pytest.approx(222.29, abs=0.02)
    assert opp["actual_billed_try"] == 0.0
    assert opp["recoverable_uplift_try"] == pytest.approx(222.29, abs=0.02)
    assert opp["rule_id"] == "refakatci_510121"
    assert opp["sut_section_id"] == "2.6.3"
    assert opp["included_in_sgk_total"] is True
    assert opp["katsayi"] == pytest.approx(0.593, abs=0.001)


def test_same_day_stay_suppressed_day_case() -> None:
    """Same-day admission/discharge (<24h) → suppressed as day-case."""
    from src.bilun.domain.prose_rules.refakatci import (
        detect_refakatci_opportunities,
    )

    header = _make_claim_header(
        admission=date(2026, 7, 10), discharge=date(2026, 7, 10)
    )
    opps = detect_refakatci_opportunities([header], [_make_procedure_line()])

    assert len(opps) == 1
    opp = opps[0]
    assert opp["days"] == 0
    assert opp["expected_try"] == 0.0
    assert opp["recoverable_uplift_try"] == 0.0
    assert opp["included_in_sgk_total"] is False
    notes = opp["suppression_notes"]
    assert any("day_case" in n or "günübirlik" in n.lower() for n in notes)
    assert "§2.2.2.(5)" in opp["detail"]


def test_icu_claim_suppressed() -> None:
    """ICU claim (has 510090) → 510121 suppressed, per-diem applies."""
    from src.bilun.domain.prose_rules.refakatci import (
        detect_refakatci_opportunities,
    )

    header = _make_claim_header(
        admission=date(2026, 7, 10), discharge=date(2026, 7, 13)
    )
    procs = [_make_procedure_line(code="510090", line_id="L-icu")]
    opps = detect_refakatci_opportunities([header], procs)

    assert len(opps) == 1
    opp = opps[0]
    # Days are still counted for informational purposes.
    assert opp["days"] == 3
    assert opp["expected_try"] == 0.0
    assert opp["recoverable_uplift_try"] == 0.0
    assert opp["included_in_sgk_total"] is False
    notes = opp["suppression_notes"]
    assert any("icu" in n.lower() or "per_diem" in n.lower() for n in notes)
    assert "§2.6.3.(3)" in opp["detail"]


@pytest.mark.parametrize(
    "icu_code",
    [
        "P552001",
        "P552002",
        "P552003",
        "P552006",
        "P552007",
        "P552008",
        "552001",
        "552003",
        "p552002",
    ],
)
def test_icu_package_codes_suppressed(icu_code: str) -> None:
    """ICU package codes P552001–P552008 (and bare 552001–552008) suppress 510121."""
    from src.bilun.domain.prose_rules.refakatci import (
        detect_refakatci_opportunities,
    )

    header = _make_claim_header(
        admission=date(2026, 7, 10), discharge=date(2026, 7, 13)
    )
    procs = [_make_procedure_line(code=icu_code, line_id="L-icu-pkg")]
    opps = detect_refakatci_opportunities([header], procs)

    assert len(opps) == 1
    opp = opps[0]
    assert opp["days"] == 3
    assert opp["expected_try"] == 0.0
    assert opp["recoverable_uplift_try"] == 0.0
    assert opp["included_in_sgk_total"] is False
    assert "§2.6.3.(3)" in opp["detail"]


@pytest.mark.parametrize(
    ("admission", "discharge", "expected_puan", "expected_daily_rate", "expected_total"),
    [
        (date(2023, 6, 15), date(2023, 6, 18), 46.28, 27.44, 82.32),
        (date(2024, 7, 1), date(2024, 7, 4), 104.13, 61.75, 185.25),
        (date(2026, 7, 10), date(2026, 7, 13), 124.95, 74.10, 222.29),
    ],
)
def test_historical_admission_date_pricing(
    admission: date,
    discharge: date,
    expected_puan: float,
    expected_daily_rate: float,
    expected_total: float,
) -> None:
    """Companion-bed rate uses the EK-2B 510121 tariff in force on admission_date."""
    from src.bilun.domain.prose_rules.refakatci import (
        detect_refakatci_opportunities,
    )

    header = _make_claim_header(admission=admission, discharge=discharge)
    procs = [_make_procedure_line(code="510010")]
    opps = detect_refakatci_opportunities([header], procs)

    assert len(opps) == 1
    opp = opps[0]
    assert opp["days"] == 3
    assert opp["puan"] == pytest.approx(expected_puan, abs=0.01)
    assert opp["expected_try"] == pytest.approx(expected_total, abs=0.02)
    assert opp["recoverable_uplift_try"] == pytest.approx(expected_total, abs=0.02)
    assert f"{expected_daily_rate:.2f} TRY/day" in opp["detail"]


def test_already_billed_510121_subtracted_from_recoverable() -> None:
    """Already-billed 510121 lines reduce recoverable_uplift_try and confirmed_refakat_try."""
    from src.bilun.domain.billing.types import RefakatciReview
    from src.bilun.domain.prose_rules.refakatci import (
        detect_refakatci_opportunities,
    )

    header = _make_claim_header(
        admission=date(2026, 7, 10), discharge=date(2026, 7, 13)
    )
    # Partial billing: 1 day (74.10 TL) billed out of 3 days (3 × 74.10 = 222.30 TL)
    partial_procs = [
        _make_procedure_line(code="510010", line_id="L-bed"),
        _make_procedure_line(
            code="510121", line_id="L-ref", billed_amount_try=Decimal("74.10")
        ),
    ]
    partial_opps = detect_refakatci_opportunities([header], partial_procs)
    assert len(partial_opps) == 1
    opp = partial_opps[0]
    assert opp["expected_try"] == pytest.approx(222.30, abs=0.01)
    assert opp["actual_billed_try"] == pytest.approx(74.10, abs=0.01)
    assert opp["recoverable_uplift_try"] == pytest.approx(148.20, abs=0.01)
    assert RefakatciReview(opportunities=partial_opps).confirmed_refakat_try == pytest.approx(
        148.20, abs=0.01
    )

    # Full billing: all 222.30 TL already billed -> 0.0 recoverable
    full_procs = [
        _make_procedure_line(code="510010", line_id="L-bed"),
        _make_procedure_line(
            code="510121", line_id="L-ref", billed_amount_try=Decimal("222.30")
        ),
    ]
    full_opps = detect_refakatci_opportunities([header], full_procs)
    assert len(full_opps) == 1
    assert full_opps[0]["expected_try"] == pytest.approx(222.30, abs=0.01)
    assert full_opps[0]["actual_billed_try"] == pytest.approx(222.30, abs=0.01)
    assert full_opps[0]["recoverable_uplift_try"] == 0.0
    assert RefakatciReview(opportunities=full_opps).confirmed_refakat_try == 0.0


def test_outpatient_skipped() -> None:
    """Outpatient claim → no opportunity at all."""
    from src.bilun.domain.prose_rules.refakatci import (
        detect_refakatci_opportunities,
    )

    header = _make_claim_header(claim_type="ayakta")
    opps = detect_refakatci_opportunities([header], [_make_procedure_line()])
    assert opps == []


def test_refakatci_opportunities_survive_public_projection() -> None:
    """expected_try, actual_billed_try, and recoverable_uplift_try survive public projection."""
    from dataclasses import asdict

    from src.bilun.api.public_responses import project_public_response
    from src.bilun.domain.billing.types import EXACTNESS_STATUS_EXACT, RefakatciReview
    from src.bilun.domain.prose_rules.refakatci import (
        detect_refakatci_opportunities,
    )

    header = _make_claim_header(
        admission=date(2026, 7, 10), discharge=date(2026, 7, 13)
    )
    procs = [
        _make_procedure_line(code="510010", line_id="L-bed"),
        _make_procedure_line(
            code="510121", line_id="L-ref", billed_amount_try=Decimal("74.10")
        ),
    ]
    opps = detect_refakatci_opportunities([header], procs)
    review = RefakatciReview(opportunities=opps, exactness_status=EXACTNESS_STATUS_EXACT)
    projected = project_public_response({"refakatci": asdict(review)}, "get_billing_report")

    proj_opp = projected["refakatci"]["opportunities"][0]
    assert proj_opp["expected_try"] == pytest.approx(222.30, abs=0.01)
    assert proj_opp["actual_billed_try"] == pytest.approx(74.10, abs=0.01)
    assert proj_opp["recoverable_uplift_try"] == pytest.approx(148.20, abs=0.01)


def test_package_window_bundles_companion_days_and_bills_excess() -> None:
    """SUT §2.2.2.B-1(1)(h), (3)-(4): companion nights inside EK-2/C package window are bundled (#259)."""
    from src.bilun.domain.claims.models import ProcedureClaimLine
    from src.bilun.domain.prose_rules.refakatci import detect_refakatci_opportunities

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

    # Stay inside Group C (8-day) window: Jul 10 → Jul 15 (5 companion nights: Jul 10..14), surgery Jul 11 (window through Jul 18) -> suppressed (0 days)
    inside_claim = _make_claim_header(
        claim_id="C-IN",
        admission=date(2026, 7, 10),
        discharge=date(2026, 7, 15),
    )
    inside_opps = detect_refakatci_opportunities(
        [inside_claim],
        [_pkg_line("C-IN", "610130", date(2026, 7, 11))],
    )
    assert len(inside_opps) == 1
    assert inside_opps[0]["days"] == 0
    assert inside_opps[0]["expected_try"] == 0.0
    assert inside_opps[0]["recoverable_uplift_try"] == 0.0
    assert inside_opps[0]["included_in_sgk_total"] is False

    # Stay exceeding Group C (8-day) window: Jul 10 → Jul 21 (11 companion nights: Jul 10..20), surgery Jul 11 (window through Jul 18) -> 2 post-window nights (Jul 19, Jul 20)
    excess_claim = _make_claim_header(
        claim_id="C-OUT",
        admission=date(2026, 7, 10),
        discharge=date(2026, 7, 21),
    )
    excess_opps = detect_refakatci_opportunities(
        [excess_claim],
        [_pkg_line("C-OUT", "610130", date(2026, 7, 11))],
    )
    assert len(excess_opps) == 1
    assert excess_opps[0]["days"] == 2
    assert excess_opps[0]["expected_try"] == pytest.approx(2 * 74.10, abs=0.01)
    assert excess_opps[0]["included_in_sgk_total"] is True

