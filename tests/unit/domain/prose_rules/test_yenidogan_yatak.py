"""Unit tests for yenidoğan (newborn) bed billing detector."""

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
    primary_icd10: str = "Z38.0",
    department: str = "genel",
):
    from src.bilun.domain.claims.models import ClaimHeader

    return ClaimHeader(
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        claim_type=claim_type,
        facility_tier="devlet",
        provider_type="sozlesmeli",
        department=department,
        admission_date=admission,
        discharge_date=discharge,
        claim_start_date=admission or date.today(),
        claim_end_date=discharge or date.today(),
        primary_icd10=primary_icd10,
        package_candidate=False,
        expected_total_billed_try=Decimal("1000"),
        expected_total_payable_try=Decimal("900"),
        expected_denial_reason="",
        scenario_tag="test",
    )


def _make_diagnosis(*, claim_id: str = "C1", icd10_code: str = "Z38.0"):
    from src.bilun.domain.claims.models import ClaimDiagnosis

    return ClaimDiagnosis(
        diagnosis_id="DX1",
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        icd10_code=icd10_code,
        is_primary=True,
        diagnosis_role="primary",
        diagnosis_date=date(2026, 7, 10),
        exemption_eligible=False,
    )


def test_newborn_3day_stay_emits_kuvoz() -> None:
    """Newborn claim (Z38) with 3-day stay → Kuvöz (510070) opportunity."""
    from src.bilun.domain.prose_rules.yenidogan_yatak import (
        detect_yenidogan_yatak_opportunities,
    )

    header = _make_claim_header(
        admission=date(2026, 7, 10), discharge=date(2026, 7, 12)
    )
    opps = detect_yenidogan_yatak_opportunities(
        [header],
        [_make_diagnosis(claim_id="C1", icd10_code="Z38.0")],
        claim_ids_with_procs={"C1"},
    )

    assert len(opps) == 1
    opp = opps[0]
    # 3-day inclusive stay (Jul 10, 11, 12).
    assert opp["days"] == 3
    assert opp["bed_code"] == "510070"
    assert opp["puan"] == pytest.approx(743.65, abs=0.01)
    # 3 × 440.98 = 1322.94
    assert opp["expected_try"] == pytest.approx(1322.94, abs=0.01)
    assert opp["rule_id"] == "yenidogan_yatak_510070"
    assert opp["rooming_in"] is False
    assert opp["included_in_sgk_total"] is True
    assert opp["sut_section_id"] == "2.2.2"


def test_rooming_in_suppresses_kot() -> None:
    """Rooming-in baby → Kot (510081) suppressed, no opportunity emitted."""
    from src.bilun.domain.prose_rules.yenidogan_yatak import (
        detect_yenidogan_yatak_opportunities,
    )

    header = _make_claim_header(
        admission=date(2026, 7, 10), discharge=date(2026, 7, 13)
    )
    # Mark this claim as rooming-in ('anne yanında').
    opps = detect_yenidogan_yatak_opportunities(
        [header],
        [_make_diagnosis(claim_id="C1", icd10_code="Z38.1")],
        claim_ids_with_procs={"C1"},
        rooming_in_claim_ids={"C1"},
    )

    # Rooming-in → Kot not billable, Kuvöz not opted in → no opportunity.
    assert opps == []

    # Opting in Kuvöz for rooming-in emits 510070 (not Kot).
    opps_kuvoz = detect_yenidogan_yatak_opportunities(
        [header],
        [_make_diagnosis(claim_id="C1", icd10_code="Z38.1")],
        claim_ids_with_procs={"C1"},
        rooming_in_claim_ids={"C1"},
        emit_kuvoz_for_rooming_in=True,
    )
    assert len(opps_kuvoz) == 1
    assert opps_kuvoz[0]["bed_code"] == "510070"
    assert opps_kuvoz[0]["rooming_in"] is True
    # 510081 Kot must NEVER be emitted for a rooming-in claim.
    assert all(o["bed_code"] != "510081" for o in opps_kuvoz)


def test_non_newborn_claim_skipped() -> None:
    """Adult inpatient claim (no newborn signal) → no opportunity."""
    from src.bilun.domain.prose_rules.yenidogan_yatak import (
        detect_yenidogan_yatak_opportunities,
    )

    header = _make_claim_header(
        primary_icd10="I10",  # adult hypertension, no newborn signal
        department="kardiyoloji",
    )
    opps = detect_yenidogan_yatak_opportunities(
        [header],
        [_make_diagnosis(claim_id="C1", icd10_code="I10")],
        claim_ids_with_procs={"C1"},
    )
    assert opps == []


def test_missing_diagnosis_skipped() -> None:
    """No newborn detection signal (dx nor department) → honest skip."""
    from src.bilun.domain.prose_rules.yenidogan_yatak import (
        detect_yenidogan_yatak_opportunities,
    )

    header = _make_claim_header(primary_icd10="J00", department="genel")
    # No diagnoses list at all, and neither dx nor dept signals newborn.
    opps = detect_yenidogan_yatak_opportunities(
        [header], (), claim_ids_with_procs={"C1"}
    )
    assert opps == []


def test_perinatal_p_code_detected() -> None:
    """P-range perinatal code (P07) also marks a newborn episode."""
    from src.bilun.domain.prose_rules.yenidogan_yatak import (
        detect_yenidogan_yatak_opportunities,
    )

    header = _make_claim_header(
        primary_icd10="P07.3", department="yenidoğan"
    )
    opps = detect_yenidogan_yatak_opportunities(
        [header],
        [_make_diagnosis(claim_id="C1", icd10_code="P07.3")],
        claim_ids_with_procs={"C1"},
    )
    assert len(opps) == 1
    assert opps[0]["bed_code"] == "510070"


def test_department_only_detection() -> None:
    """Department 'yenidoğan' triggers detection even without Z38/P dx."""
    from src.bilun.domain.prose_rules.yenidogan_yatak import (
        detect_yenidogan_yatak_opportunities,
    )

    header = _make_claim_header(primary_icd10="R50", department="Yenidoğan Yoğun Bakım")
    opps = detect_yenidogan_yatak_opportunities(
        [header], (), claim_ids_with_procs={"C1"}
    )
    assert len(opps) == 1
    assert opps[0]["bed_code"] == "510070"


def test_historical_2023_newborn_claim_uses_2023_tariff() -> None:
    """2023 newborn claim resolves the 2023 510070 tariff (275.43 puan), not 2026."""
    from src.bilun.domain.prose_rules.yenidogan_yatak import (
        detect_yenidogan_yatak_opportunities,
    )

    header = _make_claim_header(
        admission=date(2023, 6, 10), discharge=date(2023, 6, 12)
    )
    opps = detect_yenidogan_yatak_opportunities(
        [header], (), claim_ids_with_procs={"C1"}
    )
    assert len(opps) == 1
    assert opps[0]["puan"] == pytest.approx(275.43, abs=0.01)
    assert opps[0]["expected_try"] == pytest.approx(3 * 163.33, abs=0.02)

