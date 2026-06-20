"""Shared money-shaping helper for BILUN domain output.

This consolidates the 15 duplicated ``_money`` helpers that previously did
``round(float(value), 2)`` across billing/ and prose_rules/. Two problems
with that pattern:

1. **DRY violation** — the same 3-line helper was copy-pasted into 15
   modules, drifting in signature (some ``float``, some ``float | None``).
2. **Banker's rounding** — Python's built-in ``round()`` uses round-half-
   to-even (banker's rounding), which has no SUT citation. SGK money math
   should use round-half-up (ROUND_HALF_UP), matching the canonical parser
   idiom in ``claims/parsing/primitives.py`` (``CENT`` / ``ROUND_HALF_UP``).

The helper returns ``Decimal`` (the domain ``Money`` type) rather than
``float`` to avoid float representation error on the shaped value. Callers
that need JSON serialization cast to float at the serialization boundary
(separate concern, audit B-H14).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Union

CENT = Decimal("0.01")

# Accept anything that represents a money value; int/float come from
# upstream parquet/JSON loads, Decimal/str from domain math.
MoneyInput = Union[int, float, Decimal, str]


def quantize_money(value: MoneyInput | None) -> Decimal | None:
    """Quantize a money value to 2 decimal places with ROUND_HALF_UP.

    Returns ``None`` for ``None`` input (the None-safe variant the
    billing_actions helper provided). Non-numeric strings raise
    InvalidOperation, matching the parser idiom.
    """
    if value is None:
        return None
    try:
        return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None


def quantize_money_or_zero(value: MoneyInput | None) -> Decimal:
    """Like :func:`quantize_money` but returns ``Decimal("0.00")`` for None.

    Use this at call sites that previously did ``round(float(value or 0), 2)``
    and must never propagate None into a sum/total.
    """
    result = quantize_money(value)
    return result if result is not None else Decimal("0.00")


def money_round_half_up(value: MoneyInput | None) -> float:
    """Round a money value to 2dp with ROUND_HALF_UP, returning ``float``.

    This is the drop-in replacement for the legacy ``round(float(value), 2)``
    helpers: same ``float`` return type (so it composes with existing float
    arithmetic without Decimal/float mixing errors), but ROUND_HALF_UP
    rounding instead of Python's banker's rounding (round-half-to-even, which
    has no SUT citation). Returns ``0.0`` for ``None`` to match the legacy
    ``round(float(value or 0), 2)`` pattern used at most call sites.

    Decimal-through propagation (returning ``Decimal`` everywhere) is a
    larger architectural change tracked separately (audit B-H14) — it would
    break the float arithmetic at upstream call sites unless ALL money math
    migrates together. This helper delivers the rounding-correctness and DRY
    wins now without that cascade risk.
    """
    return float(quantize_money_or_zero(value))


def money_round_half_up_opt(value: MoneyInput | None) -> float | None:
    """None-preserving variant of :func:`money_round_half_up`.

    Use at call sites that previously did ``round(float(value), 2) if value
    is not None else None`` (e.g. the old billing_actions._money).
    """
    result = quantize_money(value)
    return float(result) if result is not None else None
