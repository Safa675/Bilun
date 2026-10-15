"""Unit tests for the Workstream C temporal-anomaly detectors.

Covers the two detectors in :mod:`temporal_anomaly`:

- ``detect_procedure_time_overlap``            (#8, same-date surgical overlap)
- ``detect_los_procedure_density_anomaly``     (#9, LOS vs procedure density)
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.prose_rules.temporal_anomaly import (
    detect_los_procedure_density_anomaly,
    detect_procedure_time_overlap,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Construction helpers (mirror the pattern in test_common_billing_errors.py).
# ---------------------------------------------------------------------------


def _make_claim_header(
    *,
    claim_id: str = "C1",
    patient_id: str = "P1",
    episode_id: str = "E1",
    claim_type: str = "yatis",
    admission: date | None = date(2026, 7, 10),
    discharge: date | None = date(2026, 7, 13),
    primary_icd10: str = "K35.8",
    department: str = "genel cerrahi",
) -> ClaimHeader:
    return ClaimHeader(
        claim_id=claim_id,
        patient_id=patient_id,
        episode_id=episode_id,
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


def _make_proc_line(
    *,
    procedure_line_id: str = "PL1",
    claim_id: str = "C1",
    procedure_code: str = "610130",
    procedure_category: str = "cerrahi",
    procedure_date: date = date(2026, 7, 10),
    procedure_specialty_code: str = "1000",
    quantity: int = 1,
) -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id=procedure_line_id,
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        procedure_date=procedure_date,
        procedure_code=procedure_code,
        procedure_name="test procedure",
        procedure_category=procedure_category,
        quantity=quantity,
        unit_price_try=Decimal("1000"),
        billed_amount_try=Decimal("1000"),
        expected_payable_try=Decimal("1000"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
        procedure_specialty_code=procedure_specialty_code,
    )


# ===========================================================================
# #8 — detect_procedure_time_overlap
# ===========================================================================


def test_procedure_time_overlap_positive() -> None:
    """Two same-date, same-specialty surgical procedures → overlap flag."""
    claim = _make_claim_header(claim_id="C1")
    l1 = _make_proc_line(
        procedure_line_id="PL1",
        claim_id="C1",
        procedure_code="610130",
        procedure_category="cerrahi",
        procedure_date=date(2026, 7, 10),
        procedure_specialty_code="1000",
    )
    l2 = _make_proc_line(
        procedure_line_id="PL2",
        claim_id="C1",
        procedure_code="610140",
        procedure_category="cerrahi",
        procedure_date=date(2026, 7, 10),  # same date, same specialty
        procedure_specialty_code="1000",
    )

    violations = detect_procedure_time_overlap([claim], [l1, l2])

    assert len(violations) == 1
    v = violations[0]
    assert v["claim_id"] == "C1"
    assert v["rule_id"] == "procedure_time_overlap"
    assert v["severity"] == "warning"
    assert v["type"] == "temporal_anomaly"
    assert v["sut_section_id"] == "2.4"
    assert v["procedure_specialty_code"] == "1000"
    assert v["procedure_date"] == date(2026, 7, 10)
    assert set(v["procedure_codes"]) == {"610130", "610140"}


@pytest.mark.parametrize(
    ("code_a", "code_b", "category"),
    [
        ("600010", "600020", "islem"),
        ("610130", "619999", "islem"),
        ("620010", "629999", ""),
        ("P610130", "P620010", "paket"),
    ],
)
def test_procedure_time_overlap_code_prefix_fallback_60_to_62(
    code_a: str,
    code_b: str,
    category: str,
) -> None:
    """Surgical codes in 60xxxx–62xxxx (and P60xxxx–P62xxxx) match via code prefix when category lacks a keyword."""
    claim = _make_claim_header(claim_id="C1")
    l1 = _make_proc_line(
        procedure_line_id="PL1",
        claim_id="C1",
        procedure_code=code_a,
        procedure_category=category,
        procedure_date=date(2026, 7, 10),
        procedure_specialty_code="1000",
    )
    l2 = _make_proc_line(
        procedure_line_id="PL2",
        claim_id="C1",
        procedure_code=code_b,
        procedure_category=category,
        procedure_date=date(2026, 7, 10),
        procedure_specialty_code="1000",
    )

    violations = detect_procedure_time_overlap([claim], [l1, l2])

    assert len(violations) == 1
    assert set(violations[0]["procedure_codes"]) == {code_a, code_b}


@pytest.mark.parametrize("category", ["islem", "yatak", "", "cerrahi"])
def test_procedure_time_overlap_excludes_51xxxx_bed_codes(category: str) -> None:
    """51xxxx bed/stay tariffs (510010–510121) are never classified as surgical overlap."""
    claim = _make_claim_header(claim_id="C1")
    l1 = _make_proc_line(
        procedure_line_id="PL1",
        claim_id="C1",
        procedure_code="510010",
        procedure_category=category,
        procedure_date=date(2026, 7, 10),
        procedure_specialty_code="1000",
    )
    l2 = _make_proc_line(
        procedure_line_id="PL2",
        claim_id="C1",
        procedure_code="510121",
        procedure_category=category,
        procedure_date=date(2026, 7, 10),
        procedure_specialty_code="1000",
    )

    violations = detect_procedure_time_overlap([claim], [l1, l2])

    assert violations == []


def test_procedure_time_overlap_single_surgery_no_flag() -> None:
    """Only one surgical procedure on the date → no overlap possible."""
    claim = _make_claim_header(claim_id="C1")
    l1 = _make_proc_line(
        procedure_line_id="PL1",
        claim_id="C1",
        procedure_date=date(2026, 7, 10),
        procedure_specialty_code="1000",
    )

    violations = detect_procedure_time_overlap([claim], [l1])

    assert violations == []


def test_procedure_time_overlap_different_specialty_no_flag() -> None:
    """Two surgeries same date but DIFFERENT specialties → no flag (different
    teams / rooms can operate concurrently)."""
    claim = _make_claim_header(claim_id="C1")
    l1 = _make_proc_line(
        procedure_line_id="PL1",
        claim_id="C1",
        procedure_date=date(2026, 7, 10),
        procedure_specialty_code="1000",  # genel cerrahi
    )
    l2 = _make_proc_line(
        procedure_line_id="PL2",
        claim_id="C1",
        procedure_date=date(2026, 7, 10),
        procedure_specialty_code="2000",  # farkli branş
    )

    violations = detect_procedure_time_overlap([claim], [l1, l2])

    assert violations == []


# ===========================================================================
# #9 — detect_los_procedure_density_anomaly
# ===========================================================================


def test_los_density_high_ratio_flag() -> None:
    """5 procedures on a 1-day stay → density ratio 5 → flag.

    ratio = 5/1 = 5.0, which is NOT > 5, so use 6 procedures to exceed the
    strict threshold. Per the spec the ratio>5 boundary is strict, so a
    ratio of exactly 5 should not flag.
    """
    claim = _make_claim_header(
        claim_id="C1",
        claim_type="yatis",
        admission=date(2026, 7, 10),
        discharge=date(2026, 7, 11),  # LOS = 1 day
    )
    # 6 procedures on a 1-day stay → ratio 6.0 > 5 → flag.
    lines = [
        _make_proc_line(
            procedure_line_id=f"PL{i}",
            claim_id="C1",
            procedure_date=date(2026, 7, 10),
            procedure_code="901050",
            procedure_category="laboratuvar",
        )
        for i in range(6)
    ]

    violations = detect_los_procedure_density_anomaly([claim], lines)

    assert len(violations) == 1
    v = violations[0]
    assert v["claim_id"] == "C1"
    assert v["rule_id"] == "los_procedure_density_anomaly"
    assert v["severity"] == "warning"
    assert v["anomaly_kind"] == "high_density"
    assert v["los_days"] == 1
    assert v["procedure_count"] == 6
    assert v["density_ratio"] > 5


def test_los_density_normal_ratio_no_flag() -> None:
    """2 procedures on a 3-day stay → ratio 0.67 → no flag."""
    claim = _make_claim_header(
        claim_id="C1",
        claim_type="yatis",
        admission=date(2026, 7, 10),
        discharge=date(2026, 7, 13),  # LOS = 3 days
    )
    lines = [
        _make_proc_line(
            procedure_line_id="PL1",
            claim_id="C1",
            procedure_date=date(2026, 7, 10),
            procedure_code="901050",
            procedure_category="laboratuvar",
        ),
        _make_proc_line(
            procedure_line_id="PL2",
            claim_id="C1",
            procedure_date=date(2026, 7, 11),
            procedure_code="901050",
            procedure_category="laboratuvar",
        ),
    ]

    violations = detect_los_procedure_density_anomaly([claim], lines)

    assert violations == []


def test_los_density_ghost_stay_flag() -> None:
    """5-day inpatient stay with 0 procedures → ghost-stay flag."""
    claim = _make_claim_header(
        claim_id="C1",
        claim_type="yatis",
        admission=date(2026, 7, 10),
        discharge=date(2026, 7, 15),  # LOS = 5 days, > 3
    )

    violations = detect_los_procedure_density_anomaly([claim], [])

    assert len(violations) == 1
    v = violations[0]
    assert v["claim_id"] == "C1"
    assert v["rule_id"] == "los_procedure_density_anomaly"
    assert v["severity"] == "warning"
    assert v["anomaly_kind"] == "ghost_stay"
    assert v["los_days"] == 5
    assert v["procedure_count"] == 0


def test_los_density_outpatient_no_check() -> None:
    """Outpatient claim (no admission_date) → density check skipped entirely."""
    claim = _make_claim_header(
        claim_id="C1",
        claim_type="poliklinik",
        admission=None,
        discharge=None,
    )
    # Even a high procedure count must not trip the rule on an outpatient claim.
    lines = [
        _make_proc_line(
            procedure_line_id=f"PL{i}",
            claim_id="C1",
            procedure_date=date(2026, 7, 10),
            procedure_code="901050",
            procedure_category="laboratuvar",
        )
        for i in range(6)
    ]

    violations = detect_los_procedure_density_anomaly([claim], lines)

    assert violations == []


# ===========================================================================
# _for_context wrappers smoke-test the PatientClaimContext adapter path.
# ===========================================================================


def test_for_context_wrappers_run_on_empty_context() -> None:
    """Both wrappers return [] for an empty PatientClaimContext."""
    from src.bilun.domain.claims.patient_context import PatientClaimContext

    ctx = PatientClaimContext(
        patient_id="P1",
        claims=(),
        procedure_lines=(),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )
    from src.bilun.domain.prose_rules.temporal_anomaly import (
        detect_los_procedure_density_anomaly_for_context,
        detect_procedure_time_overlap_for_context,
    )

    assert detect_procedure_time_overlap_for_context(ctx) == []
    assert detect_los_procedure_density_anomaly_for_context(ctx) == []
