"""
src/bilun/domain/utils.py
Utility helpers for the SUT engine.

No dependencies on other src.sut modules.
"""

from __future__ import annotations

import math
from typing import Any


def turkish_lower(text: str) -> str:
    """
    Lowercase a string using Turkish locale rules.

    Python's str.lower() converts I (capital I with dot above, U+0130) to
    'i\u0307' (i + combining dot above -- two codepoints), NOT plain 'i'. This
    breaks substring matching for Turkish material names that start with I
    (e.g. Idrar, Iyot, Implant).

    Turkish lowercasing rules:
      I (U+0130) -> i  (plain ASCII i)
      I (U+0049) -> i  (dotless i, U+0131)
      S -> s, C -> c, O -> o, U -> u, G -> g  (standard .lower() handles these)
    """
    return text.replace("\u0130", "i").replace("I", "\u0131").lower()


def turkish_upper(text: str) -> str:
    """Uppercase a string using Turkish locale rules.

    Replacements run before .upper() so that:
      "i" -> "İ" (dotted capital I, not ASCII "I")
      "ı" -> "I" (ASCII capital I, not "İ")
    Then .upper() handles all remaining characters.

    Note: "İ".upper() == "İ" in Python, so the pre-replacement
    survives the final .upper() call — this is intentional, not accidental.
    """
    return text.replace("i", "\u0130").replace("\u0131", "I").upper()


def _safe_float(val: Any) -> float | None:
    """Convert a value to float, returning None for NaN/None/invalid."""
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


def _safe_str(val: Any) -> str | None:
    """Convert a value to string, returning None for NaN/None."""
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return None
    s = str(val).strip()
    if s.lower() in {"nan", "none", "null", "nat"}:
        return None
    return s if s else None
