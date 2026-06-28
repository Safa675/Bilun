"""Gate B export + manifest bootstrap for §4.2.9 ESA / §4.2.27 coagulation pilot."""

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

_SECTION_PREFIXES = ("4.2.9", "4.2.27")
_SECTION_4227 = "4.2.27"
_MOTOR = "drug_indication_prose"
_TIER_B_4227 = frozenset(
    {"C006210", "C006219", "C006235", "C006241", "C006244", "C006287"}
)
_TIER_A_429 = frozenset(
    {"C004127", "C004128", "C004130", "C004131", "C004135", "C004137", "C004200"}
)
_TIER_A_4227 = frozenset(
    {
        "C006227",
        "C006228",
        "C006230",
        "C006232",
        "C006233",
        "C006239",
        "C006246",
        "C006247",
        "C006249",
        "C006250",
        "C006255",
        "C006267",
        "C006268",
    }
)
_DEONTIC_MODALITIES = frozenset(
    {"MUST_BILL", "MUST_NOT_BILL", "NO_PAY", "MAY_BILL", "PROHIBITED", "REGULATORY_ACTION"}
)
_DRUG_KEYWORDS = (
    "eritropoietin",
    "epoetin",
    "darbepoetin",
    "roksadustat",
    "etelkalsedid",
    "etelcalcetide",
    "hemofil",
    "faktör",
    "factor vii",
    "factor viii",
    "factor ix",
    "von willebrand",
    "feiba",
    "protrombin",
    "anti rh",
    "anti-rh",
    "emicizumab",
    "albumin",
    "ilaç",
    "ilac",
    "rapor",
    "reçete",
    "recete",
    "anemi",
    "hematoloji",
    "nefroloji",
    "diyaliz",
)


def _normalize_tr(text: str) -> str:
    folded = unicodedata.normalize("NFKD", str(text).casefold())
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


def _matches_drug_keyword(text: str) -> bool:
    normalized = _normalize_tr(text)
    return any(keyword in normalized for keyword in _DRUG_KEYWORDS)


def _in_force_clause_ids_4227(clauses_path: Path) -> frozenset[str]:
    """In-force §4.2.27 clause IDs from coverage parquet (matches gap_refresh)."""
    coverage_path = clauses_path.parent / "sut_clause_coverage.parquet"
    if not coverage_path.is_file():
        return frozenset()
    coverage = pl.read_parquet(coverage_path)
    motor = coverage.filter(
        (pl.col("primary_rule_id") == _MOTOR)
        & pl.col("section_id").str.starts_with(_SECTION_4227)
    )
    return frozenset(str(row) for row in motor["clause_id"].to_list())


def _gap_clause_ids_4227(clauses_path: Path) -> frozenset[str]:
    """Motor-bound §4.2.27 clause IDs with ``has_rule_encoding=false``."""
    coverage_path = clauses_path.parent / "sut_clause_coverage.parquet"
    if not coverage_path.is_file():
        return frozenset()
    coverage = pl.read_parquet(coverage_path)
    motor = coverage.filter(
        (pl.col("primary_rule_id") == _MOTOR)
        & pl.col("section_id").str.starts_with(_SECTION_4227)
        & ~pl.col("has_rule_encoding")
    )
    return frozenset(str(row) for row in motor["clause_id"].to_list())


def _encode_tier_for_clause(text: str, *, section_id: str, clause_id: str) -> tuple[str, str]:
    inn = _heuristic_inn(text)
    if clause_id in _TIER_B_4227:
        return "B", inn or _heuristic_inn_for_section(section_id, text)
    tier = _encode_tier(text, inn)
    if clause_id in _TIER_A_429 or clause_id in _TIER_A_4227:
        return "A", inn or _heuristic_inn_for_section(section_id, text)
    if tier == "C" and section_id.startswith("4.2.9"):
        normalized = _normalize_tr(text)
        if any(
            token in normalized
            for token in ("eritropoietin", "epoetin", "darbepoetin", "roksadustat", "etelkalsedid")
        ):
            if "rapor" in normalized or "reçete" in normalized or "recete" in normalized:
                return "A", inn or "esa"
    if tier == "C" and section_id.startswith("4.2.27"):
        normalized = _normalize_tr(text)
        if inn and ("rapor" in normalized or "reçete" in normalized or "recete" in normalized):
            return "A", inn
        if any(
            token in normalized
            for token in (
                "hemofil",
                "faktör",
                "factor",
                "von willebrand",
                "feiba",
                "protrombin",
                "anti rh",
                "immün tolerans",
            )
        ):
            if "rapor" in normalized or "reçete" in normalized or "recete" in normalized:
                return "A", inn or "koagulasyon_faktoru"
    return tier, inn


def _heuristic_inn_for_section(section_id: str, text: str) -> str:
    normalized = _normalize_tr(text)
    if section_id.startswith("4.2.9"):
        if "etelkalsedid" in normalized or "etelcalcetide" in normalized:
            return "etelcalcetide"
        return "esa"
    if "anti rh" in normalized or "anti-rh" in normalized:
        return "anti_rh"
    if "von willebrand" in normalized:
        return "von_willebrand"
    if "faktör viia" in normalized or "factor viia" in normalized:
        return "factor_viia"
    if "feiba" in normalized or "apcc" in normalized:
        return "apcc"
    return "koagulasyon_faktoru"


def export_4209_4227_candidates(
    clauses_path: Path,
    *,
    encoded_clause_ids: frozenset[str] | None = None,
) -> pl.DataFrame:
    """Export §4.2.9 / §4.2.27 rows with deontic or coagulation/ESA keyword signals.

    §4.2.27 uses in-force filtering from coverage parquet (4213 pattern); §4.2.9 is unchanged.
    """
    encoded_clause_ids = encoded_clause_ids or frozenset()
    in_force_4227 = _in_force_clause_ids_4227(clauses_path)
    clauses = pl.read_parquet(clauses_path)
    section = clauses.filter(
        pl.col("section_id").str.starts_with("4.2.9")
        | pl.col("section_id").str.starts_with("4.2.27")
    )
    if section.is_empty():
        return pl.DataFrame()

    rows: list[dict[str, Any]] = []
    for record in section.iter_rows(named=True):
        clause_id = str(record.get("clause_id") or "")
        section_id = str(record.get("section_id") or "")
        text = str(record.get("text_tr") or record.get("in_force_text") or "")
        deontic = str(record.get("deontic_modality") or "")
        has_deontic = deontic in _DEONTIC_MODALITIES
        has_drug_kw = _matches_drug_keyword(text)
        if section_id.startswith(_SECTION_4227):
            if in_force_4227 and clause_id not in in_force_4227:
                continue
        elif not has_deontic and not has_drug_kw:
            continue

        tier, inn = _encode_tier_for_clause(text, section_id=section_id, clause_id=clause_id)
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
                "has_drug_keyword": has_drug_kw,
            }
        )

    return pl.DataFrame(rows).sort("clause_id")


def _encoded_clause_ids_from_rules(rules: list[dict[str, Any]]) -> set[str]:
    encoded: set[str] = set()
    for rule in rules:
        for clause_id in rule.get("gate_b_sources") or []:
            encoded.add(str(clause_id))
    return encoded


def build_4209_4227_manifest(
    gate_b_frame: pl.DataFrame,
    rules: list[dict[str, Any]],
    *,
    effective_date: str,
) -> dict[str, Any]:
    """Manifest for §4.2.9 / §4.2.27 pilot — encoded + Tier C deferred trace."""
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

    section_429_total = int(
        gate_b_frame.filter(pl.col("section_id").str.starts_with("4.2.9")).height
    )
    section_4227_total = int(
        gate_b_frame.filter(pl.col("section_id").str.starts_with("4.2.27")).height
    )
    tier_a_429 = int(
        gate_b_frame.filter(
            pl.col("section_id").str.starts_with("4.2.9") & (pl.col("encode_tier") == "A")
        ).height
    )
    tier_c_429 = int(
        gate_b_frame.filter(
            pl.col("section_id").str.starts_with("4.2.9") & (pl.col("encode_tier") == "C")
        ).height
    )
    tier_a_4227 = int(
        gate_b_frame.filter(
            pl.col("section_id").str.starts_with("4.2.27") & (pl.col("encode_tier") == "A")
        ).height
    )
    tier_c_4227 = int(
        gate_b_frame.filter(
            pl.col("section_id").str.starts_with("4.2.27") & (pl.col("encode_tier") == "C")
        ).height
    )

    return {
        "manifest_version": "r5-a6-v1",
        "section_id": "4.2.9,4.2.27",
        "effective_date": effective_date,
        "rules_in_json": len(rules),
        "section_4.2.9_clause_total": section_429_total,
        "section_4.2.27_clause_total": section_4227_total,
        "section_4.2.9_tier_a_count": tier_a_429,
        "section_4.2.9_tier_c_count": tier_c_429,
        "section_4.2.27_tier_a_count": tier_a_4227,
        "section_4.2.27_tier_c_count": tier_c_4227,
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


def _manifest_status_ids_4227(manifest: dict[str, Any]) -> dict[str, frozenset[str]]:
    traces = [
        t
        for t in manifest.get("clause_traces") or []
        if str(t.get("section_id") or "").startswith(_SECTION_4227)
    ]
    return {
        "encoded": frozenset(
            str(t["clause_id"]) for t in traces if t.get("manifest_status") == "encoded"
        ),
        "tier_c_deferred": frozenset(
            str(t["clause_id"]) for t in traces if t.get("manifest_status") == "tier_c_deferred"
        ),
        "tier_a_pending": frozenset(
            str(t["clause_id"]) for t in traces if t.get("manifest_status") == "tier_a_pending"
        ),
        "tier_b_pending": frozenset(
            str(t["clause_id"]) for t in traces if t.get("manifest_status") == "tier_b_pending"
        ),
    }


def audit_4227_gap_parity(
    clauses_path: Path,
    manifest: dict[str, Any],
    *,
    gate_b_frame: pl.DataFrame | None = None,
) -> dict[str, Any]:
    """Parity audit: every §4.2.27 coverage gap must be honestly traced."""
    gap_ids = _gap_clause_ids_4227(clauses_path)
    statuses = _manifest_status_ids_4227(manifest)
    trace_ids = {
        str(t.get("clause_id") or "")
        for t in manifest.get("clause_traces") or []
        if str(t.get("section_id") or "").startswith(_SECTION_4227)
    }

    honest_gap_ids = (
        statuses["encoded"]
        | statuses["tier_c_deferred"]
        | statuses["tier_a_pending"]
        | statuses["tier_b_pending"]
    )
    untraced = sorted(gap_ids - honest_gap_ids)
    missing_from_traces = sorted(gap_ids - trace_ids)

    frame = (
        gate_b_frame
        if gate_b_frame is not None
        else export_4209_4227_candidates(clauses_path)
    )
    export_ids_4227 = {
        str(cid)
        for cid in frame.filter(pl.col("section_id").str.starts_with(_SECTION_4227))[
            "clause_id"
        ].to_list()
    }
    gaps_missing_export = sorted(gap_ids - export_ids_4227)

    return {
        "gap_count": len(gap_ids),
        "encoded_count": len(statuses["encoded"]),
        "tier_b_pending_count": len(statuses["tier_b_pending"]),
        "tier_c_deferred_count": len(statuses["tier_c_deferred"]),
        "untraced_before": len(untraced) + len(gaps_missing_export),
        "untraced_after": len(untraced) + len(gaps_missing_export),
        "untraced_clause_ids": untraced,
        "missing_from_traces": missing_from_traces,
        "gaps_missing_export": gaps_missing_export,
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
            if str(rule.get("sut_section") or "").startswith(("4.2.9", "4.2.27"))
        ]
    frame = export_4209_4227_candidates(clauses_path)
    manifest = build_4209_4227_manifest(
        frame,
        batch_rules,
        effective_date=effective_date,
    )
    encoded = frozenset(manifest["gate_b_sources_encoded"])

    corpus_csv.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    frame = export_4209_4227_candidates(clauses_path, encoded_clause_ids=encoded)
    audit = audit_4227_gap_parity(clauses_path, manifest, gate_b_frame=frame)
    manifest["section_4.2.27_gap_audit"] = {
        "untraced_before": audit["untraced_before"],
        "untraced_after": audit["untraced_after"],
        "gap_count": audit["gap_count"],
    }
    frame.write_csv(corpus_csv)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return frame, manifest


if __name__ == "__main__":
    from datetime import date

    from scripts.sut.prose.drug_indication_4209_4227_batch_rules import BATCH_A6_RULES

    repo = _PROJECT_ROOT
    clauses = repo / "data/gazette/sut_clauses.parquet"
    corpus = repo / "data/gazette/prose_corpus/L4.2_drug_indication_4209_4227.csv"
    manifest = repo / "data/gazette/prose_manifests/L4.2_drug_indication_4209_4227_manifest.json"

    frame, manifest_payload = write_gate_b_artifacts(
        clauses_path=clauses,
        rules_path=repo / "data/gazette/prose_rules/drug_indication_prose.json",
        corpus_csv=corpus,
        manifest_path=manifest,
        effective_date=date.today().isoformat(),
        batch_rules=BATCH_A6_RULES,
    )
    print(f"Wrote {frame.height} rows -> {corpus}")
    print(
        f"Manifest: {len(manifest_payload['gate_b_sources_encoded'])} encoded "
        f"tier_c={manifest_payload['tier_c_deferred_count']} -> {manifest}"
    )
    for key, value in sorted(gate_b_summary(frame).items()):
        print(f"  {key}: {value}")
