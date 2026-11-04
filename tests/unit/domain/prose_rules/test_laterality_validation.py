"""Unit tests for the §2.4 laterality (sag_sol) validation detectors.

Covers:
- ``detect_missing_laterality_imaging``  (laterality #6 — bilateral MR/CT)
- ``detect_missing_laterality_surgery``   (laterality #17 — paired-organ surgery)

The honest-skip (B-guard) test is the most important: when no line carries a
non-empty ``sag_sol``, both detectors MUST return ``[]`` to avoid a false-
positive flood on data sources that don't populate the field yet.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.prose_rules.laterality_validation import (
    detect_missing_laterality_imaging,
    detect_missing_laterality_imaging_for_context,
    detect_missing_laterality_surgery,
    detect_missing_laterality_surgery_for_context,
)
from src.bilun.domain.prose_rules.types import (
    SAVINGS_BASIS_SOURCED,
    SAVINGS_CATEGORY_SGK_UPLIFT,
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
    claim_type: str = "ayakta",
    admission: date | None = None,
    discharge: date | None = None,
    primary_icd10: str = "Z00.0",
    department: str = "genel",
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
    procedure_code: str = "801010",
    procedure_name: str = "MR Diz (Knee)",
    procedure_category: str = "radioloji",
    procedure_date: date = date(2026, 7, 10),
    quantity: int = 1,
    sag_sol: str = "",
) -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id=procedure_line_id,
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        procedure_date=procedure_date,
        procedure_code=procedure_code,
        procedure_name=procedure_name,
        procedure_category=procedure_category,
        quantity=quantity,
        unit_price_try=Decimal("1000"),
        billed_amount_try=Decimal("1000"),
        expected_payable_try=Decimal("900"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
        procedure_specialty_code="",
        sag_sol=sag_sol,
    )


class _Ctx:
    """Minimal stand-in for PatientClaimContext for the _for_context wrappers."""

    def __init__(self, claims: list[ClaimHeader], procedure_lines: list[ProcedureClaimLine]) -> None:
        self.claims = claims
        self.procedure_lines = procedure_lines


# ===========================================================================
# B1 — detect_missing_laterality_imaging (#6 bilateral MR/CT)
# ===========================================================================


class TestMissingLateralityImaging:
    """#6 — Bilateral MR/CT without laterality."""

    def test_honest_skip_all_empty_returns_empty(self) -> None:
        """B-guard (MOST IMPORTANT): when every sag_sol is '', return []."""
        header = _make_claim_header()
        lines = [
            _make_proc_line(
                procedure_line_id="PL1",
                procedure_code="801010",  # MR knee — paired
                sag_sol="",
            ),
            _make_proc_line(
                procedure_line_id="PL2",
                procedure_code="803010",  # CT knee — paired
                sag_sol="",
            ),
        ]
        assert detect_missing_laterality_imaging([header], lines) == []

    def test_mr_knee_missing_side_is_flagged(self) -> None:
        """MR knee (paired), quantity=1, sag_sol='' and at least one non-empty
        elsewhere in the dataset → violation."""
        header = _make_claim_header()
        lines = [
            _make_proc_line(
                procedure_line_id="PL1",
                procedure_code="801010",  # MR knee
                sag_sol="",
            ),
            # A second line elsewhere carries a real side — this is what lifts
            # the B-guard (proves the data source populates sag_sol).
            _make_proc_line(
                procedure_line_id="PL2",
                procedure_code="801110",  # MR shoulder
                sag_sol="1",
            ),
        ]
        violations = detect_missing_laterality_imaging([header], lines)
        assert len(violations) == 1
        v = violations[0]
        assert v["rule_id"] == "missing_laterality_imaging"
        assert v["type"] == "laterality_validation"
        assert v["sut_section_id"] == "2.4"
        assert v["severity"] == "warning"
        assert v["claim_id"] == "C1"
        assert v["procedure_code"] == "801010"
        assert v["sag_sol"] == ""

    def test_mr_knee_with_side_not_flagged(self) -> None:
        """MR knee with sag_sol='1' (right) → no violation."""
        header = _make_claim_header()
        lines = [
            _make_proc_line(
                procedure_code="801010",  # MR knee
                sag_sol="1",
            ),
        ]
        assert detect_missing_laterality_imaging([header], lines) == []

    def test_mr_brain_not_paired_not_flagged(self) -> None:
        """MR brain is a single/midline organ — never flagged even with sag_sol=''."""
        header = _make_claim_header()
        # MR brain (801001) shares the 4-char prefix 8010 with knee MR, but at
        # 5 chars (80100) it is NOT in the paired-organ set → correctly excluded.
        lines = [
            _make_proc_line(
                procedure_code="801001",  # MR beyin (brain) — not paired
                sag_sol="",
            ),
            # Lift the B-guard with a paired line carrying a side.
            _make_proc_line(
                procedure_line_id="PL2",
                procedure_code="801010",
                sag_sol="1",
            ),
        ]
        assert detect_missing_laterality_imaging([header], lines) == []

    def test_sag_sol_none_sentinel_is_flagged(self) -> None:
        """sag_sol='3' (Ayrım yok) on a paired-organ MR is treated as missing."""
        header = _make_claim_header()
        lines = [
            _make_proc_line(
                procedure_code="801010",  # MR knee
                sag_sol="3",
            ),
        ]
        violations = detect_missing_laterality_imaging([header], lines)
        assert len(violations) == 1
        assert violations[0]["sag_sol"] == "3"

    def test_claim_filter_gate_respected(self) -> None:
        """claim_ids_with_procs gate excludes lines on non-listed claims."""
        header = _make_claim_header()
        lines = [
            _make_proc_line(claim_id="C1", procedure_code="801010", sag_sol=""),
            _make_proc_line(
                procedure_line_id="PL2",
                claim_id="C2",
                procedure_code="801110",
                sag_sol="1",
            ),
        ]
        result = detect_missing_laterality_imaging(
            [header], lines, claim_ids_with_procs={"C9"}  # neither claim listed
        )
        assert result == []


# ===========================================================================
# B2 — detect_missing_laterality_surgery (#17 paired-organ surgery)
# ===========================================================================


class TestMissingLateralitySurgery:
    """#17 — Missing laterality on bilateral-organ surgery."""

    def test_honest_skip_all_empty_returns_empty(self) -> None:
        """B-guard (MOST IMPORTANT): when every sag_sol is '', return []."""
        header = _make_claim_header()
        lines = [
            _make_proc_line(
                procedure_line_id="PL1",
                procedure_code="516030",  # cataract
                procedure_category="goz_cerrahisi",
                sag_sol="",
            ),
            _make_proc_line(
                procedure_line_id="PL2",
                procedure_code="505010",  # kidney
                procedure_category="uroloji",
                sag_sol="",
            ),
        ]
        assert detect_missing_laterality_surgery([header], lines) == []

    def test_cataract_missing_side_is_flagged(self) -> None:
        """Cataract (516xxx, paired organ) with sag_sol='' and at least one
        non-empty elsewhere → violation."""
        header = _make_claim_header()
        lines = [
            _make_proc_line(
                procedure_line_id="PL1",
                procedure_code="516030",  # cataract surgery
                procedure_name="Katarak Ameliyatı",
                procedure_category="goz_cerrahisi",
                sag_sol="",
            ),
            _make_proc_line(
                procedure_line_id="PL2",
                procedure_code="516040",
                procedure_category="goz_cerrahisi",
                sag_sol="2",
            ),
        ]
        violations = detect_missing_laterality_surgery([header], lines)
        assert len(violations) == 1
        v = violations[0]
        assert v["rule_id"] == "missing_laterality_surgery"
        assert v["type"] == "laterality_validation"
        assert v["sut_section_id"] == "2.4"
        assert v["severity"] == "warning"
        assert v["claim_id"] == "C1"
        assert v["procedure_code"] == "516030"
        assert v["sag_sol"] == ""

    def test_cataract_with_side_not_flagged(self) -> None:
        """Cataract with sag_sol='2' (left) → no violation."""
        header = _make_claim_header()
        lines = [
            _make_proc_line(
                procedure_code="516030",
                procedure_category="goz_cerrahisi",
                sag_sol="2",
            ),
        ]
        assert detect_missing_laterality_surgery([header], lines) == []

    def test_appendectomy_non_paired_not_flagged(self) -> None:
        """Appendectomy is not a paired-organ procedure → never flagged."""
        header = _make_claim_header()
        lines = [
            _make_proc_line(
                procedure_code="510310",  # appendectomy (510xxx but appendix)
                procedure_category="genel_cerrahi",
                sag_sol="",
            ),
            # Lift the B-guard.
            _make_proc_line(
                procedure_line_id="PL2",
                procedure_code="516030",
                procedure_category="goz_cerrahisi",
                sag_sol="1",
            ),
        ]
        result = detect_missing_laterality_surgery([header], lines)
        # The appendectomy line must NOT appear; the cataract line is paired
        # so it WOULD be flagged by sag_sol='' — but its side is '1', so the
        # whole result is empty.
        assert result == []
        assert all(v["procedure_code"] != "510310" for v in result)


# ===========================================================================
# _for_context wrappers
# ===========================================================================


class TestForContextWrappers:
    """The _for_context wrappers bridge PatientClaimContext to the flat-list API."""

    def test_imaging_for_context_honest_skip(self) -> None:
        """All-empty sag_sol → wrapper returns []."""
        header = _make_claim_header()
        ctx = _Ctx(
            [header],
            [_make_proc_line(procedure_code="801010", sag_sol="")],
        )
        assert detect_missing_laterality_imaging_for_context(ctx) == []

    def test_imaging_for_context_flags(self) -> None:
        header = _make_claim_header()
        ctx = _Ctx(
            [header],
            [
                _make_proc_line(procedure_code="801010", sag_sol=""),
                _make_proc_line(
                    procedure_line_id="PL2", procedure_code="801110", sag_sol="1"
                ),
            ],
        )
        result = detect_missing_laterality_imaging_for_context(ctx)
        assert len(result) == 1
        assert result[0]["rule_id"] == "missing_laterality_imaging"

    def test_surgery_for_context_honest_skip(self) -> None:
        header = _make_claim_header()
        ctx = _Ctx(
            [header],
            [
                _make_proc_line(
                    procedure_code="516030",
                    procedure_category="goz_cerrahisi",
                    sag_sol="",
                ),
            ],
        )
        assert detect_missing_laterality_surgery_for_context(ctx) == []

    def test_surgery_for_context_flags(self) -> None:
        header = _make_claim_header()
        ctx = _Ctx(
            [header],
            [
                _make_proc_line(
                    procedure_code="516030",
                    procedure_category="goz_cerrahisi",
                    sag_sol="",
                ),
                _make_proc_line(
                    procedure_line_id="PL2",
                    procedure_code="516040",
                    procedure_category="goz_cerrahisi",
                    sag_sol="2",
                ),
            ],
        )
        result = detect_missing_laterality_surgery_for_context(ctx)
        assert len(result) == 1
        assert result[0]["rule_id"] == "missing_laterality_surgery"


# ---------------------------------------------------------------------------
# Violation-shape contract — mirrors common_billing_errors exactly.
# ---------------------------------------------------------------------------


def test_violation_dict_shape_matches_contract() -> None:
    """The emitted dict carries the uniform keys in the canonical shape."""
    header = _make_claim_header()
    lines = [
        _make_proc_line(procedure_code="801010", sag_sol=""),
        _make_proc_line(procedure_line_id="PL2", procedure_code="801110", sag_sol="1"),
    ]
    v = detect_missing_laterality_imaging([header], lines)[0]
    # The eight canonical keys (common_billing_errors shape):
    assert set(["type", "claim_id", "rule_id", "detail", "sut_section_id"]).issubset(v.keys())
    assert v["savings_category"] == SAVINGS_CATEGORY_SGK_UPLIFT
    assert v["savings_basis"] == SAVINGS_BASIS_SOURCED
