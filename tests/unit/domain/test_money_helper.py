"""Regression tests for the shared money helper (Dalga 5 / Decimal cluster).

Guards the consolidated money-shaping helper that replaced 15 duplicated
``round(float(value), 2)`` helpers across billing/ and prose_rules/.

Key properties pinned:
- ROUND_HALF_UP rounding (not Python's banker's rounding round-half-to-even)
- float return type (composes with existing float arithmetic; Decimal-through
  propagation is a separate B-H14 task)
- None handling for the opt variant
- No local ``_money`` defs remain in the migrated modules
"""

from __future__ import annotations

from decimal import Decimal

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Rounding correctness: ROUND_HALF_UP vs banker's rounding
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        # The canonical banker's-rounding failure case: 2.675 rounds to 2.67
        # under float round-half-to-even, but 2.68 under ROUND_HALF_UP (SUT).
        (2.675, 2.68),
        (0.125, 0.13),
        (0.135, 0.14),
        # .xx5 that happens to be even on both sides — still half-up
        (1.005, 1.01),
        # whole numbers and clean values stay clean
        (100.0, 100.0),
        (0, 0.0),
        (1234.5, 1234.5),
        # negative money (refunds / overbilling corrections)
        (-2.675, -2.68),
    ],
)
def test_money_round_half_up_not_bankers(value: float, expected: float) -> None:
    from src.bilun.domain.money import money_round_half_up

    got = money_round_half_up(value)
    assert got == pytest.approx(expected, abs=0.001), (
        f"{value} should round to {expected} under ROUND_HALF_UP, got {got}"
    )


def test_money_round_half_up_differs_from_builtin_round_on_2675() -> None:
    """The exact case the fix was made for: builtin round(2.675, 2) == 2.67."""
    from src.bilun.domain.money import money_round_half_up

    assert round(2.675, 2) == 2.67  # banker's rounding (the bug)
    assert money_round_half_up(2.675) == pytest.approx(2.68, abs=0.001)  # SUT-correct


# ---------------------------------------------------------------------------
# Input type acceptance
# ---------------------------------------------------------------------------


def test_money_accepts_int_float_decimal_str() -> None:
    from src.bilun.domain.money import money_round_half_up

    assert money_round_half_up(100) == 100.0
    assert money_round_half_up(99.999) == 100.0
    assert money_round_half_up(Decimal("50.005")) == pytest.approx(50.01, abs=0.001)
    assert money_round_half_up("50.005") == pytest.approx(50.01, abs=0.001)


def test_money_none_input_returns_zero() -> None:
    """money_round_half_up (non-opt) returns 0.0 for None — matches legacy
    `round(float(value or 0), 2)` pattern used at most call sites."""
    from src.bilun.domain.money import money_round_half_up

    assert money_round_half_up(None) == 0.0


def test_money_opt_preserves_none() -> None:
    """The opt variant returns None for None input (billing_actions used this)."""
    from src.bilun.domain.money import money_round_half_up_opt

    assert money_round_half_up_opt(None) is None
    assert money_round_half_up_opt(99.999) == 100.0


def test_money_quantize_money_returns_decimal() -> None:
    """The underlying Decimal-returning helper (for future Decimal-through paths)."""
    from src.bilun.domain.money import quantize_money

    assert quantize_money("2.675") == Decimal("2.68")
    assert quantize_money(None) is None


# ---------------------------------------------------------------------------
# DRY guard: no local _money defs remain in the migrated modules
# ---------------------------------------------------------------------------


def test_no_local_money_defs_remain_in_billing_modules() -> None:
    """Static guard: billing/ modules must import the shared helper, not define _money."""
    import re
    from pathlib import Path

    billing_dir = Path("src/bilun/domain/billing")
    prose_dir = Path("src/bilun/domain/prose_rules")
    optimization_dir = Path("src/bilun/domain/optimization")
    scripts_dir = Path("scripts/synthetic")
    offenders = []
    for d in (billing_dir, prose_dir, optimization_dir, scripts_dir):
        for py in d.glob("*.py"):
            src = py.read_text(encoding="utf-8")
            if re.search(r"^def _money\(", src, re.MULTILINE):
                offenders.append(str(py))
    assert not offenders, (
        f"local _money defs still present (must use shared helper): {offenders}"
    )


def test_migrated_modules_import_shared_helper() -> None:
    """Static guard: each formerly-duplicated module must import money_round_half_up."""
    from pathlib import Path

    files = [
        "src/bilun/domain/billing/claim_strategy.py",
        "src/bilun/domain/billing/billing_actions.py",
        "src/bilun/domain/billing/claim_audit_exposure.py",
        "src/bilun/domain/billing/claim_drg_uplift.py",
        "src/bilun/domain/prose_rules/session_uplift.py",
        "src/bilun/domain/prose_rules/drg_unbundling.py",
        "src/bilun/domain/prose_rules/material_uplift.py",
        "src/bilun/domain/prose_rules/procedure_addon_uplift.py",
        "src/bilun/domain/prose_rules/procedure_capture_gap.py",
        "src/bilun/domain/prose_rules/care_setting_review.py",
        "src/bilun/domain/prose_rules/session_pricing.py",
        "src/bilun/domain/prose_rules/blood_uplift.py",
        "src/bilun/domain/prose_rules/drg_package_adequacy.py",
    ]
    missing = []
    for f in files:
        src = Path(f).read_text(encoding="utf-8")
        if "money_round_half_up" not in src and "money_round_half_up_opt" not in src:
            missing.append(f)
    assert not missing, f"modules not importing the shared helper: {missing}"
