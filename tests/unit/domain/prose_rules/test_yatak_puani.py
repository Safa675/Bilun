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
