"""Tests for clinical lab capture gap detection."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import polars as pl
import pytest

pytestmark = pytest.mark.unit


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


def _lab_claim_line(code: str, billed: str = "10.00") -> _MockProcedureClaimLine:
    return _MockProcedureClaimLine(
        procedure_line_id=f"L-{code}",
        claim_id="C1",
        patient_id="P1",
        episode_id="V1",
        procedure_date="2024-01-01",
        procedure_code=code,
        procedure_name=code,
        procedure_category="laboratuvar",
        quantity=1,
        unit_price_try=Decimal(billed),
        billed_amount_try=Decimal(billed),
        expected_payable_try=Decimal("0"),
    )


def _lab_df(rows: list[dict[str, Any]]) -> pl.DataFrame:
    return pl.DataFrame(
        rows,
        schema={
            "patient_id": pl.Utf8,
            "visit_id": pl.Utf8,
            "test_name": pl.Utf8,
        },
    )


def test_clinical_lab_missing_from_claim_is_flagged() -> None:
    from src.bilun.domain.prose_rules.lab_capture_gap import detect_lab_capture_gaps

    lab_df = _lab_df(
        [
            {"patient_id": "P1", "visit_id": "V1", "test_name": "l112180"},
        ]
    )
    gaps = detect_lab_capture_gaps(lab_df, [], "V1", service_date="2024-01-01")
    assert len(gaps) == 1
    assert gaps[0]["procedure_code"] == "L112180"
    assert gaps[0]["actual_billed_try"] == 0.0
    assert gaps[0]["included_in_sgk_total"] is False


def test_duplicate_clinical_results_do_not_create_duplicate_gaps() -> None:
    from src.bilun.domain.prose_rules.lab_capture_gap import detect_lab_capture_gaps

    lab_df = _lab_df(
        [
            {"patient_id": "P1", "visit_id": "V1", "test_name": "l112180"},
            {"patient_id": "P1", "visit_id": "V1", "test_name": "l112180"},
            {"patient_id": "P1", "visit_id": "V1", "test_name": "l112180"},
            {"patient_id": "P1", "visit_id": "V1", "test_name": "l112180"},
        ]
    )
    gaps = detect_lab_capture_gaps(lab_df, [], "V1", service_date="2024-01-01")
    assert len(gaps) == 1


def test_billed_lab_line_suppresses_gap() -> None:
    from src.bilun.domain.prose_rules.lab_capture_gap import detect_lab_capture_gaps

    lab_df = _lab_df(
        [
            {"patient_id": "P1", "visit_id": "V1", "test_name": "l112180"},
        ]
    )
    gaps = detect_lab_capture_gaps(
        lab_df,
        [_lab_claim_line("L112180", billed="12.84")],
        "V1",
        service_date="2024-01-01",
    )
    assert len(gaps) == 0


def test_zero_billed_line_does_not_suppress_gap() -> None:
    from src.bilun.domain.prose_rules.lab_capture_gap import detect_lab_capture_gaps

    lab_df = _lab_df(
        [
            {"patient_id": "P1", "visit_id": "V1", "test_name": "l112180"},
        ]
    )
    gaps = detect_lab_capture_gaps(
        lab_df,
        [_lab_claim_line("L112180", billed="0.00")],
        "V1",
        service_date="2024-01-01",
    )
    assert len(gaps) == 1


def test_only_laboratuvar_category_suppresses_gap() -> None:
    from src.bilun.domain.prose_rules.lab_capture_gap import detect_lab_capture_gaps

    lab_df = _lab_df(
        [
            {"patient_id": "P1", "visit_id": "V1", "test_name": "l112180"},
        ]
    )
    non_lab_line = _MockProcedureClaimLine(
        procedure_line_id="P-1",
        claim_id="C1",
        patient_id="P1",
        episode_id="V1",
        procedure_date="2024-01-01",
        procedure_code="L112180",
        procedure_name="Kortizol",
        procedure_category="muayene",
        quantity=1,
        unit_price_try=Decimal("12.84"),
        billed_amount_try=Decimal("12.84"),
        expected_payable_try=Decimal("0"),
    )
    gaps = detect_lab_capture_gaps(lab_df, [non_lab_line], "V1", service_date="2024-01-01")
    assert len(gaps) == 1


@pytest.mark.parametrize("truncated_code", ["L1070", "L100", "L10702", "L1018"])
def test_truncated_lab_code_is_not_priced_via_prefix_search(truncated_code: str) -> None:
    """#280: truncated lab codes must not price as another test via catalog prefix_search."""
    from src.bilun.domain.prose_rules.lab_capture_gap import (
        _resolve_lab_list_price,
        detect_lab_capture_gaps,
    )

    assert _resolve_lab_list_price(truncated_code, service_date="2026-10-15") == (None, "")
    lab_df = _lab_df([{"patient_id": "P1", "visit_id": "V1", "test_name": truncated_code}])
    assert detect_lab_capture_gaps(lab_df, [], "V1", service_date="2026-10-15") == []


def test_exact_lab_code_l107020_still_prices_correctly_on_2026_10_15() -> None:
    """#280: exact 7-character L-codes continue to resolve their EK-2B list price."""
    from src.bilun.domain.prose_rules.lab_capture_gap import (
        _resolve_lab_list_price,
        detect_lab_capture_gaps,
    )

    price, method = _resolve_lab_list_price("L107020", service_date="2026-10-15")
    assert price == pytest.approx(19.73, abs=0.01)
    assert method == "ek2b_list_price"

    lab_df = _lab_df([{"patient_id": "P1", "visit_id": "V1", "test_name": "L107020"}])
    gaps = detect_lab_capture_gaps(lab_df, [], "V1", service_date="2026-10-15")
    assert len(gaps) == 1
    assert gaps[0]["procedure_code"] == "L107020"
    assert gaps[0]["list_price_try"] == 19.73
    assert gaps[0]["recoverable_gap_try"] == 19.73
    assert gaps[0]["price_methodology"] == "ek2b_list_price"

