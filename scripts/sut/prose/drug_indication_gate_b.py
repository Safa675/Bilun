"""Shared Gate B primitives for drug indication (themes / INN / tier).

CSV export for §4.2.14.C was retired — use ``gate_b_generic.export_candidates``
with ``SECTION_4214C`` instead.
"""

from __future__ import annotations

import re
import unicodedata

_TIER_C_PATTERNS = (
    r"\becog\b",
    r"pd-l1",
    r"pd l1",
    r"egfr",
    r"alk",
    r"ros1",
    r"mutasyon",
    r"minör yanıt",
    r"majör yanıt",
    r"kür sonunda",
    r"sağlık bakanlığı",
    r"performans",
    r"transfüzyon",
    r"karnofsky",
)
_CLINICAL_COMPLEX_RE = re.compile("|".join(_TIER_C_PATTERNS), re.I)

_DEFER_THEME_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "ecog",
        re.compile(
            r"\becog\b|karnofsky|performans durumu|performans skoru|performans skor",
            re.I,
        ),
    ),
    (
        "mutation_panel",
        re.compile(
            r"pd-?l1|egfr|\balk\b|ros1|braf|\bher2\b|mutasyon|gen analiz|molekuler|moleküler",
            re.I,
        ),
    ),
    (
        "prior_therapy",
        re.compile(
            r"onceden|önceden|onceki|önceki|birinci basamak|ikinci basamak|"
            r"\d+\.\s*kür|salvage|refrakter|basamak kemoterapi|hat tedavi",
            re.I,
        ),
    ),
    (
        "response_assessment",
        re.compile(
            r"yanit|yanıt|respons|progresyon|stabil hastalik|stabil hastalık|"
            r"min(?:or|ör)\s+yan|maj(?:or|ör)\s+yan|kür sonunda",
            re.I,
        ),
    ),
    (
        "moh_patient_approval",
        re.compile(
            r"saglik bakanligi|sağlık bakanlığı|bakanlik onay|bakanlık onay|"
            r"hasta ozelinde|hasta özelinde|saglik bakanligindan|sağlık bakanlığından",
            re.I,
        ),
    ),
)


def infer_defer_themes(text: str) -> list[str]:
    """Map Tier C clause prose to deferred-ingest theme tags (Phase 5)."""
    normalized = _normalize_tr(text)
    themes: list[str] = []
    for theme_id, pattern in _DEFER_THEME_PATTERNS:
        if pattern.search(normalized) or pattern.search(str(text or "")):
            themes.append(theme_id)
    if not themes and _CLINICAL_COMPLEX_RE.search(normalized):
        themes.append("clinical_pathway")
    if not themes:
        themes.append("clinical_pathway")
    return themes


def _normalize_tr(text: str) -> str:
    folded = unicodedata.normalize("NFKD", str(text).casefold())
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


def _heuristic_inn(text: str) -> str:
    """Best-effort INN from drug-leading fıkra text."""
    t = str(text or "").strip()
    m = re.match(r"^[\(\[]?(?:\d+|[a-zçğıöşü])[\)\].]\s*", t, re.I)
    rest = t[m.end() :].strip() if m else t
    seg = rest.split(";")[0].split(",")[0].strip()
    if len(seg) > 80 or seg.lower().startswith("bu "):
        return ""
    return seg


def _encode_tier(text: str, heuristic_inn: str) -> str:
    if not heuristic_inn:
        return "C"
    if _CLINICAL_COMPLEX_RE.search(text):
        return "C"
    normalized = _normalize_tr(text)
    if "rapor" in normalized or "reçete" in normalized or "recete" in normalized:
        if len(heuristic_inn) < 60:
            return "A"
        return "B"
    if "endikasyon" in normalized and len(heuristic_inn) < 60:
        return "A"
    return "C"
