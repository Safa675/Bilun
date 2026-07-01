"""Gate B export + manifest bootstrap for §4.2.18 / §4.2.36 drug indication pilot."""

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

_SECTION_PREFIXES = ("4.2.18", "4.2.36")
_DEONTIC_MODALITIES = frozenset(
    {"MUST_BILL", "MUST_NOT_BILL", "NO_PAY", "MAY_BILL", "PROHIBITED", "REGULATORY_ACTION"}
)
_DRUG_KEYWORDS = (
    "orlistat",
    "obez",
    "obesity",
    "parkinson",
    "apomorfin",
    "kabergolin",
    "entakapon",
    "tolkapon",
    "tolcapone",
    "amantadin",
    "rasajilin",
    "rasagilin",
    "pergolid",
    "pramipexol",
    "ropinirol",
    "bornaprin",
    "nöroloji",
    "geriatri",
    "endokrinoloji",
    "metabolizma",
    "bmi",
    "ilaç",
    "ilac",
    "rapor",
    "reçete",
    "recete",
    "ekstrapiramidal",
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
    if tier == "C" and section_id.startswith("4.2.18"):
        normalized = _normalize_tr(text)
        if "orlistat" in normalized and (
            "rapor" in normalized or "reçete" in normalized or "recete" in normalized
        ):
            return "A", inn or "orlistat"
        if "reçete" in normalized and "birer aylık" in normalized:
            return "A", inn or "orlistat"
    if tier == "C" and section_id.startswith("4.2.36"):
        normalized = _normalize_tr(text)
        if inn and ("rapor" in normalized or "reçete" in normalized or "recete" in normalized):
            return "A", inn
        if any(
            token in normalized
            for token in (
                "apomorfin",
                "kabergolin",
                "entakapon",
                "tolkapon",
                "amantadin",
                "rasajilin",
                "pergolid",
                "pramipexol",
                "ropinirol",
                "bornaprin",
            )
        ):
            if "rapor" in normalized or "reçete" in normalized or "recete" in normalized:
                return "A", inn or "parkinson_ilac"
    return tier, inn


def export_4218_4236_candidates(
    clauses_path: Path,
    *,
    encoded_clause_ids: frozenset[str] | None = None,
) -> pl.DataFrame:
    """Export all §4.2.18 / §4.2.36 rows (small sections — full clause trace)."""
    encoded_clause_ids = encoded_clause_ids or frozenset()
    clauses = pl.read_parquet(clauses_path)
    section = clauses.filter(
        pl.col("section_id").str.starts_with("4.2.18")
        | pl.col("section_id").str.starts_with("4.2.36")
    )
    if section.is_empty():
        return pl.DataFrame()

    rows: list[dict[str, Any]] = []
    for record in section.iter_rows(named=True):
        clause_id = str(record.get("clause_id") or "")
        section_id = str(record.get("section_id") or "")
        text = str(record.get("text_tr") or "")
        deontic = str(record.get("deontic_modality") or "")
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
                "defer_themes": ",".join(defer_themes) if defer_themes else "",
                "has_drug_keyword": _matches_drug_keyword(text),
            }
        )

    return pl.DataFrame(rows).sort("clause_id")


def _encoded_clause_ids_from_rules(rules: list[dict[str, Any]]) -> set[str]:
    encoded: set[str] = set()
    for rule in rules:
        for clause_id in rule.get("gate_b_sources") or []:
            encoded.add(str(clause_id))
    return encoded


def build_4218_4236_manifest(
    gate_b_frame: pl.DataFrame,
    rules: list[dict[str, Any]],
    *,
    effective_date: str,
) -> dict[str, Any]:
    """Manifest for §4.2.18 / §4.2.36 pilot — encoded + Tier C deferred trace."""
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

    section_4218_total = int(
        gate_b_frame.filter(pl.col("section_id").str.starts_with("4.2.18")).height
    )
    section_4236_total = int(
        gate_b_frame.filter(pl.col("section_id").str.starts_with("4.2.36")).height
    )
    tier_a_4218 = int(
        gate_b_frame.filter(
            pl.col("section_id").str.starts_with("4.2.18") & (pl.col("encode_tier") == "A")
        ).height
    )
    tier_c_4218 = int(
        gate_b_frame.filter(
            pl.col("section_id").str.starts_with("4.2.18") & (pl.col("encode_tier") == "C")
        ).height
    )
    tier_a_4236 = int(
        gate_b_frame.filter(
            pl.col("section_id").str.starts_with("4.2.36") & (pl.col("encode_tier") == "A")
        ).height
    )
    tier_c_4236 = int(
        gate_b_frame.filter(
            pl.col("section_id").str.starts_with("4.2.36") & (pl.col("encode_tier") == "C")
        ).height
    )

    return {
        "manifest_version": "r5-a5-v1",
        "section_id": "4.2.18,4.2.36",
        "effective_date": effective_date,
        "rules_in_json": len(rules),
        "section_4.2.18_clause_total": section_4218_total,
        "section_4.2.36_clause_total": section_4236_total,
        "section_4.2.18_tier_a_count": tier_a_4218,
        "section_4.2.18_tier_c_count": tier_c_4218,
        "section_4.2.36_tier_a_count": tier_a_4236,
        "section_4.2.36_tier_c_count": tier_c_4236,
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
    for prefix in _SECTION_PREFIXES:
        section_frame = enriched.filter(pl.col("section_id").str.starts_with(prefix))
        summary[f"section:{prefix}:total"] = section_frame.height
        for tier in ("A", "B", "C"):
            summary[f"section:{prefix}:tier_{tier.lower()}"] = int(
                section_frame.filter(pl.col("encode_tier") == tier).height
            )
    return summary


def write_gate_b_artifacts(
    *,
    clauses_path: Path,
    rules_path: Path,
    corpus_csv: Path,
    manifest_path: Path,
    effective_date: str,
    batch_rules: list[dict[str, Any]] | None = None,
) -> tuple[pl.DataFrame, dict[str, Any]]:
    if batch_rules is None:
        payload = json.loads(rules_path.read_text(encoding="utf-8"))
        batch_rules = [
            rule
            for rule in (payload.get("rules") or [])
            if str(rule.get("sut_section") or "").startswith(("4.2.18", "4.2.36"))
        ]
    manifest = build_4218_4236_manifest(
        export_4218_4236_candidates(clauses_path),
        batch_rules,
        effective_date=effective_date,
    )
    encoded = frozenset(manifest["gate_b_sources_encoded"])

    corpus_csv.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    frame = export_4218_4236_candidates(clauses_path, encoded_clause_ids=encoded)
    frame.write_csv(corpus_csv)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return frame, manifest


if __name__ == "__main__":
    from datetime import date

    from scripts.sut.rule_sources import load_legacy_drug_batch

    BATCH_A5_RULES = load_legacy_drug_batch(
        "drug_indication_4218_4236_batch_rules.py:BATCH_A5_RULES"
    )

    repo = _PROJECT_ROOT
    clauses = repo / "data/gazette/sut_clauses.parquet"
    corpus = repo / "data/gazette/prose_corpus/L4.2_drug_indication_4218_4236.csv"
    manifest = repo / "data/gazette/prose_manifests/L4.2_drug_indication_4218_4236_manifest.json"

    frame, manifest_payload = write_gate_b_artifacts(
        clauses_path=clauses,
        rules_path=repo / "data/gazette/prose_rules/drug_indication_prose.json",
        corpus_csv=corpus,
        manifest_path=manifest,
        effective_date=date.today().isoformat(),
        batch_rules=BATCH_A5_RULES,
    )
    print(f"Wrote {frame.height} rows -> {corpus}")
    print(
        f"Manifest: {len(manifest_payload['gate_b_sources_encoded'])} encoded "
        f"tier_c={manifest_payload['tier_c_deferred_count']} -> {manifest}"
    )
    for key, value in sorted(gate_b_summary(frame).items()):
        print(f"  {key}: {value}")
