"""W6: JSON-driven factor sourcing for ``compute_session_point_factors``.

These tests verify the §2.2.2.B refactor that makes
``data/gazette/prose_rules/session_pricing_2_2_2_B.json`` the single source of
truth for the factor *values* applied to same-session multi-procedure claims.

The four rules in the JSON are:

- ``2.2.2.B.a`` — same_session + same_incision + all_in_ek2c → other @ 0.25
- ``2.2.2.B.b`` — same_session + diff incision + all_in_ek2c → other @ 0.5
- ``2.2.2.B.c`` — same_session + same_incision + mixed ek2c/ek2b → ek2b @ 0.3
- ``2.2.2.B.ç`` — same_session + diff incision + mixed ek2c/ek2b → ek2b @ 0.5

Covered:
1. JSON-driven factors for all four rules (values read from the JSON action).
2. Hardcoded-literal fallback when the JSON loader returns no rules.
3. cross_specialty +0.25 uplift (capped at 1.0) for both branches.
4. ``_match_session_pricing_rule`` precedence (mixed before all_in_ek2c).

Catalog membership (which annex a code belongs to) is stubbed so each branch
is exercised deterministically — these tests assert factor *sourcing*, not the
catalog data itself.
"""

from __future__ import annotations

import pytest

from src.bilun.domain.prose_rules import session_pricing
from src.bilun.domain.prose_rules.session_pricing import (
    _factor_with_uplift,
    _match_session_pricing_rule,
    compute_session_point_factors,
    load_session_pricing_rules,
)

pytestmark = pytest.mark.unit

# Codes are arbitrary; membership is stubbed per-test so the branch taken is
# fully controlled regardless of catalog state.
_EK2C_ONLY_A = "100100"
_EK2C_ONLY_B = "100200"
_EK2B_ONLY = "200100"


def _stub_membership(monkeypatch, mapping: dict[str, tuple[bool, bool]]):
    """Stub ``procedure_annex_membership`` to return (in_ek2b, in_ek2c)."""

    def fake(code: str, **kwargs):
        return mapping.get(code, (False, False))

    monkeypatch.setattr(
        session_pricing, "procedure_annex_membership", fake, raising=True
    )


def _clear_loader_cache() -> None:
    """Reset the lru_cache on the JSON loader (and its backing _load)."""
    load_session_pricing_rules.cache_clear()
    session_pricing._load_session_rules.cache_clear()


class TestLoadSessionPricingRules:
    def test_loads_four_rules(self) -> None:
        _clear_loader_cache()
        rules = load_session_pricing_rules()
        assert len(rules) == 4
        ids = {r["rule_id"] for r in rules}
        assert ids == {"2.2.2.B.a", "2.2.2.B.b", "2.2.2.B.c", "2.2.2.B.ç"}

    def test_returns_empty_list_when_loader_fails(self, monkeypatch) -> None:
        _clear_loader_cache()

        def boom():
            raise OSError("file gone")

        monkeypatch.setattr(
            session_pricing, "_load_session_rules", boom, raising=True
        )
        assert load_session_pricing_rules() == []


class TestMatchSessionPricingRule:
    def setup_method(self) -> None:
        _clear_loader_cache()

    def test_all_in_ek2c_same_incision_matches_a(self) -> None:
        rule = _match_session_pricing_rule(
            same_incision=True, all_in_ek2c=True, mixed_ek2c_ek2b=False
        )
        assert rule is not None
        assert rule["rule_id"] == "2.2.2.B.a"

    def test_all_in_ek2c_diff_incision_matches_b(self) -> None:
        rule = _match_session_pricing_rule(
            same_incision=False, all_in_ek2c=True, mixed_ek2c_ek2b=False
        )
        assert rule is not None
        assert rule["rule_id"] == "2.2.2.B.b"

    def test_mixed_same_incision_matches_c_before_a(self) -> None:
        # mixed flags are both true here; .c must win over .a despite
        # all_in_ek2c also being set (precedence mirrors the if/elif order).
        rule = _match_session_pricing_rule(
            same_incision=True, all_in_ek2c=True, mixed_ek2c_ek2b=True
        )
        assert rule is not None
        assert rule["rule_id"] == "2.2.2.B.c"

    def test_mixed_diff_incision_matches_cedilla(self) -> None:
        rule = _match_session_pricing_rule(
            same_incision=False, all_in_ek2c=True, mixed_ek2c_ek2b=True
        )
        assert rule is not None
        assert rule["rule_id"] == "2.2.2.B.ç"

    def test_no_rule_matches_returns_none(self, monkeypatch) -> None:
        # Neither flag set → no rule applies.
        rule = _match_session_pricing_rule(
            same_incision=True, all_in_ek2c=False, mixed_ek2c_ek2b=False
        )
        assert rule is None


class TestFactorWithUplift:
    def test_no_uplift_returns_base(self) -> None:
        assert _factor_with_uplift(0.25, cross_specialty=False) == 0.25
        assert _factor_with_uplift(0.5, cross_specialty=False) == 0.5

    def test_uplift_adds_quarter(self) -> None:
        assert _factor_with_uplift(0.25, cross_specialty=True) == 0.5
        assert _factor_with_uplift(0.5, cross_specialty=True) == 0.75

    def test_uplift_capped_at_one(self) -> None:
        assert _factor_with_uplift(0.9, cross_specialty=True) == 1.0
        assert _factor_with_uplift(1.0, cross_specialty=True) == 1.0


class TestJsonDrivenFactors:
    """Factor VALUES are read from the JSON action for each matched rule."""

    def setup_method(self) -> None:
        _clear_loader_cache()

    def test_rule_a_other_factor_from_json(self, monkeypatch) -> None:
        _stub_membership(
            monkeypatch,
            {_EK2C_ONLY_A: (False, True), _EK2C_ONLY_B: (False, True)},
        )
        result = compute_session_point_factors(
            [_EK2C_ONLY_A, _EK2C_ONLY_B], same_incision=True
        )
        assert result.rule_id == "2.2.2.B.a"
        # primary @ 1.0, other @ 0.25 (JSON value, not a literal)
        non_primary = [f for f in result.factors if not f.is_primary]
        assert len(non_primary) == 1
        assert non_primary[0].point_factor == pytest.approx(0.25)

    def test_rule_b_other_factor_from_json(self, monkeypatch) -> None:
        _stub_membership(
            monkeypatch,
            {_EK2C_ONLY_A: (False, True), _EK2C_ONLY_B: (False, True)},
        )
        result = compute_session_point_factors(
            [_EK2C_ONLY_A, _EK2C_ONLY_B], same_incision=False
        )
        assert result.rule_id == "2.2.2.B.b"
        non_primary = [f for f in result.factors if not f.is_primary]
        assert len(non_primary) == 1
        assert non_primary[0].point_factor == pytest.approx(0.5)

    def test_rule_c_ek2b_factor_from_json(self, monkeypatch) -> None:
        # ek2c code is the primary (higher points via the score fn); ek2b-only
        # code receives the JSON ek2b_procedure_factor.
        _stub_membership(
            monkeypatch,
            {_EK2C_ONLY_A: (False, True), _EK2B_ONLY: (True, False)},
        )
        result = compute_session_point_factors(
            [_EK2C_ONLY_A, _EK2B_ONLY], same_incision=True
        )
        assert result.rule_id == "2.2.2.B.c"
        ek2b_factors = [
            f
            for f in result.factors
            if f.procedure_code == _EK2B_ONLY
        ]
        assert len(ek2b_factors) == 1
        assert ek2b_factors[0].point_factor == pytest.approx(0.3)

    def test_rule_cedilla_ek2b_factor_from_json(self, monkeypatch) -> None:
        _stub_membership(
            monkeypatch,
            {_EK2C_ONLY_A: (False, True), _EK2B_ONLY: (True, False)},
        )
        result = compute_session_point_factors(
            [_EK2C_ONLY_A, _EK2B_ONLY], same_incision=False
        )
        assert result.rule_id == "2.2.2.B.ç"
        ek2b_factors = [
            f
            for f in result.factors
            if f.procedure_code == _EK2B_ONLY
        ]
        assert len(ek2b_factors) == 1
        assert ek2b_factors[0].point_factor == pytest.approx(0.5)


class TestCrossSpecialtyUplift:
    """The +0.25 cross-specialty uplift applies (capped at 1.0) on top of the
    JSON-sourced base for BOTH the all_in_ek2c and mixed branches."""

    def setup_method(self) -> None:
        _clear_loader_cache()

    def test_uplift_all_in_ek2c_same_incision(self, monkeypatch) -> None:
        _stub_membership(
            monkeypatch,
            {_EK2C_ONLY_A: (False, True), _EK2C_ONLY_B: (False, True)},
        )
        result = compute_session_point_factors(
            [_EK2C_ONLY_A, _EK2C_ONLY_B],
            same_incision=True,
            cross_specialty=True,
        )
        # base 0.25 + 0.25 = 0.5
        non_primary = [f for f in result.factors if not f.is_primary]
        assert non_primary[0].point_factor == pytest.approx(0.5)

    def test_uplift_all_in_ek2c_diff_incision(self, monkeypatch) -> None:
        _stub_membership(
            monkeypatch,
            {_EK2C_ONLY_A: (False, True), _EK2C_ONLY_B: (False, True)},
        )
        result = compute_session_point_factors(
            [_EK2C_ONLY_A, _EK2C_ONLY_B],
            same_incision=False,
            cross_specialty=True,
        )
        # base 0.5 + 0.25 = 0.75
        non_primary = [f for f in result.factors if not f.is_primary]
        assert non_primary[0].point_factor == pytest.approx(0.75)

    def test_uplift_mixed_same_incision(self, monkeypatch) -> None:
        _stub_membership(
            monkeypatch,
            {_EK2C_ONLY_A: (False, True), _EK2B_ONLY: (True, False)},
        )
        result = compute_session_point_factors(
            [_EK2C_ONLY_A, _EK2B_ONLY],
            same_incision=True,
            cross_specialty=True,
        )
        # base 0.3 + 0.25 = 0.55
        ek2b = [f for f in result.factors if f.procedure_code == _EK2B_ONLY]
        assert ek2b[0].point_factor == pytest.approx(0.55)


class TestFallbackWhenJsonMissing:
    """When the JSON loader yields no rules, the original hardcoded literals
    (0.25 / 0.5 / 0.3) must still produce identical output."""

    def _force_empty_rules(self, monkeypatch) -> None:
        _clear_loader_cache()
        monkeypatch.setattr(
            session_pricing,
            "load_session_pricing_rules",
            lambda: [],
            raising=True,
        )

    def test_fallback_all_in_ek2c_same_incision(self, monkeypatch) -> None:
        self._force_empty_rules(monkeypatch)
        _stub_membership(
            monkeypatch,
            {_EK2C_ONLY_A: (False, True), _EK2C_ONLY_B: (False, True)},
        )
        result = compute_session_point_factors(
            [_EK2C_ONLY_A, _EK2C_ONLY_B], same_incision=True
        )
        # rule_id falls back to the hardcoded id; factor to 0.25
        assert result.rule_id == "2.2.2.B.a"
        non_primary = [f for f in result.factors if not f.is_primary]
        assert non_primary[0].point_factor == pytest.approx(0.25)

    def test_fallback_all_in_ek2c_diff_incision(self, monkeypatch) -> None:
        self._force_empty_rules(monkeypatch)
        _stub_membership(
            monkeypatch,
            {_EK2C_ONLY_A: (False, True), _EK2C_ONLY_B: (False, True)},
        )
        result = compute_session_point_factors(
            [_EK2C_ONLY_A, _EK2C_ONLY_B], same_incision=False
        )
        assert result.rule_id == "2.2.2.B.b"
        non_primary = [f for f in result.factors if not f.is_primary]
        assert non_primary[0].point_factor == pytest.approx(0.5)

    def test_fallback_mixed_same_incision(self, monkeypatch) -> None:
        self._force_empty_rules(monkeypatch)
        _stub_membership(
            monkeypatch,
            {_EK2C_ONLY_A: (False, True), _EK2B_ONLY: (True, False)},
        )
        result = compute_session_point_factors(
            [_EK2C_ONLY_A, _EK2B_ONLY], same_incision=True
        )
        assert result.rule_id == "2.2.2.B.c"
        ek2b = [f for f in result.factors if f.procedure_code == _EK2B_ONLY]
        assert ek2b[0].point_factor == pytest.approx(0.3)

    def test_fallback_mixed_diff_incision(self, monkeypatch) -> None:
        self._force_empty_rules(monkeypatch)
        _stub_membership(
            monkeypatch,
            {_EK2C_ONLY_A: (False, True), _EK2B_ONLY: (True, False)},
        )
        result = compute_session_point_factors(
            [_EK2C_ONLY_A, _EK2B_ONLY], same_incision=False
        )
        assert result.rule_id == "2.2.2.B.ç"
        ek2b = [f for f in result.factors if f.procedure_code == _EK2B_ONLY]
        assert ek2b[0].point_factor == pytest.approx(0.5)
