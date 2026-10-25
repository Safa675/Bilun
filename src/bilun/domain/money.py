"""Shared money-shaping helper for BILUN domain output.

This consolidates the 15 duplicated ``_money`` helpers that previously did
``round(float(value), 2)`` across billing/ and prose_rules/. Two problems
with that pattern:

1. **DRY violation** — the same 3-line helper was copy-pasted into 15
   modules, drifting in signature (some ``float``, some ``float | None``).
2. **Banker's rounding** — Python's built-in ``round()`` uses round-half-
   to-even (banker's rounding), which has no SUT citation. The other money
   math here uses round-half-up (ROUND_HALF_UP), matching the canonical parser
   idiom in ``claims/parsing/primitives.py`` (``CENT`` / ``ROUND_HALF_UP``);
   no SUT clause names that rounding either.

A list price is different: SUT 2.2.(15) (C000544) takes the EK-2/B, EK-2/C and
EK-2/Ç price as puan × katsayı "yuvarlama işlemi yapılmaksızın virgülden sonra
iki basamak olacak şekilde", i.e. cut at the kuruş, never rounded (#299):
:func:`puan_price_try` (510010: 374.97 × 0.593 = 222.35721 is 222.35).

The helper returns ``Decimal`` (the domain ``Money`` type) rather than
``float`` to avoid float representation error on the shaped value. Callers
that need JSON serialization cast to float at the serialization boundary
(separate concern, audit B-H14).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP
from typing import Union

CENT = Decimal("0.01")
# A puan × katsayı product is exact at nine decimals for every puan written with up to six. The 2020
# and 2021 EK-2/B, EK-2/C and EK-2/Ç lists hold the puan as the float of TL ÷ 0.593 (55.6492411467116
# for 33.00 TL), whose product misses its TL amount by the float's error (below 1e-10 TL): the
# product is taken to nine decimals before the cut, so that error never costs a kuruş.
_PUAN_PRODUCT_PLACES = Decimal("1e-9")

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


def puan_price_try(puan: MoneyInput, katsayi: MoneyInput) -> float:
    """TL price of a puan: puan × katsayı cut at the kuruş, SUT 2.2.(15) (C000544).

    "İşlem puanının belirtilen katsayı ile çarpılması sonucu bulunacak tutar yuvarlama işlemi
    yapılmaksızın virgülden sonra iki basamak olacak şekilde alınır": 374.97 × 0.593 =
    222.35721 is 222.35 and 11,325 × 0.593 = 6,715.725 is 6,715.72 (a rounding gives 222.36 and
    6,715.73). The product is computed on the decimal values as written (a float by its shortest
    repr), so no binary error moves a cut; see ``_PUAN_PRODUCT_PLACES`` for the old lists' floats.
    Use it for every puan × katsayı product (the EK-2/B, EK-2/C and EK-2/Ç builders, the engine's
    own copies); a share or a sum of such prices is other money (:func:`money_round_half_up`).
    """
    product = Decimal(str(puan)) * Decimal(str(katsayi))
    product = product.quantize(_PUAN_PRODUCT_PLACES, rounding=ROUND_HALF_EVEN)
    return float(product.quantize(CENT, rounding=ROUND_DOWN))
