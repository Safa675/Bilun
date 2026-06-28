"""Gate B export + Tier C trace completion for §4.2.13 viral hepatitis."""

from __future__ import annotations

import json
import re
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

_SECTION_PREFIX = "4.2.13"
_MOTOR = "drug_indication_prose"
_DEONTIC_MODALITIES = frozenset(
    {"MUST_BILL", "MUST_NOT_BILL", "NO_PAY", "MAY_BILL", "PROHIBITED", "REGULATORY_ACTION"}
)
_TIER_B_ORAL_SWITCH_RE = re.compile(
    r"oral antiviral (?:degisimi|değişimi) ya da tedaviye yeni oral antiviral",
    re.I,
)
_TIER_B_CLAUSE_IDS = frozenset({"C004584", "C004593"})
_DRUG_KEYWORDS = (
    "ilaç",
    "ilac",
    "antiviral",
    "interferon",
    "ribavirin",
    "entekavir",
    "tenofovir",
    "lamivudin",
    "sofosbuvir",
    "ledipasvir",
    "glekaprevir",
    "pibrentasvir",
    "velpatasvir",
    "pegile",
    "peginterferon",
    "hepatit",
    "endikasyon",
    "rapor",
    "reçete",
    "recete",
)


def _normalize_tr(text: str) -> str:
    folded = unicodedata.normalize("NFKD", str(text).casefold())
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


def _matches_drug_keyword(text: str) -> bool:
    normalized = _normalize_tr(text)
    return any(keyword in normalized for keyword in _DRUG_KEYWORDS)


def _in_force_clause_ids(clauses_path: Path) -> frozenset[str]:
    """In-force §4.2.13 clause IDs from coverage parquet (matches gap_refresh)."""
    coverage_path = clauses_path.parent / "sut_clause_coverage.parquet"
    if not coverage_path.is_file():
        return frozenset()
    coverage = pl.read_parquet(coverage_path)
    motor = coverage.filter(
        (pl.col("primary_rule_id") == _MOTOR)
        & pl.col("section_id").str.starts_with(_SECTION_PREFIX)
    )
    return frozenset(str(row) for row in motor["clause_id"].to_list())


def _encode_tier_for_clause(text: str, *, section_id: str, clause_id: str) -> tuple[str, str]:
    if clause_id in _TIER_B_CLAUSE_IDS:
        return "B", "hepatit_ilac"
    inn = _heuristic_inn(text)
    tier = _encode_tier(text, inn)
    if tier == "C" and section_id.startswith(_SECTION_PREFIX):
        normalized = _normalize_tr(text)
        if _TIER_B_ORAL_SWITCH_RE.search(normalized):
            return "B", "hepatit_ilac"
    if tier == "C" and section_id.startswith(_SECTION_PREFIX):
        normalized = _normalize_tr(text)
        if inn and ("rapor" in normalized or "reçete" in normalized or "recete" in normalized):
            return "A", inn
        if any(
            token in normalized
            for token in (
                "entekavir",
                "tenofovir",
                "lamivudin",
                "sofosbuvir",
                "ledipasvir",
                "glekaprevir",
                "pibrentasvir",
                "pegile interferon",
                "peginterferon",
            )
        ):
            if "rapor" in normalized or "reçete" in normalized or "recete" in normalized:
                return "A", inn or "hepatit_ilac"
    return tier, inn


def export_4213_candidates(
    clauses_path: Path,
    *,
    encoded_clause_ids: frozenset[str] | None = None,
) -> pl.DataFrame:
    """Export in-force §4.2.13 rows with Gate B enrichment."""
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
            }
        )

    return pl.DataFrame(rows).sort("clause_id")


def _encoded_clause_ids_from_rules(rules: list[dict[str, Any]]) -> set[str]:
    encoded: set[str] = set()
    for rule in rules:
        for clause_id in rule.get("gate_b_sources") or []:
            encoded.add(str(clause_id))
    return encoded


def _trace_entry(
    row: dict[str, Any],
    *,
    encoded_ids: set[str],
    rules_by_clause: dict[str, list[str]],
) -> tuple[dict[str, Any], str]:
    clause_id = str(row.get("clause_id") or "")
    encode_tier = str(row.get("encode_tier") or "C")
    text = str(row.get("text_tr") or "")
    if clause_id in encoded_ids:
        status = "encoded"
    elif encode_tier == "A":
        status = "tier_a_pending"
    elif encode_tier == "B":
        status = "tier_b_pending"
    else:
        status = "tier_c_deferred"

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
    return entry, status


def build_4213_manifest(
    gate_b_frame: pl.DataFrame,
    rules: list[dict[str, Any]],
    *,
    effective_date: str,
) -> dict[str, Any]:
    """Manifest for §4.2.13 hepatitis — encoded + Tier C deferred trace."""
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
        entry, status = _trace_entry(
            row,
            encoded_ids=encoded_ids,
            rules_by_clause=rules_by_clause,
        )
        clause_id = entry["clause_id"]
        if status == "tier_a_pending":
            tier_a_pending.append(clause_id)
        elif status == "tier_b_pending":
            tier_b_pending.append(clause_id)
        elif status == "tier_c_deferred":
            tier_c_deferred.append(clause_id)
        traces.append(entry)

    return {
        "manifest_version": "r5-hep4213-v1",
        "section_id": "4.2.13",
        "effective_date": effective_date,
        "rules_in_json": len(rules),
        "section_4.2.13_clause_total": gate_b_frame.height,
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


def merge_4213_into_shared_manifest(
    manifest_4213: dict[str, Any],
    existing_shared: dict[str, Any] | None,
    rules_4213_4216: list[dict[str, Any]],
    *,
    effective_date: str,
) -> dict[str, Any]:
    """Patch §4.2.13 traces into the shared 4213+4216 manifest; preserve §4.2.16."""
    traces_4216: list[dict[str, Any]] = []
    if existing_shared:
        traces_4216 = [
            trace
            for trace in existing_shared.get("clause_traces") or []
            if str(trace.get("section_id") or "").startswith("4.2.16")
        ]

    traces_4213 = list(manifest_4213.get("clause_traces") or [])
    all_traces = sorted(traces_4213 + traces_4216, key=lambda t: str(t.get("clause_id") or ""))

    encoded_ids = _encoded_clause_ids_from_rules(rules_4213_4216)
    tier_a_pending = [t["clause_id"] for t in all_traces if t.get("manifest_status") == "tier_a_pending"]
    tier_b_pending = [t["clause_id"] for t in all_traces if t.get("manifest_status") == "tier_b_pending"]
    tier_c_deferred = [
        t["clause_id"] for t in all_traces if t.get("manifest_status") == "tier_c_deferred"
    ]

    section_4213_total = len(traces_4213)
    section_4216_total = len(traces_4216)

    return {
        "manifest_version": "r5-a2-v1",
        "section_id": "4.2.13,4.2.16",
        "effective_date": effective_date,
        "rules_in_json": len(rules_4213_4216),
        "section_4.2.13_clause_total": section_4213_total,
        "section_4.2.16_clause_total": section_4216_total,
        "section_clause_total": section_4213_total + section_4216_total,
        "encoded_clause_count": len(encoded_ids),
        "encoded_clause_ids": sorted(encoded_ids),
        "gate_b_sources_encoded": sorted(encoded_ids),
        "tier_a_pending_clause_ids": sorted(tier_a_pending),
        "tier_b_pending_clause_ids": sorted(tier_b_pending),
        "tier_c_deferred_clause_ids": sorted(tier_c_deferred),
        "tier_a_pending_count": len(tier_a_pending),
        "tier_b_pending_count": len(tier_b_pending),
        "tier_c_deferred_count": len(tier_c_deferred),
        "clause_traces": all_traces,
    }


def _gap_clause_ids(clauses_path: Path) -> frozenset[str]:
    """Motor-bound §4.2.13 clause IDs with ``has_rule_encoding=false``."""
    coverage_path = clauses_path.parent / "sut_clause_coverage.parquet"
    if not coverage_path.is_file():
        return frozenset()
    coverage = pl.read_parquet(coverage_path)
    motor = coverage.filter(
        (pl.col("primary_rule_id") == _MOTOR)
        & pl.col("section_id").str.starts_with(_SECTION_PREFIX)
        & ~pl.col("has_rule_encoding")
    )
    return frozenset(str(row) for row in motor["clause_id"].to_list())


def _manifest_status_ids(manifest: dict[str, Any]) -> dict[str, frozenset[str]]:
    traces = [
        t
        for t in manifest.get("clause_traces") or []
        if str(t.get("section_id") or "").startswith(_SECTION_PREFIX)
    ]
    encoded = frozenset(
        str(t["clause_id"]) for t in traces if t.get("manifest_status") == "encoded"
    )
    tier_c = frozenset(
        str(t["clause_id"]) for t in traces if t.get("manifest_status") == "tier_c_deferred"
    )
    tier_a = frozenset(
        str(t["clause_id"]) for t in traces if t.get("manifest_status") == "tier_a_pending"
    )
    tier_b = frozenset(
        str(t["clause_id"]) for t in traces if t.get("manifest_status") == "tier_b_pending"
    )
    return {
        "encoded": encoded,
        "tier_c_deferred": tier_c,
        "tier_a_pending": tier_a,
        "tier_b_pending": tier_b,
    }


def scan_4213_tier_ab_promotions(
    gate_b_frame: pl.DataFrame,
    *,
    encoded_clause_ids: frozenset[str] | set[str],
) -> list[dict[str, Any]]:
    """Find Tier C gaps that look actionable as Tier A/B (oral switch, renewal)."""
    encoded = {str(cid) for cid in encoded_clause_ids}
    promotions: list[dict[str, Any]] = []
    tier_c = gate_b_frame.filter(pl.col("encode_tier") == "C")
    for row in tier_c.iter_rows(named=True):
        clause_id = str(row.get("clause_id") or "")
        if clause_id in encoded:
            continue
        text = str(row.get("text_tr") or "")
        normalized = _normalize_tr(text)
        reasons: list[str] = []
        proposed_tier = ""
        if clause_id in _TIER_B_CLAUSE_IDS or _TIER_B_ORAL_SWITCH_RE.search(normalized):
            proposed_tier = "B"
            reasons.append("hbv_oral_switch_report")
        if reasons:
            promotions.append(
                {
                    "clause_id": clause_id,
                    "section_id": str(row.get("section_id") or ""),
                    "proposed_tier": proposed_tier,
                    "reasons": reasons,
                    "text_tr": text,
                }
            )
    return promotions


def audit_4213_gap_parity(
    clauses_path: Path,
    manifest: dict[str, Any],
    *,
    gate_b_frame: pl.DataFrame | None = None,
) -> dict[str, Any]:
    """Parity audit: every §4.2.13 coverage gap must be honestly traced."""
    gap_ids = _gap_clause_ids(clauses_path)
    statuses = _manifest_status_ids(manifest)
    trace_ids = {
        str(t.get("clause_id") or "")
        for t in manifest.get("clause_traces") or []
        if str(t.get("section_id") or "").startswith(_SECTION_PREFIX)
    }

    honest_gap_ids = (
        statuses["encoded"]
        | statuses["tier_c_deferred"]
        | statuses["tier_a_pending"]
        | statuses["tier_b_pending"]
    )
    untraced = sorted(gap_ids - honest_gap_ids)
    misclassified_ab = sorted(
        (statuses["tier_a_pending"] | statuses["tier_b_pending"]) & statuses["encoded"]
    )
    missing_from_traces = sorted(gap_ids - trace_ids)
    encoded_still_gap = sorted(gap_ids & statuses["encoded"])

    frame = gate_b_frame if gate_b_frame is not None else export_4213_candidates(clauses_path)
    export_ids = set(frame["clause_id"].to_list())
    gaps_missing_export = sorted(gap_ids - export_ids)

    promotions = scan_4213_tier_ab_promotions(
        frame,
        encoded_clause_ids=statuses["encoded"],
    )

    return {
        "gap_count": len(gap_ids),
        "encoded_count": len(statuses["encoded"]),
        "tier_b_pending_count": len(statuses["tier_b_pending"]),
        "tier_c_deferred_count": len(statuses["tier_c_deferred"]),
        "untraced_before": len(untraced) + len(misclassified_ab) + len(gaps_missing_export),
        "untraced_clause_ids": untraced,
        "misclassified_ab_gap_ids": misclassified_ab,
        "missing_from_traces": missing_from_traces,
        "gaps_missing_export": gaps_missing_export,
        "encoded_still_gap": encoded_still_gap,
        "promotion_candidates": promotions,
        "promotion_count": len(promotions),
    }


def run_4213_audit(
    clauses_path: Path,
    rules_path: Path,
    *,
    effective_date: str,
) -> dict[str, Any]:
    """Full §4.2.13 audit: parity before/after manifest build."""
    payload = json.loads(rules_path.read_text(encoding="utf-8"))
    rules_4213 = [
        rule
        for rule in (payload.get("rules") or [])
        if str(rule.get("sut_section") or "").startswith(_SECTION_PREFIX)
    ]
    frame = export_4213_candidates(clauses_path)
    before_manifest = build_4213_manifest(frame, rules_4213, effective_date=effective_date)
    before = audit_4213_gap_parity(clauses_path, before_manifest, gate_b_frame=frame)

    promotions = scan_4213_tier_ab_promotions(
        frame,
        encoded_clause_ids=_manifest_status_ids(before_manifest)["encoded"],
    )
    promoted_ids = sorted({p["clause_id"] for p in promotions})

    after_manifest = build_4213_manifest(frame, rules_4213, effective_date=effective_date)
    after = audit_4213_gap_parity(clauses_path, after_manifest, gate_b_frame=frame)

    return {
        "untraced_before": before["untraced_before"],
        "untraced_after": after["untraced_before"],
        "repaired_untraced": max(0, before["untraced_before"] - after["untraced_before"]),
        "promoted_clause_ids": promoted_ids,
        "promotion_count": len(promoted_ids),
        "gap_count": after["gap_count"],
        "encoded_count": after["encoded_count"],
        "tier_b_pending_count": after["tier_b_pending_count"],
        "tier_c_deferred_count": after["tier_c_deferred_count"],
        "promotion_candidates": promotions,
    }


def gate_b_summary(enriched: pl.DataFrame) -> dict[str, int]:
    if enriched.is_empty():
        return {"total": 0}
    summary: dict[str, int] = {"total": enriched.height}
    for col in ("encode_tier", "encode_priority"):
        for key, count in enriched.group_by(col).len().iter_rows():
            summary[f"{col}:{key}"] = int(count)
    return summary


def _load_rules_for_sections(rules_path: Path, prefixes: tuple[str, ...]) -> list[dict[str, Any]]:
    payload = json.loads(rules_path.read_text(encoding="utf-8"))
    return [
        rule
        for rule in (payload.get("rules") or [])
        if any(str(rule.get("sut_section") or "").startswith(prefix) for prefix in prefixes)
    ]


def write_gate_b_artifacts(
    *,
    clauses_path: Path,
    rules_path: Path,
    corpus_csv: Path,
    shared_manifest_path: Path,
    effective_date: str,
) -> tuple[pl.DataFrame, dict[str, Any], dict[str, Any]]:
    rules_4213 = _load_rules_for_sections(rules_path, (_SECTION_PREFIX,))
    rules_4213_4216 = _load_rules_for_sections(rules_path, ("4.2.13", "4.2.16"))

    manifest_4213 = build_4213_manifest(
        export_4213_candidates(clauses_path),
        rules_4213,
        effective_date=effective_date,
    )
    encoded = frozenset(manifest_4213["gate_b_sources_encoded"])

    existing_shared: dict[str, Any] | None = None
    if shared_manifest_path.is_file():
        existing_shared = json.loads(shared_manifest_path.read_text(encoding="utf-8"))

    shared_manifest = merge_4213_into_shared_manifest(
        manifest_4213,
        existing_shared,
        rules_4213_4216,
        effective_date=effective_date,
    )

    corpus_csv.parent.mkdir(parents=True, exist_ok=True)
    shared_manifest_path.parent.mkdir(parents=True, exist_ok=True)

    frame = export_4213_candidates(clauses_path, encoded_clause_ids=encoded)
    frame.write_csv(corpus_csv)
    shared_manifest_path.write_text(
        json.dumps(shared_manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return frame, manifest_4213, shared_manifest


if __name__ == "__main__":
    from datetime import date

    repo = _PROJECT_ROOT
    clauses = repo / "data/gazette/sut_clauses.parquet"
    rules = repo / "data/gazette/prose_rules/drug_indication_prose.json"
    corpus = repo / "data/gazette/prose_corpus/L4.2_drug_indication_4213.csv"
    manifest = repo / "data/gazette/prose_manifests/L4.2_drug_indication_4213_4216_manifest.json"

    frame, manifest_4213, shared = write_gate_b_artifacts(
        clauses_path=clauses,
        rules_path=rules,
        corpus_csv=corpus,
        shared_manifest_path=manifest,
        effective_date=date.today().isoformat(),
    )
    print(f"Wrote {frame.height} rows -> {corpus}")
    print(
        f"§4.2.13 manifest: encoded={manifest_4213['encoded_clause_count']} "
        f"tier_a_pending={manifest_4213['tier_a_pending_count']} "
        f"tier_c={manifest_4213['tier_c_deferred_count']}"
    )
    print(
        f"Shared manifest: encoded={shared['encoded_clause_count']} "
        f"tier_a_pending={shared['tier_a_pending_count']} "
        f"tier_c={shared['tier_c_deferred_count']} -> {manifest}"
    )
    for key, value in sorted(gate_b_summary(frame).items()):
        print(f"  {key}: {value}")
