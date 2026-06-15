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
