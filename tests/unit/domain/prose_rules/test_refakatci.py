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
        unit_price_try=Decimal("0"),
        billed_amount_try=Decimal("0"),
        expected_payable_try=Decimal("0"),
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
    assert opp["included_in_sgk_total"] is False
    notes = opp["suppression_notes"]
    assert any("icu" in n.lower() or "per_diem" in n.lower() for n in notes)
    assert "§2.6.3.(3)" in opp["detail"]


def test_outpatient_skipped() -> None:
    """Outpatient claim → no opportunity at all."""
    from src.bilun.domain.prose_rules.refakatci import (
        detect_refakatci_opportunities,
    )

    header = _make_claim_header(claim_type="ayakta")
    opps = detect_refakatci_opportunities([header], [_make_procedure_line()])
    assert opps == []


def test_historical_2023_companion_claim_uses_2023_tariff() -> None:
    """2023 inpatient claim resolves 2023 510121 puan (46.28), not 2026 (124.95)."""
    from src.bilun.domain.prose_rules.refakatci import (
        detect_refakatci_opportunities,
    )

    header = _make_claim_header(
        admission=date(2023, 6, 10), discharge=date(2023, 6, 13)
    )
    opps = detect_refakatci_opportunities([header], [_make_procedure_line()])
    assert len(opps) == 1
    assert opps[0]["puan"] == pytest.approx(46.28, abs=0.01)
    assert opps[0]["expected_try"] == pytest.approx(82.32, abs=0.02)

