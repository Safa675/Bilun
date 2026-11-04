"""Unit tests for the Workstream C temporal-anomaly detectors.

Covers the two detectors in :mod:`temporal_anomaly`:

- ``detect_procedure_time_overlap``            (#8, honest skip: lines carry no times)
- ``detect_los_procedure_density_anomaly``     (#9, LOS vs service density)
"""

from __future__ import annotations

from datetime import date, timedelta
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


# Admission panel of the showcase medical stays (stories.py ADMIT_PANEL).
_ADMIT_PANEL: tuple[str, ...] = (
    "L107020", "L101850", "L102890", "L104780", "L107420",
    "L106910", "L106150", "L100300", "L101280",
)


def _stay_lines(
    admission: date,
    discharge: date,
    *,
    companion: bool = True,
    codes: tuple[str, ...] = (),
) -> list[ProcedureClaimLine]:
    """Lines billed the way the showcase stays bill them.

    One 510010 bed line per calendar day (admission..discharge inclusive),
    one 510121 companion line per night when ``companion``, then one line
    per ``codes`` entry on the admission day.
    """
    nights = (discharge - admission).days
    rows = [("510010", "yatak", admission + timedelta(days=i)) for i in range(nights + 1)]
    if companion:
        rows += [("510121", "yatak", admission + timedelta(days=i)) for i in range(nights)]
    rows += [
        (code, "laboratuvar" if code.startswith("L") else "islem", admission)
        for code in codes
    ]
    return [
        _make_proc_line(
            procedure_line_id=f"PL{i}",
            claim_id="C1",
            procedure_code=code,
            procedure_category=category,
            procedure_date=day,
        )
        for i, (code, category, day) in enumerate(rows)
    ]


# ===========================================================================
# #8 — detect_procedure_time_overlap
# ===========================================================================


def test_procedure_time_overlap_clean_same_session_bill_no_flag() -> None:
    """Clean S8: two EK-2C packages in one session, same date and branch → no flag.

    P609235 (laparoscopic cholecystectomy) + P603840 (umbilical hernia
    repair through the same port) is the same-session case the SUT prices
    (§2.2.2.B(3)), and MEDULA lines carry no times to show an overlap.
    Checked through the ``PatientClaimContext`` adapter the engine calls.
    """
    # #263: this bill used to get procedure_time_overlap.
    from src.bilun.domain.claims.patient_context import PatientClaimContext
    from src.bilun.domain.prose_rules.temporal_anomaly import (
        detect_procedure_time_overlap_for_context,
    )

    claim = _make_claim_header(
        claim_id="C1", admission=date(2026, 9, 15), discharge=date(2026, 9, 16)
    )
    lines = tuple(
        _make_proc_line(
            procedure_line_id=f"PL{i}",
            claim_id="C1",
            procedure_code=code,
            procedure_category="paket",
            procedure_date=date(2026, 9, 15),
            procedure_specialty_code="1900",  # genel cerrahi
        )
        for i, code in enumerate(("P609235", "P603840"))
    )
    ctx = PatientClaimContext(
        patient_id="P1",
        claims=(claim,),
        procedure_lines=lines,
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )

    assert detect_procedure_time_overlap([claim], list(lines)) == []
    assert detect_procedure_time_overlap_for_context(ctx) == []


@pytest.mark.parametrize(
    ("code_a", "code_b", "category"),
    [
        ("610130", "610140", "cerrahi"),
        ("600010", "600020", "islem"),
        ("610130", "619999", "islem"),
        ("620010", "629999", ""),
        ("P610130", "P620010", "paket"),
    ],
)
def test_procedure_time_overlap_same_date_surgical_pair_no_flag(
    code_a: str,
    code_b: str,
    category: str,
) -> None:
    """Two surgical lines on the same claim, date and specialty → no flag (no times)."""
    # #263: these pairs were flagged before; a shared date is not overlap evidence.
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

    assert violations == []


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
    """6 services on a 1-day stay → density ratio 6.0 > 5 → flag.

    ratio = 5/1 = 5.0 is NOT > 5, so 6 services are needed to exceed the
    strict threshold. The stay's bed, companion and admission-panel lines
    ride along and must not add to the count.
    """
    # #263: services only — daily 51xxxx tariff and L-code lab lines no longer count.
    admission, discharge = date(2026, 7, 10), date(2026, 7, 11)  # LOS = 1 day
    claim = _make_claim_header(
        claim_id="C1",
        claim_type="yatis",
        admission=admission,
        discharge=discharge,
    )
    services = ("801720", "801720", "530100", "530080", "520010", "520010")
    lines = _stay_lines(admission, discharge, codes=(*services, *_ADMIT_PANEL))

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


@pytest.mark.parametrize(
    ("admission", "discharge", "codes", "line_count"),
    [
        pytest.param(
            date(2026, 3, 9),
            date(2026, 3, 15),
            (
                *_ADMIT_PANEL, "L103900", "L106240",
                "906020", "905675", "801720", "530350", "530360",
                "L107020", "L101850", "L103900", "801720",
            ),
            33,
            id="clean-S2-33-lines-6-nights",
        ),
        pytest.param(
            date(2026, 5, 11),
            date(2026, 5, 16),
            (
                *_ADMIT_PANEL, "L107010", "905671", "906020",
                "L107020", "L101850", "L104780",
            ),
            26,
            id="clean-S4-26-lines-5-nights",
        ),
    ],
)
def test_los_density_clean_medical_stay_no_flag(
    admission: date,
    discharge: date,
    codes: tuple[str, ...],
    line_count: int,
) -> None:
    """Clean S2 / S4: daily bed + companion lines and admission labs → no flag.

    Counting every line gave 33/6 = 5.5 and 26/5 = 5.2 (> 5); the services
    alone are 6 over 6 nights and 2 over 5.
    """
    claim = _make_claim_header(claim_id="C1", admission=admission, discharge=discharge)
    lines = _stay_lines(admission, discharge, codes=codes)
    assert len(lines) == line_count

    assert detect_los_procedure_density_anomaly([claim], lines) == []


@pytest.mark.parametrize("companion", [False, True])
@pytest.mark.parametrize("nights", [4, 5])
def test_los_density_tariff_only_stay_ghost_flag(nights: int, companion: bool) -> None:
    """A stay of > 3 nights billed with daily bed (± companion) lines only → ghost stay.

    The 5-night case is six 510010 lines, which got no finding while bed
    lines counted as procedures.
    """
    admission = date(2026, 7, 10)
    discharge = admission + timedelta(days=nights)
    claim = _make_claim_header(claim_id="C1", admission=admission, discharge=discharge)
    lines = _stay_lines(admission, discharge, companion=companion)

    violations = detect_los_procedure_density_anomaly([claim], lines)

    assert len(violations) == 1
    v = violations[0]
    assert v["rule_id"] == "los_procedure_density_anomaly"
    assert v["anomaly_kind"] == "ghost_stay"
    assert v["los_days"] == nights
    assert v["procedure_count"] == 0


def test_los_density_tariff_only_stay_at_threshold_no_flag() -> None:
    """A 3-night bed-only stay is not > 3 nights → no ghost-stay flag."""
    admission, discharge = date(2026, 7, 10), date(2026, 7, 13)
    claim = _make_claim_header(claim_id="C1", admission=admission, discharge=discharge)
    lines = _stay_lines(admission, discharge)

    assert detect_los_procedure_density_anomaly([claim], lines) == []


def test_los_density_tariff_and_lab_only_stay_no_ghost() -> None:
    """Lab lines evidence care: a 5-night stay with bed lines and an admission
    panel is neither dense nor a ghost stay."""
    admission, discharge = date(2026, 7, 10), date(2026, 7, 15)
    claim = _make_claim_header(claim_id="C1", admission=admission, discharge=discharge)
    lines = _stay_lines(admission, discharge, codes=_ADMIT_PANEL)

    assert detect_los_procedure_density_anomaly([claim], lines) == []


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
