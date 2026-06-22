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

    def test_duplicate_normalized_code_collision_does_not_break_total(self) -> None:
        """B-H7 regression: two codes that normalize to the same key
        (e.g. P701450 and 70-1450 both → 701450) cause a factor-map dict
        collision — the primary factor is silently dropped.  The total
        must still be correct because primary identification downstream
        is procedure_line_id-based, not factor-map-based, and the default
        primary_factor is 1.0 which matches the actual primary factor.
        If any of those masking defaults change, this test will catch the
        regression.
        """
        from src.bilun.domain.prose_rules.catalog_membership import (
            normalize_procedure_code,
        )
        from src.bilun.domain.prose_rules.session_pricing import (
            compute_session_point_factors,
        )

        primary = _proc(
            procedure_line_id="PL_A",
            procedure_code="P701450",
            expected_payable_try=Decimal("1000"),
        )
        secondary = _proc(
            procedure_line_id="PL_B",
            procedure_code="70-1450",
            expected_payable_try=Decimal("1000"),
        )

        assert normalize_procedure_code("P701450") == normalize_procedure_code(
            "70-1450"
        ), "fixture must produce a collision"

        session = compute_session_point_factors(
            ["P701450", "70-1450"], same_incision=True
        )
        assert len(session.factors) == 2

        factors_map = {
            normalize_procedure_code(f.procedure_code): f for f in session.factors
        }
        assert len(factors_map) == 1, "factor-map collision expected"

        total, meta = compute_session_adjusted_itemized_total(
            [primary, secondary],
            same_incision=True,
        )
        assert total == 1300.0, (
            f"collision must not change the total; got {total}"
        )
        assert meta["methodology"] == "session_adjusted"
