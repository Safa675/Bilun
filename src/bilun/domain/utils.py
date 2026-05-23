"""
src/bilun/domain/utils.py
Utility helpers for the SUT engine.

No dependencies on other src.sut modules.
"""

from __future__ import annotations

import math
import re
from difflib import SequenceMatcher
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


def fuzzy_match_name(
    needle_lower: str,
    candidates: list[tuple[str, Any]],
    *,
    threshold: float = 0.85,
) -> tuple[str, Any] | None:
    """Fuzzy-match a name against a list of (lowered_name, item) tuples.

    Returns the best (name, item) with similarity >= threshold, or None.
    Uses SequenceMatcher for typo-tolerant matching (e.g. 1-2 char differences).

    Two-level matching:
      1. Full-name comparison against each candidate name.
      2. Token-level: splits candidate name into words and compares each
         against needle (handles e.g. 'enjektör' matching
         'enjektör 50cc (beslenme amaçlı)').
    """
    _TOKEN_SPLIT_RE = re.compile(r"[\s\(\)\-/,.;:]+")

    best_ratio = 0.0
    best_match: tuple[str, Any] | None = None

    for cand_name, cand_item in candidates:
        # Level 1: full-name comparison
        ratio = SequenceMatcher(None, needle_lower, cand_name).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = (cand_name, cand_item)

        # Level 2: token-level comparison
        tokens = [t for t in _TOKEN_SPLIT_RE.split(cand_name) if t and len(t) >= 3]
        for token in tokens:
            token_ratio = SequenceMatcher(None, needle_lower, token).ratio()
            if token_ratio > best_ratio:
                best_ratio = token_ratio
                best_match = (cand_name, cand_item)

    if best_ratio >= threshold:
        return best_match
    return None


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
