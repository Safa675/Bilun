"""§2.2.2.A(5) / §2.2.2.B(3) sessions hold EK-2/B §6 operations only (#261)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ProcedureClaimLine
from src.bilun.domain.prose_rules.session_pricing import compute_session_adjusted_itemized_total
from src.bilun.domain.prose_rules.session_scope import (
    is_session_operation_code,
    session_operation_lines,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "code",
    ["600010", "610131", "615931", "621800", "629999", "P610131", "P603840", "61-0131"],
)
def test_ek2b_section_6_codes_and_their_packages_are_operations(code) -> None:
    assert is_session_operation_code(code) is True


@pytest.mark.parametrize(
    "code",
    [
        "510010",  # Bed.
        "510121",  # Companion.
        "520020",  # ER exam.
        "530350",  # Nebuliser.
        "530100",  # ECG.
        "550160",  # Anaesthesia B group.
        "701450",  # Colonoscopy (§7, non-OR).
        "705430",  # Blood component.
        "801720",  # Chest X-ray.
        "R101450",  # CT angiography.
        "910230",  # Pathology.
        "L107020",  # Lab.
        "P552001",  # ICU day package.
        "401010",  # EK-2/Ç dental range.
        "630000",
        "",
        "P",
    ],
)
def test_other_lines_are_never_session_lines(code) -> None:
    assert is_session_operation_code(code) is False


def _line(line_id: str, code: str, amount: str) -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id=line_id, claim_id="C1", patient_id="P1", episode_id="E1",
        procedure_date=date(2026, 8, 18), procedure_code=code, procedure_name=code,
        procedure_category="islem", quantity=1, unit_price_try=Decimal(amount),
        billed_amount_try=Decimal(amount), expected_payable_try=Decimal(amount),
        is_package_included=False, package_code="", surcharge_applicable=False,
        copay_rate_applicable=False, denial_reason_expected="", rule_trace_expected="",
    )


def test_itemized_total_scales_only_the_secondary_operation() -> None:
    lines = [
        _line("bed", "510010", "222.36"),
        _line("op-2", "615995", "3032.01"),
        _line("anaesthesia", "550230", "1105.31"),
        _line("lab", "L107020", "30.00"),
        _line("op-1", "615931", "3837.32"),
    ]
    assert [line.procedure_line_id for line in session_operation_lines(lines)] == ["op-2", "op-1"]
    total, meta = compute_session_adjusted_itemized_total(lines, cross_specialty=False)
    # 615931 (higher puan) in full, 615995 at 30 % (§2.2.2.A(5)(a)); others at 100 %.
    assert total == pytest.approx(222.36 + 3032.01 * 0.30 + 1105.31 + 30.00 + 3837.32, abs=0.01)
    assert meta["sessions_with_adjustment"] == 1
    assert meta["itemized_lines"] == 5
