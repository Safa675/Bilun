"""ICD-10 code normalisation and matching, shared by every rule that lists diagnosis codes.

The rules differ in how far a listed code reaches, so a caller names its reading:

- ``Icd10Cover.EXACT``: a listed code covers itself and the codes one dot segment below it. A
  category covers its dotted sub-codes (``K50`` covers ``K50.0``); a dotted code covers only itself
  (``M86.3`` covers neither the SKRS leaf ``M86.31`` nor its sibling ``M86.4``). EK-4/D's listed
  codes, the 4.2 drug-combination and the 2.4 treatment-pricing rules (their EK-2/D-3 HBO list and
  their clinical categories included) and the ravulizumab NMOSD code read it.
- ``Icd10Cover.LEAVES``: as ``EXACT``, and a dotted code also covers every longer code that starts
  with it, so ``M08.0`` covers the SKRS site leaves ``M08.00``-``M08.09`` (#305); never its parent
  or a sibling. The 4.2 drug-indication rules read it.

``icd10_in_range`` matches a gazette range (``A15-A19``, a single ``C34``) by the numeric category;
a dotted single span (``C49.5``) matches only itself (and a further dot segment). EK-1/A, EK-4/D's
ranges and the drug-indication ranges read it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from enum import Enum


class Icd10Cover(Enum):
    """How far a listed ICD-10 code reaches (see the module docstring)."""

    EXACT = "exact"
    LEAVES = "leaves"


def normalize_icd10(raw: object) -> str:
    """A code as the matchers compare it: stripped and upper-cased; ``None`` is ``""``."""
    return str(raw or "").strip().upper()


def normalize_icd10_list(values: Iterable[object] | None) -> list[str]:
    """Listed codes normalised in order; a falsy entry is dropped (a blank string stays ``""``)."""
    return [str(value).strip().upper() for value in values or [] if value]


def icd10_covers(listed: str, code: str, *, cover: Icd10Cover) -> bool:
    """True when the listed code covers ``code`` under ``cover``; both are compared as given."""
    if code == listed:
        return True
    if cover is Icd10Cover.LEAVES and "." in listed:
        return code.startswith(listed)
    return code.startswith(listed + ".")


def icd10_covered_by_any(code: str, listed: Iterable[str], *, cover: Icd10Cover) -> bool:
    """True when one of the listed codes covers ``code`` (both compared as given)."""
    return any(icd10_covers(item, code, cover=cover) for item in listed)


def icd10_any_code_covered(
    codes: Iterable[object] | None, listed: Iterable[str], *, cover: Icd10Cover
) -> bool:
    """True when a code (normalised, empty codes skipped) is covered by one of the listed codes."""
    listed = list(listed)
    for raw in codes or []:
        code = normalize_icd10(raw)
        if code and icd10_covered_by_any(code, listed, cover=cover):
            return True
    return False


def icd10_in_range(code: str, start: str, end: str) -> bool:
    """Check if an ICD-10 code falls within a gazette exemption range.

    Matching logic:
      Range "A15-A19" matches "A16", "A16.2", "A17", etc.
      Single "C34" matches "C34", "C34.1", "C34.9", etc.
      Sub-code "C49.5" matches only "C49.5" exactly.
    """
    if not code or not start:
        return False

    code = code.strip().upper()
    start = start.strip().upper()
    end = end.strip().upper()

    if not code or not code[0].isalpha():
        return False

    code_letter = code[0]
    start_letter = start[0] if start else ""

    if code_letter != start_letter:
        return False

    if "." in start and start == end:
        return code == start or code.startswith(start + ".")

    if "." in start:
        return code.startswith(start.split(".")[0])

    m_code = re.match(r"[A-Z](\d{2,3})", code)
    m_start = re.match(r"[A-Z](\d{2,3})", start)
    m_end = re.match(r"[A-Z](\d{2,3})", end)

    if not m_code or not m_start or not m_end:
        return False

    code_num = int(m_code.group(1))
    start_num = int(m_start.group(1))
    end_num = int(m_end.group(1))

    return start_num <= code_num <= end_num
