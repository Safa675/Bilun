"""Reading a material line, shared by the §3 material-bundling and specialty-material rules.

``material_fields`` reads the name, code and unit price a material line carries under either of
its key spellings. ``material_name_matches`` says whether one of a rule's keywords occurs in the
material name, both folded ``TurkishFold.ACCENTLESS`` (so the dotless ``ı`` stays ``ı``). The
dental §2.4.1 rule keeps its own name match, which also reads a negation ("altın içermeyen").
"""

from __future__ import annotations

from typing import Any

from ..turkish_fold import TurkishFold, fold_turkish


def material_fields(mat: dict[str, Any]) -> tuple[str, str, float]:
    """``(name, code, unit_price)``: name trimmed, code trimmed and upper-cased, price 0 when absent."""
    name = str(mat.get("name") or mat.get("material_name") or "").strip()
    code = str(mat.get("code") or mat.get("material_code") or "").strip().upper()
    unit_price = float(mat.get("unit_price") or mat.get("billed_amount_try") or 0)
    return name, code, unit_price


def material_name_matches(material_name: str, keywords: list[str]) -> bool:
    """True when a folded keyword is a substring of the folded name (an empty name never matches)."""
    normalized = fold_turkish(material_name, TurkishFold.ACCENTLESS)
    if not normalized:
        return False
    for keyword in keywords:
        if fold_turkish(keyword, TurkishFold.ACCENTLESS) in normalized:
            return True
    return False
