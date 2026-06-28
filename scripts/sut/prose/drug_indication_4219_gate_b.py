"""Gate B export + manifest bootstrap for §4.2.19 migraine drug indication pilot."""

from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path
from typing import Any

import polars as pl

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.prose.drug_indication_gate_b import (  # noqa: E402
    _encode_tier,
    _heuristic_inn,
    infer_defer_themes,
)

_SECTION_PREFIX = "4.2.19"
_DEONTIC_MODALITIES = frozenset(
    {"MUST_BILL", "MUST_NOT_BILL", "NO_PAY", "MAY_BILL", "PROHIBITED", "REGULATORY_ACTION"}
)
_DRUG_KEYWORDS = (
    "migren",
    "triptan",
    "topiramat",
    "topiramate",
    "sumatriptan",
    "zolmitriptan",
    "rizatriptan",
    "ilaç",
    "ilac",
    "rapor",
    "reçete",
    "recete",
    "nöroloji",
    "nöroloji",
)


def _normalize_tr(text: str) -> str:
    folded = unicodedata.normalize("NFKD", str(text).casefold())
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


def _matches_drug_keyword(text: str) -> bool:
    normalized = _normalize_tr(text)
    return any(keyword in normalized for keyword in _DRUG_KEYWORDS)


def _encode_tier_for_clause(text: str, *, section_id: str) -> tuple[str, str]:
    inn = _heuristic_inn(text)
    tier = _encode_tier(text, inn)
    if tier == "C" and section_id.startswith(_SECTION_PREFIX):
        normalized = _normalize_tr(text)
        if inn and ("rapor" in normalized or "reçete" in normalized or "recete" in normalized):
            return "A", inn
        if any(token in normalized for token in ("triptan", "topiramat", "topiramate", "migren")):
            if "reçete" in normalized or "recete" in normalized or "rapor" in normalized:
                return "A", inn or "migren_ilac"
    return tier, inn


def export_4219_candidates(
    clauses_path: Path,
    *,
    encoded_clause_ids: frozenset[str] | None = None,
) -> pl.DataFrame:
    """Export §4.2.19 rows with deontic or migraine drug-keyword signals."""
    encoded_clause_ids = encoded_clause_ids or frozenset()
    clauses = pl.read_parquet(clauses_path)
    section = clauses.filter(pl.col("section_id").str.starts_with(_SECTION_PREFIX))
    if section.is_empty():
        return pl.DataFrame()

    rows: list[dict[str, Any]] = []
    for record in section.iter_rows(named=True):
        clause_id = str(record.get("clause_id") or "")
        section_id = str(record.get("section_id") or "")
        text = str(record.get("text_tr") or "")
        deontic = str(record.get("deontic_modality") or "")
        if deontic not in _DEONTIC_MODALITIES and not _matches_drug_keyword(text):
            continue
        encode_tier, inn = _encode_tier_for_clause(text, section_id=section_id)
        if clause_id in encoded_clause_ids:
            encode_priority = "p0_encoded"
        elif encode_tier == "A":
            encode_priority = "p1_encode"
        elif encode_tier == "B":
            encode_priority = "p2_tier_b"
        else:
            encode_priority = "p3_tier_c"
        rows.append(
            {
                "clause_id": clause_id,
                "section_id": section_id,
                "deontic_modality": deontic,
                "text_tr": text,
                "heuristic_inn": inn,
                "encode_tier": encode_tier,
                "encode_priority": encode_priority,
                "in_manifest": clause_id in encoded_clause_ids,
            }
        )

    return pl.DataFrame(rows).sort("clause_id")


def _encoded_clause_ids_from_rules(rules: list[dict[str, Any]]) -> set[str]:
    encoded: set[str] = set()
    for rule in rules:
        for clause_id in rule.get("gate_b_sources") or []:
            encoded.add(str(clause_id))
    return encoded


def build_4219_manifest(
    gate_b_frame: pl.DataFrame,
    rules: list[dict[str, Any]],
    *,
    effective_date: str,
) -> dict[str, Any]:
    """Manifest for §4.2.19 pilot — encoded + Tier C deferred trace."""
    encoded_ids = _encoded_clause_ids_from_rules(rules)
    rules_by_clause: dict[str, list[str]] = {}
    for rule in rules:
        rule_id = str(rule.get("rule_id") or "")
        for clause_id in rule.get("gate_b_sources") or []:
            rules_by_clause.setdefault(str(clause_id), []).append(rule_id)

    traces: list[dict[str, Any]] = []
    tier_a_pending: list[str] = []
    tier_b_pending: list[str] = []
    tier_c_deferred: list[str] = []

    for row in gate_b_frame.iter_rows(named=True):
        clause_id = str(row.get("clause_id") or "")
        encode_tier = str(row.get("encode_tier") or "C")
        text = str(row.get("text_tr") or "")
        if clause_id in encoded_ids:
            status = "encoded"
        elif encode_tier == "A":
            status = "tier_a_pending"
            tier_a_pending.append(clause_id)
        elif encode_tier == "B":
            status = "tier_b_pending"
            tier_b_pending.append(clause_id)
        else:
            status = "tier_c_deferred"
            tier_c_deferred.append(clause_id)

        entry: dict[str, Any] = {
            "clause_id": clause_id,
            "section_id": str(row.get("section_id") or ""),
            "encode_tier": encode_tier,
            "manifest_status": status,
            "heuristic_inn": str(row.get("heuristic_inn") or ""),
        }
        if status == "encoded":
            entry["linked_rule_ids"] = sorted(rules_by_clause.get(clause_id, []))
        elif status == "tier_c_deferred":
            themes = infer_defer_themes(text)
            entry["defer_themes"] = themes
            labels = ", ".join(themes) if themes else "clinical_pathway"
            entry["defer_reason"] = (
                f"Deferred — requires structured ingest for: {labels}. "
                "Tier C manifest-only until EMR fields support pathway."
            )
        traces.append(entry)

    return {
        "manifest_version": "r5-a4-v1",
        "section_id": "4.2.19",
        "effective_date": effective_date,
        "rules_in_json": len(rules),
        "section_4.2.19_clause_total": gate_b_frame.height,
        "section_clause_total": gate_b_frame.height,
        "encoded_clause_count": len(encoded_ids),
        "encoded_clause_ids": sorted(encoded_ids),
        "gate_b_sources_encoded": sorted(encoded_ids),
        "tier_a_pending_clause_ids": sorted(tier_a_pending),
        "tier_b_pending_clause_ids": sorted(tier_b_pending),
        "tier_c_deferred_clause_ids": sorted(tier_c_deferred),
        "tier_a_pending_count": len(tier_a_pending),
        "tier_b_pending_count": len(tier_b_pending),
        "tier_c_deferred_count": len(tier_c_deferred),
        "clause_traces": traces,
    }


def gate_b_summary(enriched: pl.DataFrame) -> dict[str, int]:
    if enriched.is_empty():
        return {"total": 0}
    summary: dict[str, int] = {"total": enriched.height}
    for col in ("encode_tier", "encode_priority"):
        for key, count in enriched.group_by(col).len().iter_rows():
            summary[f"{col}:{key}"] = int(count)
    return summary


def write_gate_b_artifacts(
    *,
    clauses_path: Path,
    rules_path: Path,
    corpus_csv: Path,
    manifest_path: Path,
    effective_date: str,
) -> tuple[pl.DataFrame, dict[str, Any]]:
    payload = json.loads(rules_path.read_text(encoding="utf-8"))
    batch_rules = [
        rule
        for rule in (payload.get("rules") or [])
        if str(rule.get("sut_section") or "").startswith("4.2.19")
    ]
    manifest = build_4219_manifest(
        export_4219_candidates(clauses_path),
        batch_rules,
        effective_date=effective_date,
    )
    encoded = frozenset(manifest["gate_b_sources_encoded"])

    corpus_csv.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    frame = export_4219_candidates(clauses_path, encoded_clause_ids=encoded)
    frame.write_csv(corpus_csv)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return frame, manifest
