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


# Split on whitespace and common Turkish/medical punctuation so that
# "Disposable enjektör (1,2,5 cc)" tokenizes to real words only.
_TOKEN_SPLIT_RE = re.compile(r"[\s,()/\-;:.\"']+")


def _tokenize_name(name: str) -> list[str]:
    """Tokenize a normalized (turkish_lower) name into bare word tokens.

    Empty tokens and pure-digit tokens shorter than 2 chars are dropped so
    that stray punctuation or single digits do not pollute membership tests.
    """
    return [t for t in _TOKEN_SPLIT_RE.split(name) if len(t) >= 2 or t.isdigit()]


def token_bound_substring_match(needle: str, haystack: str) -> bool:
    """Token-bound containment test for Turkish material-name matching.

    Returns True when the ``needle`` (a catalog entry name) matches the
    ``haystack`` (a billed material name) without the false positives that
    plain ``in`` substring matching produces. A short entry like ``"lam"``
    must not match ``"melamin"``; an entry like ``"süt sağma seti"`` should
    match ``"süt sağma seti (disposable)"``.

    Rules, in order:
      1. Exact equality (after normalization).
      2. The entry is a multi-word phrase and every one of its tokens is
         present in the haystack's token set (handles "süt sağma seti" vs
         "süt sağma seti (disposable)").
      3. The entry is a single token and that token appears verbatim in the
         haystack's token list (handles "ped" vs "pediyatrik" correctly —
         no match, since "ped" is not a token of "pediyatrik").

    Inputs are assumed already passed through ``turkish_lower``.
    """
    if not needle or not haystack:
        return False
    if needle == haystack:
        return True
    needle_tokens = _tokenize_name(needle)
    haystack_tokens = set(_tokenize_name(haystack))
    if not needle_tokens or not haystack_tokens:
        return False
    if len(needle_tokens) == 1:
        return needle_tokens[0] in haystack_tokens
    # Multi-word entry: require ALL of its tokens present in the haystack.
    return all(tok in haystack_tokens for tok in needle_tokens)


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

    Performance: SequenceMatcher.ratio() is expensive (~260k calls/cohort).
    Its value is bounded above by 2*min(len)/sum(len) (since matching blocks
    can't exceed the shorter string). When that bound is already below
    ``threshold``, the pair CANNOT reach threshold, so we skip the ratio()
    call entirely — measured to eliminate ~95% of calls with zero false
    negatives (the skipped pairs would have returned below-threshold anyway).
    """
    _TOKEN_SPLIT_RE = re.compile(r"[\s\(\)\-/,.;:]+")

    best_ratio = 0.0
    best_name: str | None = None
    best_item: Any = None
    needle_len = len(needle_lower)

    for cand_name, cand_item in candidates:
        # Level 1: full-name comparison with length-bound pre-filter.
        cand_len = len(cand_name)
        if cand_len and needle_len:
            # Upper bound on ratio() = 2*min/(sum). Skip if even the bound
            # can't reach threshold — ratio() would return below it anyway.
            if 2 * min(needle_len, cand_len) / (needle_len + cand_len) >= threshold:
                ratio = SequenceMatcher(None, needle_lower, cand_name).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_name = cand_name
                    best_item = cand_item

        # Level 2: token-level comparison with the same length-bound filter.
        tokens = [t for t in _TOKEN_SPLIT_RE.split(cand_name) if t and len(t) >= 3]
        for token in tokens:
            tok_len = len(token)
            if 2 * min(needle_len, tok_len) / (needle_len + tok_len) < threshold:
                continue
            token_ratio = SequenceMatcher(None, needle_lower, token).ratio()
            if token_ratio > best_ratio:
                best_ratio = token_ratio
                best_name = cand_name
                best_item = cand_item

    if best_ratio >= threshold and best_name is not None:
        return (best_name, best_item)
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
