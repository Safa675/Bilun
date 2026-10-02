"""Session-adjusted itemized totals for billing strategy (§2.2.2.B)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from itertools import permutations

import pytest

from src.bilun.domain.claims.models import ProcedureClaimLine
from src.bilun.domain.prose_rules import session_pricing
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


@pytest.fixture
def catalog(monkeypatch):
    """Control catalog membership/ranking while exercising real session rules."""
    def configure(*, ek2c=(), points=None):
        scores = points or {"111111": 30, "222222": 20, "333333": 10}
        monkeypatch.setattr(
            session_pricing, "procedure_annex_membership",
            lambda code, **kwargs: (True, code in ek2c),
        )
        monkeypatch.setattr(
            session_pricing, "_procedure_point_score", lambda code, **kwargs: scores.get(code, 0),
        )

    configure()
    return configure


def _priced(line_id: str, code: str, amount: str, **overrides) -> ProcedureClaimLine:
    return _proc(
        procedure_line_id=line_id,
        procedure_code=code,
        unit_price_try=Decimal(amount),
        billed_amount_try=Decimal(amount),
        expected_payable_try=Decimal(amount),
        **overrides,
    )


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

    @pytest.mark.parametrize("secondary_amount, expected", [("1000", 1300.0), ("100", 1030.0)])
    def test_duplicate_normalized_codes_keep_occurrence_factors(
        self, catalog, secondary_amount, expected,
    ) -> None:
        """Each duplicate keeps its own amount and the first tied occurrence is primary."""
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
            expected_payable_try=Decimal(secondary_amount),
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
            cross_specialty=False,
        )
        assert total == expected
        assert meta["methodology"] == "session_adjusted"

    @pytest.mark.parametrize(
        "package_membership, same_incision, cross_specialty, secondary_factor",
        [
            (False, True, False, Decimal("0.30")),
            (False, False, False, Decimal("0.50")),
            (False, True, True, Decimal("0.55")),
            (False, False, True, Decimal("0.75")),
            (True, True, False, Decimal("0.25")),
            (True, False, False, Decimal("0.50")),
            (True, True, True, Decimal("0.50")),
            (True, False, True, Decimal("0.75")),
        ],
    )
    def test_each_secondary_uses_own_payable(
        self, catalog, package_membership, same_incision, cross_specialty, secondary_factor,
    ) -> None:
        catalog(ek2c=("111111", "222222", "333333") if package_membership else ())
        lines = [
            _priced("primary", "111111", "1000"),
            _priced("secondary", "222222", "100"),
            _priced("third", "333333", "250"),
        ]
        for ordered in permutations(lines):
            total, meta = compute_session_adjusted_itemized_total(
                list(ordered), same_incision=same_incision, cross_specialty=cross_specialty,
            )
            assert total == float(Decimal("1000") + Decimal("350") * secondary_factor)
            assert total <= sum(float(line.expected_payable_try) for line in lines)
            assert meta["itemized_lines"] == 3

    def test_primary_is_selected_by_points_not_price_or_input_order(self, catalog) -> None:
        primary = _priced("primary", "111111", "100")
        secondary = _priced("secondary", "222222", "1000")
        for lines in ([primary, secondary], [secondary, primary]):
            total, _ = compute_session_adjusted_itemized_total(lines, cross_specialty=False)
            assert total == 400.0

    @pytest.mark.parametrize("same_incision, expected", [(True, 1330.0), (False, 1350.0)])
    def test_mixed_membership_keeps_each_full_factor_package_line(
        self, catalog, same_incision, expected,
    ) -> None:
        catalog(ek2c=("111111", "222222"))
        lines = [
            _priced("primary", "111111", "1000"),
            _priced("other-package", "222222", "300"),
            _priced("itemized", "333333", "100"),
        ]
        total, _ = compute_session_adjusted_itemized_total(
            lines, same_incision=same_incision, cross_specialty=False,
        )
        assert total == expected

    def test_mixed_membership_itemized_primary_uses_itemized_fallback(self, catalog) -> None:
        catalog(ek2c=("222222",))
        total, _ = compute_session_adjusted_itemized_total(
            [_priced("primary", "111111", "1000"), _priced("secondary", "222222", "100")],
            cross_specialty=False,
        )
        assert total == 1030.0

    @pytest.mark.parametrize("unpriced", ["0", "-1"])
    def test_billed_fallback_and_quantity_are_whole_line_amounts(self, catalog, unpriced) -> None:
        lines = [
            _priced("primary", "111111", "1000"),
            _proc(
                procedure_line_id="secondary", procedure_code="222222", quantity=3,
                unit_price_try=Decimal("100"), billed_amount_try=Decimal("300"),
                expected_payable_try=Decimal(unpriced),
            ),
        ]
        total, _ = compute_session_adjusted_itemized_total(lines, cross_specialty=False)
        assert total == 1090.0

    def test_positive_payable_wins_over_billed_and_unit_price(self, catalog) -> None:
        lines = [
            _priced("primary", "111111", "1000"),
            _proc(
                procedure_line_id="secondary", procedure_code="222222", quantity=3,
                unit_price_try=Decimal("100"), billed_amount_try=Decimal("300"),
                expected_payable_try=Decimal("240"),
            ),
        ]
        total, _ = compute_session_adjusted_itemized_total(lines, cross_specialty=False)
        assert total == 1072.0

    @pytest.mark.parametrize("invalid_code", ["", " ", "P", "-."])
    @pytest.mark.parametrize("position", [0, 1, 2])
    def test_invalid_codes_do_not_shift_valid_occurrence_factors(
        self, catalog, invalid_code, position,
    ) -> None:
        lines = [_priced("primary", "111111", "1000"), _priced("secondary", "222222", "100")]
        lines.insert(position, _priced("unknown", invalid_code, "70"))
        total, _ = compute_session_adjusted_itemized_total(lines, cross_specialty=False)
        assert total == 1100.0  # invalid-code factor fallback remains 1.0

    def test_rounds_only_after_summing_line_payables(self, catalog) -> None:
        lines = [
            _priced("primary", "111111", "10"),
            _priced("secondary", "222222", "0.01"),
            _priced("third", "333333", "0.01"),
        ]
        total, _ = compute_session_adjusted_itemized_total(
            lines, same_incision=False, cross_specialty=False,
        )
        assert total == 10.01

    @pytest.mark.parametrize("apply_blood_fraction, expected", [(True, 1036.0), (False, 1050.0)])
    def test_blood_cap_still_uses_own_payable(self, catalog, apply_blood_fraction, expected) -> None:
        total, _ = compute_session_adjusted_itemized_total(
            [
                _priced("primary", "111111", "1000"), _priced("blood", "705430", "100"),
                _priced("package", "111111", "5000", procedure_category="paket"),
            ],
            same_incision=False, cross_specialty=False, apply_blood_fraction=apply_blood_fraction,
        )
        assert total == expected

    def test_separate_sessions_and_exclusions_are_preserved(self, catalog) -> None:
        lines = [
            _priced("primary", "111111", "1000"),
            _priced("secondary", "222222", "100"),
            _priced("tomorrow", "333333", "200", procedure_date=date(2026, 1, 11)),
            _priced("package", "111111", "5000", procedure_category="paket"),
            _priced("included", "111111", "6000", is_package_included=True),
            _priced("zero", "111111", "0"),
        ]
        total, meta = compute_session_adjusted_itemized_total(lines, cross_specialty=False)
        assert total == 1230.0
        assert meta["itemized_lines"] == 3
        assert meta["sessions_with_adjustment"] == 1
