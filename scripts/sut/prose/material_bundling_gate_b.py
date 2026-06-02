"""Gate B extraction helpers for L1.4 §3.1–3.2 material bundling prose."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

import polars as pl

_KEYWORDS = (
    "ayrıca faturalandır",
    "faturalandırılmayacak",
    "faturalandırılamaz",
    "ayrı faturalandır",
    "ayrıca faturalandırılamaz",
    "ayrıca faturalandırılmaz",
)
_PREFIXES = ("3.1", "3.2")
_DEONTIC_MODALITIES = frozenset({"MUST_NOT_BILL", "NO_PAY"})

# Prose rows that duplicate annex-list enforcement (heuristic on Turkish excerpt).
_EK3B1_TEXT_PATTERNS = (
    r"ek-3\s*b-1",
    r"ek-3/b\s*listes",
    r"ek-3b\s*listes",
    r"sarf\s+malzemeleri\s+listes",
    r"paket\s+sarf",
    r"tüketim\s+malzemeleri\s+listes",
)
_EK3B2_TEXT_PATTERNS = (
    r"ek-3\s*b-2",
    r"kurumca\s+karşılanmaz\s+malzemeler\s+listes",
    r"ödenmeyecek\s+malzemeler\s+listes",
    r"hariç\s+malzemeler\s+listes",
)

_ENCODED_RULE_IDS: frozenset[str] = frozenset(
    {
        "3.1.3.(7).serbest_kodsuz",
        "3.1.3.(8).demirbas",
        "3.1.3.(9).reusable_provider",
        "3.1.2.c.warranty_maintenance",
        "3.1.1.(11).missing_material_code",
        "3.1.2.(2).not_in_ek3c",
        "3.1.1.(11).procedure_pairing",
    }
)


def _normalize_tr(text: str) -> str:
    folded = unicodedata.normalize("NFKD", str(text).casefold())
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


def _matches_any_pattern(text: str, patterns: tuple[str, ...]) -> bool:
    normalized = _normalize_tr(text)
    return any(re.search(pat, normalized) for pat in patterns)


def _annex_refs_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(item) for item in raw]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except json.JSONDecodeError:
            return []
    return []


def _selection_reason(
    *,
    has_keyword: bool,
    has_deontic: bool,
) -> str:
    if has_keyword and has_deontic:
        return "keyword_and_deontic"
    if has_keyword:
        return "keyword"
    return "deontic"


def _duplicate_of(
    *,
    excerpt: str,
    annex_refs: list[str],
) -> str:
    annex_upper = " ".join(annex_refs).upper()
    ek3b1_annex = any(
        token in annex_upper
        for token in ("EK-3B-1", "EK-3/B", "EK-3B", "EK-3B1")
    )
    ek3b2_annex = "EK-3B-2" in annex_upper or "EK-3B2" in annex_upper

    ek3b1_text = _matches_any_pattern(excerpt, _EK3B1_TEXT_PATTERNS)
    ek3b2_text = _matches_any_pattern(excerpt, _EK3B2_TEXT_PATTERNS)

    if (ek3b1_annex or ek3b1_text) and (ek3b2_annex or ek3b2_text):
        return "ek3b1_and_ek3b2"
    if ek3b1_annex or ek3b1_text:
        return "ek3b1"
    if ek3b2_annex or ek3b2_text:
        return "ek3b2"
    return "none"


def _encode_priority(duplicate_of: str, encoded_rule_id: str) -> str:
    if encoded_rule_id:
        return "skip_already_encoded"
    if duplicate_of != "none":
        return "skip_annex_duplicate"
    return "p1_encode"


def _suggested_condition_type(excerpt: str, deontic: str) -> str:
    norm = _normalize_tr(excerpt)
    if any(k in norm for k in ("kodsuz", "serbest kod")):
        return "material_name_any|material_code_missing"
    if "titubb" in norm or "uts" in norm or "barkod" in norm:
        return "titubb_uts_field"
    if "ek-3/c" in norm or "ek-3c" in norm:
        return "material_not_in_ek3c|material_in_ek3c"
    if "işlem" in norm and ("eşleş" in norm or "ilave" in norm):
        return "procedure_pairing_required"
    if deontic == "MUST_NOT_BILL":
        return "material_name_any"
    return "manual_review"


def load_candidate_clauses(clauses_path: Path) -> pl.DataFrame:
    """§3.1–3.2 rows matching Gate B keyword or NO_PAY / MUST_NOT_BILL deontic."""
    df = pl.read_parquet(clauses_path)

    prefix_expr = pl.lit(False)
    for prefix in _PREFIXES:
        prefix_expr = prefix_expr | pl.col("section_id").str.starts_with(prefix)

    keyword_expr = pl.lit(False)
    for kw in _KEYWORDS:
        keyword_expr = keyword_expr | pl.col("text_tr").str.contains(kw, literal=False)

    deontic_expr = pl.col("deontic_modality").is_in(list(_DEONTIC_MODALITIES))

    return df.filter(prefix_expr & (keyword_expr | deontic_expr))


def enrich_gate_b_dataframe(
    hit: pl.DataFrame,
    *,
    prose_json_path: Path | None = None,
) -> pl.DataFrame:
    """Add dedup, priority, and encoding hints for Gate B CSV outputs."""
    rows: list[dict[str, Any]] = []
    for record in hit.iter_rows(named=True):
        excerpt = str(record.get("text_tr") or "")
        annex_refs = _annex_refs_list(record.get("annex_refs"))
        deontic = str(record.get("deontic_modality") or "")

        has_keyword = any(kw in excerpt.casefold() for kw in _KEYWORDS)
        has_deontic = deontic in _DEONTIC_MODALITIES
        dup = _duplicate_of(excerpt=excerpt, annex_refs=annex_refs)

        encoded_rule_id = ""
        if prose_json_path and prose_json_path.is_file():
            # Clause-level mapping is manual; flag only when excerpt overlaps encoded keywords.
            norm = _normalize_tr(excerpt)
            if "demirbaş" in norm or "demirbas" in norm:
                encoded_rule_id = "3.1.3.(8).demirbas"
            elif "tekrar kullanılabilir" in norm or "tekrar kullanilabilir" in norm:
                encoded_rule_id = "3.1.3.(9).reusable_provider"
            elif "serbest kodsuz" in norm or "kodsuz giriş" in norm:
                encoded_rule_id = "3.1.3.(7).serbest_kodsuz"

        priority = _encode_priority(dup, encoded_rule_id)

        rows.append(
            {
                "clause_id": record.get("clause_id"),
                "section_id": record.get("section_id"),
                "section_title": record.get("section_title"),
                "deontic_modality": deontic,
                "selection_reason": _selection_reason(
                    has_keyword=has_keyword, has_deontic=has_deontic
                ),
                "duplicate_of": dup,
                "encode_priority": priority,
                "encoded_rule_id": encoded_rule_id,
                "suggested_condition_type": _suggested_condition_type(excerpt, deontic),
                "annex_refs": json.dumps(annex_refs, ensure_ascii=False),
                "excerpt": excerpt,
                "char_count": record.get("char_count"),
            }
        )

    return pl.DataFrame(rows)


def build_review_sample(
    enriched: pl.DataFrame,
    *,
    fraction: float = 0.1,
    min_rows: int = 5,
    seed: int = 42,
) -> pl.DataFrame:
    """Stratified sample for human modality review (≥10% of P1 encode candidates)."""
    candidates = enriched.filter(pl.col("encode_priority") == "p1_encode")
    if candidates.is_empty():
        candidates = enriched
    n = max(min_rows, int(len(candidates) * fraction + 0.999))
    n = min(n, len(candidates))
    if n <= 0:
        return candidates.head(0)

    # At least one row per section prefix when possible.
    parts: list[pl.DataFrame] = []
    for prefix in _PREFIXES:
        subset = candidates.filter(pl.col("section_id").str.starts_with(prefix))
        if len(subset) > 0:
            parts.append(subset.sample(n=1, shuffle=True, seed=seed))
    sample = pl.concat(parts).unique(subset=["clause_id"]) if parts else candidates.head(0)
    remaining = n - len(sample)
    if remaining > 0:
        remaining_pool = candidates.filter(
            ~pl.col("clause_id").is_in(sample["clause_id"].to_list())
            if len(sample) > 0
            else pl.lit(True)
        )
        if len(remaining_pool) > 0:
            extra = remaining_pool.sample(
                n=min(remaining, len(remaining_pool)), shuffle=True, seed=seed + 1
            )
            sample = pl.concat([sample, extra]).unique(subset=["clause_id"])
    return sample.sort("section_id", "clause_id")


def gate_b_summary(enriched: pl.DataFrame) -> dict[str, int]:
    return {
        "total_rows": len(enriched),
        "p1_encode": int(
            enriched.filter(pl.col("encode_priority") == "p1_encode").height
        ),
        "skip_annex_duplicate": int(
            enriched.filter(pl.col("encode_priority") == "skip_annex_duplicate").height
        ),
        "skip_already_encoded": int(
            enriched.filter(pl.col("encode_priority") == "skip_already_encoded").height
        ),
        "duplicate_ek3b1": int(enriched.filter(pl.col("duplicate_of") == "ek3b1").height),
        "duplicate_ek3b2": int(enriched.filter(pl.col("duplicate_of") == "ek3b2").height),
    }
