"""Tests for the claim-line based lab optimizer.

Session-fraction / seans kesir oranı rules are intentionally NOT applied to lab
tests because SUT §2.2.2.A(5) / §2.2.2.B refer to surgical/medical procedures
with "kesi" (incision), not laboratory "tetkikler".
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import polars as pl
import pytest

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[4]
# EK-2B prices in force on this day: L107020 19.72, L102820 26.33, L103120 5.88 TL.
_DAY = "2026-03-01"


@dataclass(frozen=True)
class _MockProcedureClaimLine:
    procedure_line_id: str
    claim_id: str
    patient_id: str
    episode_id: str
    procedure_date: str
    procedure_code: str
    procedure_name: str
    procedure_category: str
    quantity: int
    unit_price_try: Decimal
    billed_amount_try: Decimal
    expected_payable_try: Decimal
    is_package_included: bool = False
    package_code: str = ""
    surcharge_applicable: bool = False
    copay_rate_applicable: bool = False
    denial_reason_expected: str = ""
    rule_trace_expected: str = ""
    lab_result_id: str = ""
    lab_billing_status: str = ""
    procedure_specialty_code: str = ""


@dataclass(frozen=True)
class _MockClaimHeader:
    claim_id: str
    patient_id: str
    episode_id: str
    claim_start_date: str = ""
    admission_date: str | None = None


@dataclass(frozen=True)
class _MockPatientClaimContext:
    patient_id: str
    claims: tuple[Any, ...]
    procedure_lines: tuple[Any, ...]
    material_lines: tuple[Any, ...] = ()
    drug_lines: tuple[Any, ...] = ()
    diagnoses: tuple[Any, ...] = ()
    performed_procedure_lines: tuple[Any, ...] = ()
    medula_rejection_events: tuple[Any, ...] = ()


def _lab_line(
    *,
    code: str,
    name: str,
    billed: str,
    episode: str = "V1",
    claim: str = "C1",
    day: str = "2024-01-01",
) -> _MockProcedureClaimLine:
    return _MockProcedureClaimLine(
        procedure_line_id=f"L-{code}",
        claim_id=claim,
        patient_id="P1",
        episode_id=episode,
        procedure_date=day,
        procedure_code=code,
        procedure_name=name,
        procedure_category="laboratuvar",
        quantity=1,
        unit_price_try=Decimal(billed),
        billed_amount_try=Decimal(billed),
        expected_payable_try=Decimal("0"),
    )


def test_one_billed_lab_per_visit_no_flag() -> None:
    from src.bilun.domain.billing.claim_lab import _optimize_lab_billing_from_claims

    ctx = _MockPatientClaimContext(
        patient_id="P1",
        claims=(_MockClaimHeader("C1", "P1", "V1"),),
        procedure_lines=(_lab_line(code="L112180", name="Kortizol", billed="12.84"),),
    )
    result = _optimize_lab_billing_from_claims(ctx)
    assert result.hemogram_bundling_savings == 0.0
    assert result.session_fraction_savings == 0.0
    assert not result.flagged_tests


def test_multiple_distinct_labs_same_visit_no_session_fraction_flag() -> None:
    """Session-fraction rules do not apply to lab tests."""
    from src.bilun.domain.billing.claim_lab import _optimize_lab_billing_from_claims

    ctx = _MockPatientClaimContext(
        patient_id="P1",
        claims=(_MockClaimHeader("C1", "P1", "V1"),),
        procedure_lines=(
            _lab_line(code="L112180", name="Kortizol", billed="12.84"),
            _lab_line(code="L120000", name="İdrar", billed="7.89"),
            _lab_line(code="L103430", name="HLA", billed="888.97"),
        ),
    )
    result = _optimize_lab_billing_from_claims(ctx)
    assert result.session_fraction_savings == 0.0
    assert not any(
        f["flag_type"] == "session_fraction_overbilling" for f in result.flagged_tests
    )


def test_hemogram_bundling_on_claim_lines() -> None:
    from src.bilun.domain.billing.claim_lab import _optimize_lab_billing_from_claims

    ctx = _MockPatientClaimContext(
        patient_id="P1",
        claims=(_MockClaimHeader("C1", "P1", "V1"),),
        procedure_lines=(
            _lab_line(code="L101010", name="Hemoglobin", billed="10.00"),
            _lab_line(code="L101020", name="Hematokrit", billed="10.00"),
        ),
    )
    result = _optimize_lab_billing_from_claims(ctx)
    assert result.hemogram_bundling_savings > 0.0
    assert any(f["flag_type"] == "hemogram_unbundling" for f in result.flagged_tests)


def test_no_hemogram_bundling_for_single_cbc_line() -> None:
    from src.bilun.domain.billing.claim_lab import _optimize_lab_billing_from_claims

    ctx = _MockPatientClaimContext(
        patient_id="P1",
        claims=(_MockClaimHeader("C1", "P1", "V1"),),
        procedure_lines=(_lab_line(code="L107020", name="Tam Kan Sayımı (Hemogram)", billed="19.72"),),
    )
    result = _optimize_lab_billing_from_claims(ctx)
    assert result.hemogram_bundling_savings == 0.0
    assert not result.flagged_tests


_HEMOGRAM = {"code": "L107020", "name": "Tam Kan Sayımı (Hemogram)", "billed": "19.72"}
_MANUAL_HCT = {"code": "L103120", "name": "Hematokrit (Manuel)", "billed": "5.88"}
_HBA1C = {"code": "L102820", "name": "Glike hemoglobin (Hb A1c)", "billed": "26.33"}


def _one_date(*lines: dict[str, str]) -> _MockPatientClaimContext:
    return _MockPatientClaimContext(
        patient_id="P1",
        claims=(_MockClaimHeader("C1", "P1", "V1"),),
        procedure_lines=tuple(_lab_line(day=_DAY, **line) for line in lines),
    )


def test_hemogram_with_hba1c_on_one_date_is_not_unbundling() -> None:
    """#270: "Glike hemoglobin (Hb A1c)" contains "hemoglobin" but is not a CBC test."""
    from src.bilun.domain.billing.claim_lab import _optimize_lab_billing_from_claims

    result = _optimize_lab_billing_from_claims(_one_date(_HEMOGRAM, _HBA1C))
    assert result.hemogram_bundling_savings == 0.0
    assert result.flagged_tests == []


@pytest.mark.parametrize(
    ("second", "savings"),
    [(_HEMOGRAM, 19.72), (_MANUAL_HCT, 5.88)],
    ids=["two_hemograms", "hemogram_and_manual_hematocrit"],
)
def test_coded_cbc_lines_on_one_date_are_unbundling(second: dict[str, str], savings: float) -> None:
    """Savings stay billed total minus one dated L107020 price."""
    from src.bilun.domain.billing.claim_lab import _optimize_lab_billing_from_claims

    result = _optimize_lab_billing_from_claims(_one_date(_HEMOGRAM, second))
    assert result.hemogram_bundling_savings == savings
    flags = [(f["flag_type"], f["gazette_price"], f["savings_try"]) for f in result.flagged_tests]
    assert flags == [("hemogram_unbundling", 19.72, savings)]


@pytest.mark.parametrize(
    ("name", "is_cbc"),
    [
        ("Hemoglobin", True),
        ("HEMOGLOBİN", True),
        ("HEMOGLOBIN", True),
        (" lökosit ", True),
        ("LÖKOSİT", True),
        ("Glike hemoglobin (Hb A1c)", False),
        ("Lökosit sayımı, manuel (Vücut sıvıları)", False),
        (None, False),
    ],
)
def test_cbc_parameter_names_match_exactly_after_turkish_case_folding(
    name: str | None, is_cbc: bool
) -> None:
    from src.bilun.domain.billing.claim_lab import _is_hemogram_subtest_line

    line = SimpleNamespace(procedure_code="", procedure_name=name)
    assert _is_hemogram_subtest_line(line) is is_cbc


def test_only_hemogram_and_manual_hematocrit_codes_are_cbc_lines() -> None:
    """#270: of the EK-2B L-codes in force on 2026-03-01, only two are CBC lines."""
    from src.bilun.domain.billing.claim_lab import _is_hemogram_subtest_line

    in_force = (
        pl.scan_parquet(_REPO / "data/gazette/curated/ek2b_catalog_history.parquet")
        .filter(
            pl.col("code").str.starts_with("L")
            & (pl.col("valid_from") <= _DAY)
            & (pl.col("valid_to").is_null() | (pl.col("valid_to") >= _DAY))
        )
        .select("code", "name")
        .collect()
    )
    # The classifier reads one claim line; the catalog slicing around it is vectorised.
    is_cbc = pl.struct("code", "name").map_elements(
        lambda row: _is_hemogram_subtest_line(
            SimpleNamespace(procedure_code=row["code"], procedure_name=row["name"])
        ),
        return_dtype=pl.Boolean,
    )
    assert in_force.height > 1000
    assert in_force.filter(is_cbc)["code"].sort().to_list() == ["L103120", "L107020"]
