"""Gate B export + enrichment for L4.2 §4.2.14.C drug indication prose."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

import polars as pl

_SECTION_ID = "4.2.14.C"
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


def _load_pilot_inns(rules_path: Path) -> set[str]:
    if not rules_path.is_file():
        return set()
    payload = json.loads(rules_path.read_text(encoding="utf-8"))
    inns: set[str] = set()
    for rule in payload.get("rules") or []:
        for name in rule.get("drug_names") or []:
            inns.add(_normalize_tr(name))
    return inns


def _pilot_rule_id(text: str, pilot_inns: set[str]) -> str:
    normalized = _normalize_tr(text)
    for inn in sorted(pilot_inns, key=len, reverse=True):
        if inn and inn in normalized:
            return "existing_pilot"
    return ""


def export_4_2_14_c_candidates(
    clauses_path: Path,
    *,
    rules_path: Path | None = None,
) -> pl.DataFrame:
    """Export §4.2.14.C rows with Gate B enrichment columns."""
    rules_path = rules_path or Path("data/gazette/prose_rules/drug_indication_prose.json")
    pilot_inns = _load_pilot_inns(rules_path)

    clauses = pl.read_parquet(clauses_path)
    section = clauses.filter(pl.col("section_id") == _SECTION_ID)
    if section.is_empty():
        return pl.DataFrame()

    rows: list[dict[str, Any]] = []
    for row in section.iter_rows(named=True):
        text = str(row.get("text_tr") or "")
        inn = _heuristic_inn(text)
        tier = _encode_tier(text, inn)
        pilot = _pilot_rule_id(text, pilot_inns)
        duplicate_of = "existing_pilot" if pilot else "none"
        defer_themes = infer_defer_themes(text) if tier == "C" else []
        if tier == "A" and pilot:
            encode_priority = "skip_already_encoded"
        elif tier == "C":
            encode_priority = "defer_tier_c"
        elif tier == "A":
            encode_priority = "p1_encode"
        else:
            encode_priority = "p2_encode"

        rows.append(
            {
                "clause_id": row.get("clause_id"),
                "section_id": row.get("section_id"),
                "deontic_modality": row.get("deontic_modality"),
                "text_tr": text,
                "heuristic_inn": inn,
                "encode_tier": tier,
                "duplicate_of": duplicate_of,
                "pilot_rule_id": pilot,
                "encode_priority": encode_priority,
                "defer_themes": ",".join(defer_themes) if defer_themes else "",
            }
        )

    return pl.DataFrame(rows)


def write_gate_b_export(
    clauses_path: Path,
    output_csv: Path,
    *,
    rules_path: Path | None = None,
) -> pl.DataFrame:
    frame = export_4_2_14_c_candidates(clauses_path, rules_path=rules_path)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    frame.write_csv(output_csv)
    return frame


def gate_b_summary(enriched: pl.DataFrame) -> dict[str, int]:
    if enriched.is_empty():
        return {}
    summary: dict[str, int] = {"total": enriched.height}
    for col in ("encode_tier", "encode_priority", "duplicate_of"):
        for key, count in sorted(enriched.group_by(col).len().iter_rows()):
            summary[f"{col}:{key}"] = int(count)
    return dict(sorted(summary.items()))


def clause_ids_for_drug_names(
    clauses_path: Path,
    drug_names: list[str],
    *,
    section_id: str = _SECTION_ID,
    limit: int = 12,
) -> list[str]:
    """Return clause IDs whose text mentions any normalized drug token."""
    clauses = pl.read_parquet(clauses_path)
    section = clauses.filter(pl.col("section_id") == section_id)
    tokens = [_normalize_tr(name) for name in drug_names if name]
    hits: list[str] = []
    for row in section.iter_rows(named=True):
        text = _normalize_tr(str(row.get("text_tr") or ""))
        if any(token in text for token in tokens if token):
            cid = str(row.get("clause_id") or "")
            if cid:
                hits.append(cid)
        if len(hits) >= limit:
            break
    return hits


if __name__ == "__main__":
    repo = Path(__file__).resolve().parents[3]
    clauses = repo / "data/gazette/sut_clauses.parquet"
    out = repo / "data/gazette/prose_corpus/L4.2_drug_indication_4.2.14.C.csv"
    frame = write_gate_b_export(clauses, out)
    print(f"Wrote {frame.height} rows -> {out}")
    for key, value in sorted(gate_b_summary(frame).items()):
        print(f"  {key}: {value}")
