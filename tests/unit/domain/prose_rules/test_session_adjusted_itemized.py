"""Session-adjusted itemized totals for billing strategy (§2.2.2.B)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ProcedureClaimLine
from src.bilun.domain.prose_rules.session_pricing import (
    compute_session_adjusted_itemized_total,
)

pytestmark = pytest.mark.unit


def _proc(**overrides) -> ProcedureClaimLine:
    base = dict(
        procedure_line_id="PL1",
        claim_id="CLM1",
        patient_id="P1",
        episode_id="E1",
        procedure_date=date(2026, 1, 10),
        procedure_code="610070",
        procedure_name="Primary",
        procedure_category="islem",
        quantity=1,
        unit_price_try=Decimal("1000"),
        billed_amount_try=Decimal("1000"),
        expected_payable_try=Decimal("1000"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=True,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    base.update(overrides)
    return ProcedureClaimLine(**base)


class TestSessionAdjustedItemizedTotal:
    def test_single_line_unchanged(self) -> None:
        lines = [_proc(expected_payable_try=Decimal("500"))]
        total, meta = compute_session_adjusted_itemized_total(lines)
        assert total == 500.0
        assert meta["methodology"] == "claim_lines"

    def test_same_session_secondary_scaled(self) -> None:
        primary = _proc(
            procedure_line_id="PL1",
            procedure_code="610070",
            expected_payable_try=Decimal("1000"),
        )
        secondary = _proc(
            procedure_line_id="PL2",
            procedure_code="610080",
            expected_payable_try=Decimal("1000"),
        )
        raw = 2000.0
        total, meta = compute_session_adjusted_itemized_total(
            [primary, secondary],
            same_incision=True,
        )
        assert meta["sessions_with_adjustment"] == 1
        assert meta["methodology"] == "session_adjusted"
        assert total < raw
        assert total > 1000.0
