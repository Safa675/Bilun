"""Gate B export + manifest bootstrap for §4.2.24 asthma / COPD / allergy drug indication pilot."""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from datetime import date
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

_SECTION_PREFIX = "4.2.24."
_MOTOR = "drug_indication_prose"
_DEONTIC_MODALITIES = frozenset(
    {"MUST_BILL", "MUST_NOT_BILL", "NO_PAY", "MAY_BILL", "PROHIBITED", "REGULATORY_ACTION"}
)
_DRUG_KEYWORDS = (
    "formeterol",
    "salmeterol",
    "vilanterol",
    "montelukast",
    "zafirlukast",
    "mepolizumab",
    "benralizumab",
    "omalizumab",
    "dupilumab",
    "tezepelumab",
    "indakaterol",
    "tiotropium",
    "glikopironyum",
    "flutikazon",
    "budesonid",
    "beclometazon",
    "laba",
    "lama",
    "inhale kortikosteroid",
    "nasal kortikosteroid",
    "antihistaminik",
    "azelastin",
    "astım",
    "astim",
    "koah",
    "obstrüktif",
    "alerji",
    "ilaç",
    "ilac",
    "rapor",
    "reçete",
    "recete",
)
_INN_TOKENS = (
    "formeterol",
    "salmeterol",
    "vilanterol",
    "montelukast",
    "zafirlukast",
    "mepolizumab",
    "benralizumab",
    "omalizumab",
    "indakaterol",
    "tiotropium",
    "flutikazon",
    "budesonid",
    "azelastin",
)


def _normalize_tr(text: str) -> str:
    folded = unicodedata.normalize("NFKD", str(text).casefold())
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


def _matches_drug_keyword(text: str) -> bool:
    normalized = _normalize_tr(text)
    return any(keyword in normalized for keyword in _DRUG_KEYWORDS)


def _drug_keyword_density(text: str) -> int:
    normalized = _normalize_tr(text)
    return sum(1 for keyword in _DRUG_KEYWORDS if keyword in normalized)


def _has_report_signal(text: str) -> bool:
    normalized = _normalize_tr(text)
    return "rapor" in normalized or "reçete" in normalized or "recete" in normalized


def _encode_tier_for_clause(text: str, *, section_id: str) -> tuple[str, str]:
    inn = _heuristic_inn(text)
    tier = _encode_tier(text, inn)
    if tier == "C" and section_id.startswith("4.2.24"):
        normalized = _normalize_tr(text)
        if inn and _has_report_signal(text):
            return "A", inn
        if any(token in normalized for token in _INN_TOKENS) and _has_report_signal(text):
            return "A", inn or "solunum_ilac"
    return tier, inn


def _signal_score(*, deontic: str, text: str, tier: str) -> int:
    score = _drug_keyword_density(text)
    if deontic in _DEONTIC_MODALITIES:
        score += 3
    if _has_report_signal(text):
        score += 2
    if tier == "A":
        score += 2
    return score


def _in_force_clause_ids(clauses_path: Path) -> frozenset[str]:
    """In-force §4.2.24 clause IDs from coverage parquet."""
    coverage_path = clauses_path.parent / "sut_clause_coverage.parquet"
    if not coverage_path.is_file():
        return frozenset()
    coverage = pl.read_parquet(coverage_path)
    motor = coverage.filter(
        (pl.col("primary_rule_id") == _MOTOR)
        & pl.col("section_id").str.starts_with(_SECTION_PREFIX)
    )
    return frozenset(str(row) for row in motor["clause_id"].to_list())


def export_4224_candidates(
    clauses_path: Path,
    *,
    encoded_clause_ids: frozenset[str] | None = None,
) -> pl.DataFrame:
    """Export in-force §4.2.24.* rows with Gate B enrichment sorted by signal score."""
    encoded_clause_ids = encoded_clause_ids or frozenset()
    in_force = _in_force_clause_ids(clauses_path)
    clauses = pl.read_parquet(clauses_path)
    section = clauses.filter(pl.col("section_id").str.starts_with(_SECTION_PREFIX))
    if in_force:
        section = section.filter(pl.col("clause_id").is_in(list(in_force)))
    if section.is_empty():
        return pl.DataFrame()

    rows: list[dict[str, Any]] = []
    for record in section.iter_rows(named=True):
        clause_id = str(record.get("clause_id") or "")
        section_id = str(record.get("section_id") or "")
        text = str(record.get("text_tr") or "")
        deontic = str(record.get("deontic_modality") or "")
        has_deontic = deontic in _DEONTIC_MODALITIES
        has_drug_kw = _matches_drug_keyword(text)
        if in_force or has_deontic or has_drug_kw:
            pass
        else:
            continue

        tier, inn = _encode_tier_for_clause(text, section_id=section_id)
        defer_themes = infer_defer_themes(text) if tier == "C" else []
        if clause_id in encoded_clause_ids:
            encode_priority = "skip_already_encoded"
        elif tier == "C":
            encode_priority = "defer_tier_c"
        elif tier == "A":
            encode_priority = "p1_encode"
        else:
            encode_priority = "p2_encode"

        rows.append(
            {
                "clause_id": clause_id,
                "section_id": section_id,
                "deontic_modality": deontic,
                "text_tr": text,
                "heuristic_inn": inn,
                "encode_tier": tier,
                "encode_priority": encode_priority,
                "signal_score": _signal_score(deontic=deontic, text=text, tier=tier),
                "defer_themes": ",".join(defer_themes) if defer_themes else "",
            }
        )

    return (
        pl.DataFrame(rows)
        .sort(["signal_score", "clause_id"], descending=[True, False])
        if rows
        else pl.DataFrame()
    )


def _encoded_clause_ids_from_rules(rules: list[dict[str, Any]]) -> set[str]:
    encoded: set[str] = set()
    for rule in rules:
        for clause_id in rule.get("gate_b_sources") or []:
            encoded.add(str(clause_id))
    return encoded


def build_4224_manifest(
    gate_b_frame: pl.DataFrame,
    rules: list[dict[str, Any]],
    *,
    effective_date: str,
) -> dict[str, Any]:
    """Manifest for §4.2.24 pilot — encoded + tier_a_pending + Tier C deferred."""
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
            "signal_score": int(row.get("signal_score") or 0),
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
        "manifest_version": "r5-a24-v1",
        "section_id": "4.2.24",
        "effective_date": effective_date,
        "rules_in_json": len(rules),
        "section_4.2.24_clause_total": gate_b_frame.height,
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
    rules: list[dict[str, Any]],
    corpus_csv: Path,
    manifest_path: Path,
    effective_date: str,
) -> tuple[pl.DataFrame, dict[str, Any]]:
    manifest = build_4224_manifest(
        export_4224_candidates(clauses_path),
        rules,
        effective_date=effective_date,
    )
    encoded = frozenset(manifest["gate_b_sources_encoded"])

    corpus_csv.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    frame = export_4224_candidates(clauses_path, encoded_clause_ids=encoded)
    frame.write_csv(corpus_csv)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return frame, manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="§4.2.24 asthma/COPD Gate B export")
    parser.add_argument(
        "--write-manifest",
        action="store_true",
        help="Write corpus CSV + manifest JSON using batch rules (pre-merge)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    from scripts.sut.rule_sources import load_legacy_drug_batch

    BATCH_A24_RULES = load_legacy_drug_batch(
        "drug_indication_4224_pilot_batch_rules.py:BATCH_A24_RULES"
    )

    args = _parse_args()
    repo = _PROJECT_ROOT
    clauses = repo / "data/gazette/sut_clauses.parquet"
    corpus = repo / "data/gazette/prose_corpus/L4.2_drug_indication_4224.csv"
    manifest = repo / "data/gazette/prose_manifests/L4.2_drug_indication_4224_manifest.json"
    effective = date.today().isoformat()

    frame, manifest_payload = write_gate_b_artifacts(
        clauses_path=clauses,
        rules=BATCH_A24_RULES,
        corpus_csv=corpus,
        manifest_path=manifest,
        effective_date=effective,
    )
    print(f"Wrote {frame.height} rows -> {corpus}")
    print(
        f"Manifest: {len(manifest_payload['gate_b_sources_encoded'])} encoded "
        f"tier_a_pending={manifest_payload['tier_a_pending_count']} "
        f"tier_b_pending={manifest_payload['tier_b_pending_count']} "
        f"tier_c={manifest_payload['tier_c_deferred_count']} -> {manifest}"
    )
    for key, value in sorted(gate_b_summary(frame).items()):
        print(f"  {key}: {value}")
