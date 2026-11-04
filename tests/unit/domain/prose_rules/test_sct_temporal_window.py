"""Unit tests for the SCT (stem-cell transplant) temporal-window detector.

Covers the El Kitabı Tablo 31 conditional carve-out for code ``704981``
(mezenkimal kök hücre nakli / mesenchymal SCT):

  * Valid add-on only within 60 days of an allogeneic BMT
    (704970/704971/704972) on the same patient.
  * Bundled into the BMT fee when within 90 days of an allogeneic BMT that
    sits on the SAME claim.

The detector needs cross-claim visibility (a prior-admission BMT must be
visible to a current 704981 line), so the four canonical scenarios below use
two separate claims for the same patient.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.sct_temporal_window import (
    ALLOGENEIC_BMT_CODES,
    ADDON_WINDOW_DAYS,
    BUNDLE_WINDOW_DAYS,
    MESENCHYMAL_SCT_CODE,
    detect_sct_temporal_window_violations,
    detect_sct_temporal_window_violations_for_context,
)

pytestmark = pytest.mark.unit

_PATIENT = "P1"
_EPISODE = "E1"

# Catalog anchors (verified via the catalog snapshot):
#   704970 — allojenik BMT (kardeş/akrabadan)        — EK-2/C A1 package
#   704981 — mezenkimal kök hücre nakli              — EK-2/B fee-for-service
_BMT_CODE = "704970"


def _claim(
    *,
    claim_id: str,
    admission: date,
    discharge: date | None = None,
) -> ClaimHeader:
    return ClaimHeader(
        claim_id=claim_id,
        patient_id=_PATIENT,
        episode_id=_EPISODE,
        claim_type="yatis",
        facility_tier="devlet",
        provider_type="sozlesmeli",
        department="hematoloji",
        admission_date=admission,
        discharge_date=discharge,
        claim_start_date=admission,
        claim_end_date=discharge or admission,
        primary_icd10="C92.00",
        expected_total_billed_try=Decimal("100000"),
        expected_total_payable_try=Decimal("90000"),
        expected_denial_reason="",
        scenario_tag="sct_test",
    )


def _proc(
    *,
    procedure_line_id: str,
    claim_id: str,
    procedure_code: str,
    procedure_date: date,
    procedure_name: str = "test procedure",
    procedure_category: str = "islem",
    billed: Decimal = Decimal("92017.29"),
) -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id=procedure_line_id,
        claim_id=claim_id,
        patient_id=_PATIENT,
        episode_id=_EPISODE,
        procedure_date=procedure_date,
        procedure_code=procedure_code,
        procedure_name=procedure_name,
        procedure_category=procedure_category,
        quantity=1,
        unit_price_try=billed,
        billed_amount_try=billed,
        expected_payable_try=billed,
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )


# ── Canonical scenarios (the four required cases) ────────────────────────────


def test_mesenkimal_sct_within_60_days_of_allogeneic_bmt_on_separate_claim_no_violation() -> None:
    """704981 within 60 days of an allogeneic BMT on a SEPARATE claim → valid add-on.

    BMT on claim C1 (2026-01-10), mesenchymal SCT on claim C2 (2026-02-01,
    22 days later). This is the legitimate cross-claim add-on path: no
    violation.
    """
    bmt_date = date(2026, 1, 10)
    sct_date = date(2026, 2, 1)  # 22 days after BMT — inside 60-day window
    assert 0 <= (sct_date - bmt_date).days <= ADDON_WINDOW_DAYS

    c1 = _claim(claim_id="C1", admission=bmt_date, discharge=date(2026, 1, 20))
    c2 = _claim(claim_id="C2", admission=sct_date, discharge=date(2026, 2, 5))
    bmt = _proc(
        procedure_line_id="BMT1",
        claim_id="C1",
        procedure_code=_BMT_CODE,
        procedure_date=bmt_date,
    )
    sct = _proc(
        procedure_line_id="SCT1",
        claim_id="C2",
        procedure_code=MESENCHYMAL_SCT_CODE,
        procedure_date=sct_date,
    )

    violations = detect_sct_temporal_window_violations([c1, c2], [bmt, sct])
    assert violations == []

    # Also exercise the PatientClaimContext entry point (the canonical wiring).
    ctx = PatientClaimContext(
        patient_id=_PATIENT,
        claims=(c1, c2),
        procedure_lines=(bmt, sct),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )
    assert detect_sct_temporal_window_violations_for_context(ctx) == []


def test_mesenkimal_sct_without_any_bmt_emits_addon_violation() -> None:
    """704981 billed with NO allogeneic BMT on the patient → add-on violation."""
    sct_date = date(2026, 3, 15)
    c2 = _claim(claim_id="C2", admission=sct_date, discharge=date(2026, 3, 20))
    sct = _proc(
        procedure_line_id="SCT1",
        claim_id="C2",
        procedure_code=MESENCHYMAL_SCT_CODE,
        procedure_date=sct_date,
    )

    violations = detect_sct_temporal_window_violations([c2], [sct])
    assert len(violations) == 1
    v = violations[0]
    assert v["type"] == "sct_addon_without_primary"
    assert v["rule_id"] == "sct_addon_without_qualifying_bmt"
    assert v["procedure_code"] == MESENCHYMAL_SCT_CODE
    assert v["primary_bmt_code"] == ""  # no qualifying primary
    assert v["gap_days"] is None
    assert v["same_claim_as_bmt"] is False
    assert v["risk_amount_try"] == pytest.approx(92017.29)


def test_mesenkimal_sct_beyond_60_day_window_emits_addon_violation() -> None:
    """704981 >60 days after the allogeneic BMT → outside add-on window → violation.

    BMT on C1 (2026-01-10), mesenchymal SCT on C2 (2026-05-01, 111 days
    later — well past the 60-day window but the BMT clearly exists, so the
    finding is "outside window" rather than "no primary".
    """
    bmt_date = date(2026, 1, 10)
    sct_date = date(2026, 5, 1)  # 111 days after BMT — outside 60-day window
    gap = (sct_date - bmt_date).days
    assert gap > ADDON_WINDOW_DAYS

    c1 = _claim(claim_id="C1", admission=bmt_date, discharge=date(2026, 1, 20))
    c2 = _claim(claim_id="C2", admission=sct_date, discharge=date(2026, 5, 5))
    bmt = _proc(
        procedure_line_id="BMT1",
        claim_id="C1",
        procedure_code=_BMT_CODE,
        procedure_date=bmt_date,
    )
    sct = _proc(
        procedure_line_id="SCT1",
        claim_id="C2",
        procedure_code=MESENCHYMAL_SCT_CODE,
        procedure_date=sct_date,
    )

    violations = detect_sct_temporal_window_violations([c1, c2], [bmt, sct])
    assert len(violations) == 1
    v = violations[0]
    assert v["type"] == "sct_addon_without_primary"
    assert v["procedure_code"] == MESENCHYMAL_SCT_CODE
    # The BMT exists but is too old → it is recorded on the finding.
    assert v["primary_bmt_code"] == _BMT_CODE
    assert v["gap_days"] == gap
    assert v["same_claim_as_bmt"] is False  # BMT is on C1, SCT on C2


def test_mesenkimal_sct_on_same_claim_as_allogeneic_bmt_emits_bundled_violation() -> None:
    """704981 on the SAME claim as an allogeneic BMT (within 90 days) → bundled.

    Both procedures on claim C1 (BMT 2026-01-10, SCT 2026-02-20 — 41 days
    later, so inside the 90-day bundle window AND inside 60-day add-on window).
    Because they share a claim, bundling is the correct (more specific) finding;
    the add-on finding must NOT also fire.
    """
    bmt_date = date(2026, 1, 10)
    sct_date = date(2026, 2, 20)  # 41 days after BMT
    gap = (sct_date - bmt_date).days
    assert gap <= BUNDLE_WINDOW_DAYS
    assert gap <= ADDON_WINDOW_DAYS  # both windows apply; bundling wins

    c1 = _claim(claim_id="C1", admission=bmt_date, discharge=date(2026, 3, 1))
    bmt = _proc(
        procedure_line_id="BMT1",
        claim_id="C1",
        procedure_code=_BMT_CODE,
        procedure_date=bmt_date,
    )
    sct = _proc(
        procedure_line_id="SCT1",
        claim_id="C1",
        procedure_code=MESENCHYMAL_SCT_CODE,
        procedure_date=sct_date,
    )

    violations = detect_sct_temporal_window_violations([c1], [bmt, sct])
    assert len(violations) == 1
    v = violations[0]
    assert v["type"] == "sct_bundled_with_bmt"
    assert v["rule_id"] == "sct_mesenkimal_bundled_with_allogeneic_bmt"
    assert v["procedure_code"] == MESENCHYMAL_SCT_CODE
    assert v["primary_bmt_code"] == _BMT_CODE
    assert v["gap_days"] == gap
    assert v["same_claim_as_bmt"] is True


# ── Supporting edge-case coverage ────────────────────────────────────────────


@pytest.mark.parametrize("bmt_code", sorted(ALLOGENEIC_BMT_CODES))
def test_all_allogeneic_bmt_codes_qualify_as_primary(bmt_code: str) -> None:
    """Every allogeneic BMT code (704970/704971/704972) qualifies a 704981 add-on."""
    bmt_date = date(2026, 1, 10)
    sct_date = date(2026, 1, 30)  # 20 days — inside 60-day window
    c1 = _claim(claim_id="C1", admission=bmt_date, discharge=date(2026, 1, 20))
    c2 = _claim(claim_id="C2", admission=sct_date, discharge=date(2026, 2, 1))
    bmt = _proc(
        procedure_line_id="BMT1", claim_id="C1", procedure_code=bmt_code, procedure_date=bmt_date
    )
    sct = _proc(
        procedure_line_id="SCT1",
        claim_id="C2",
        procedure_code=MESENCHYMAL_SCT_CODE,
        procedure_date=sct_date,
    )
    assert detect_sct_temporal_window_violations([c1, c2], [bmt, sct]) == []


def test_sct_billed_before_bmt_emits_addon_violation() -> None:
    """A mesenchymal SCT billed BEFORE the BMT is not a post-BMT add-on → violation.

    The handbook window is explicitly "after" the allogeneic transplant, so a
    negative day gap is treated as outside the window.
    """
    sct_date = date(2026, 1, 5)
    bmt_date = date(2026, 2, 1)  # BMT AFTER the SCT
    c1 = _claim(claim_id="C1", admission=bmt_date, discharge=date(2026, 2, 10))
    c2 = _claim(claim_id="C2", admission=sct_date, discharge=date(2026, 1, 8))
    bmt = _proc(
        procedure_line_id="BMT1", claim_id="C1", procedure_code=_BMT_CODE, procedure_date=bmt_date
    )
    sct = _proc(
        procedure_line_id="SCT1",
        claim_id="C2",
        procedure_code=MESENCHYMAL_SCT_CODE,
        procedure_date=sct_date,
    )
    violations = detect_sct_temporal_window_violations([c1, c2], [bmt, sct])
    assert len(violations) == 1
    assert violations[0]["type"] == "sct_addon_without_primary"


def test_zero_billed_sct_line_is_ignored() -> None:
    """A 704981 line with zero billed amount (already bundled on the claim) → skip."""
    sct_date = date(2026, 3, 1)
    c2 = _claim(claim_id="C2", admission=sct_date, discharge=date(2026, 3, 5))
    sct = _proc(
        procedure_line_id="SCT1",
        claim_id="C2",
        procedure_code=MESENCHYMAL_SCT_CODE,
        procedure_date=sct_date,
        billed=Decimal("0"),
    )
    assert detect_sct_temporal_window_violations([c2], [sct]) == []


def test_non_mesenchymal_procedure_lines_are_ignored() -> None:
    """Lines for codes other than 704981 are never flagged by this detector."""
    sct_date = date(2026, 3, 1)
    c2 = _claim(claim_id="C2", admission=sct_date, discharge=date(2026, 3, 5))
    other = _proc(
        procedure_line_id="X1",
        claim_id="C2",
        procedure_code="704980",  # autologous SCT — out of scope for this detector
        procedure_date=sct_date,
    )
    assert detect_sct_temporal_window_violations([c2], [other]) == []


def test_empty_inputs_return_no_violations() -> None:
    """Defensive: no lines → no violations."""
    assert detect_sct_temporal_window_violations([], []) == []


def test_bundled_pre_empts_addon_exactly_one_violation() -> None:
    """A same-claim BMT (inside both 60- and 90-day windows) yields ONE bundled
    violation, never both a bundled and an add-on finding for the same line."""
    bmt_date = date(2026, 1, 10)
    sct_date = date(2026, 2, 1)  # 22 days — inside 60 and inside 90
    c1 = _claim(claim_id="C1", admission=bmt_date, discharge=date(2026, 2, 10))
    bmt = _proc(
        procedure_line_id="BMT1", claim_id="C1", procedure_code=_BMT_CODE, procedure_date=bmt_date
    )
    sct = _proc(
        procedure_line_id="SCT1",
        claim_id="C1",
        procedure_code=MESENCHYMAL_SCT_CODE,
        procedure_date=sct_date,
    )
    violations = detect_sct_temporal_window_violations([c1], [bmt, sct])
    assert len(violations) == 1
    assert violations[0]["type"] == "sct_bundled_with_bmt"
