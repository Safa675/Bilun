"""A1 — §4.2.14.C manifest trace verification and repair (R5 Epic A Phase 2)."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import polars as pl

from scripts.sut.prose.drug_indication_gate_b import (
    export_4_2_14_c_candidates,
    gate_b_summary,
    infer_defer_themes,
)
from scripts.sut.prose.drug_indication_manifest import (
    build_defer_reason,
    build_phase5_manifest,
)

_REPO = Path(__file__).resolve().parents[3]
_SECTION_ID = "4.2.14.C"
_CLAUSES_PATH = _REPO / "data/gazette/sut_clauses.parquet"
_MANIFEST_PATH = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4.2.14.C_manifest.json"
_RULES_PATH = _REPO / "data/gazette/prose_rules/drug_indication_prose.json"

_EMR_SIGNAL_RE = re.compile(
    r"\becog\b|pd-?l1|egfr|\balk\b|ros1|mutasyon|karnofsky|performans skor",
    re.I,
)
_NON_ACTIONABLE_TYPES = frozenset({"chapter", "section_heading", "amendment"})


def load_4214c_clause_frame(clauses_path: Path | None = None) -> pl.DataFrame:
    path = clauses_path or _CLAUSES_PATH
    return pl.read_parquet(path).filter(pl.col("section_id") == _SECTION_ID)


def in_force_4214c_clause_ids(clauses_path: Path | None = None) -> frozenset[str]:
    frame = load_4214c_clause_frame(clauses_path)
    return frozenset(frame.filter(pl.col("is_in_force"))["clause_id"].to_list())


def gate_b_4214c_clause_ids(
    clauses_path: Path | None = None,
    *,
    rules_path: Path | None = None,
) -> frozenset[str]:
    frame = export_4_2_14_c_candidates(
        clauses_path or _CLAUSES_PATH,
        rules_path=rules_path or _RULES_PATH,
    )
    return frozenset(frame["clause_id"].to_list())


from scripts.sut.prose.manifest_index import traced_clause_ids


def manifest_traced_clause_ids(manifest: dict[str, Any]) -> frozenset[str]:
    """Union of encoded + tier_C_deferred + emr_blocked (+ non_actionable when present)."""
    return traced_clause_ids(manifest)


def manifest_coverage_gap(
    manifest: dict[str, Any] | None = None,
    *,
    clauses_path: Path | None = None,
    in_force_only: bool = True,
) -> dict[str, Any]:
    """Compare parquet clause IDs against manifest trace buckets."""
    manifest = manifest or json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    section = load_4214c_clause_frame(clauses_path)
    if in_force_only:
        canonical = frozenset(section.filter(pl.col("is_in_force"))["clause_id"].to_list())
    else:
        canonical = gate_b_4214c_clause_ids(clauses_path)

    traced = manifest_traced_clause_ids(manifest)
    encoded = frozenset(str(c) for c in (manifest.get("encoded_clause_ids") or []))
    tier_c = frozenset(str(c) for c in (manifest.get("tier_c_deferred_clause_ids") or []))
    emr = frozenset(str(c) for c in (manifest.get("emr_blocked_clause_ids") or []))

    return {
        "canonical_count": len(canonical),
        "traced_count": len(traced & canonical),
        "missing_clause_ids": sorted(canonical - traced),
        "extra_clause_ids": sorted(traced - canonical),
        "encoded_count": len(encoded & canonical),
        "tier_c_deferred_count": len(tier_c & canonical),
        "emr_blocked_count": len(emr & canonical),
        "gate_b_total": export_4_2_14_c_candidates(clauses_path or _CLAUSES_PATH).height,
    }


def _is_emr_blocked_row(row: dict[str, Any]) -> bool:
    text = str(row.get("text_tr") or row.get("in_force_text") or "")
    if _EMR_SIGNAL_RE.search(text):
        return True
    themes = infer_defer_themes(text)
    return bool({"ecog", "mutation_panel", "response_assessment"} & set(themes))


def _is_non_actionable_row(row: dict[str, Any]) -> bool:
    clause_type = str(row.get("clause_type") or "")
    deontic = row.get("deontic_modality")
    if clause_type in _NON_ACTIONABLE_TYPES and not deontic:
        return True
    if not row.get("is_in_force", True):
        return True
    if clause_type == "bent" and not deontic:
        return True
    text = str(row.get("text_tr") or "").strip()
    if clause_type in {"prose", "numbered_item"} and len(text) < 40 and not deontic:
        return True
    return False


def _rebuild_clause_traces(
    *,
    section_frame: pl.DataFrame,
    encoded: set[str],
    tier_a: set[str],
    tier_b: set[str],
    tier_c: set[str],
    emr: set[str],
    non_actionable: set[str],
    rules_by_clause: dict[str, list[str]],
    gate_b_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    traces: list[dict[str, Any]] = []
    in_force = section_frame.filter(pl.col("is_in_force")).sort("clause_id")
    for row in in_force.iter_rows(named=True):
        clause_id = str(row["clause_id"])
        gb = gate_b_by_id.get(clause_id, {})
        encode_tier = str(gb.get("encode_tier") or "C")
        text = str(row.get("text_tr") or "")

        if clause_id in encoded:
            status = "encoded"
        elif clause_id in tier_a:
            status = "tier_a_pending"
        elif clause_id in tier_b:
            status = "tier_b_pending"
        elif clause_id in emr:
            status = "emr_blocked"
        elif clause_id in non_actionable:
            status = "non_actionable"
        else:
            status = "tier_c_deferred"

        entry: dict[str, Any] = {
            "clause_id": clause_id,
            "encode_tier": encode_tier,
            "manifest_status": status,
            "heuristic_inn": str(gb.get("heuristic_inn") or ""),
        }
        if status == "encoded":
            entry["linked_rule_ids"] = rules_by_clause.get(clause_id, [])
        elif status == "tier_c_deferred":
            themes = infer_defer_themes(text)
            entry["defer_themes"] = themes
            entry["defer_reason"] = build_defer_reason(themes)
        elif status == "emr_blocked":
            themes = infer_defer_themes(text)
            entry["defer_themes"] = themes
            entry["defer_reason"] = (
                "EMR-blocked — clinical assessment fields (ECOG, mutation panel, "
                "response/progression) required; not encodable on DrugClaimLine alone."
            )
        elif status == "non_actionable":
            entry["defer_reason"] = (
                "Non-actionable — structural heading, struck/superseded row, or "
                "navigational prose without deontic billing signal."
            )
        traces.append(entry)
    return traces


def repair_4214c_manifest(
    *,
    clauses_path: Path | None = None,
    rules_path: Path | None = None,
    manifest_path: Path | None = None,
    effective_date: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Rebuild §4.2.14.C manifest with 100% in-force clause trace coverage."""
    clauses_path = clauses_path or _CLAUSES_PATH
    rules_path = rules_path or _RULES_PATH
    manifest_path = manifest_path or _MANIFEST_PATH
    effective_date = effective_date or date.today().isoformat()

    existing: dict[str, Any] = {}
    if manifest_path.is_file():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))

    rules_payload = json.loads(rules_path.read_text(encoding="utf-8"))
    rules = list(rules_payload.get("rules") or [])
    gate_b_frame = export_4_2_14_c_candidates(clauses_path, rules_path=rules_path)
    base = build_phase5_manifest(
        gate_b_frame=gate_b_frame,
        rules=rules,
        phase1_added=existing.get("rules_added_phase1", 0),
        phase2_added=existing.get("rules_added_phase2", 0),
        batch_clause_ids=existing.get("batch_clause_ids") or {},
        gate_b_summary_payload=gate_b_summary(gate_b_frame),
        effective_date=effective_date,
    )

    encoded = {cid for cid in base["encoded_clause_ids"] if cid in in_force_4214c_clause_ids(clauses_path)}
    tier_a: set[str] = set()
    tier_b: set[str] = set()
    tier_c: set[str] = set()

    section_frame = load_4214c_clause_frame(clauses_path)
    in_force_ids = in_force_4214c_clause_ids(clauses_path)
    gate_b_by_id = {str(r["clause_id"]): r for r in gate_b_frame.iter_rows(named=True)}

    preserved_status: dict[str, str] = {}
    for trace in existing.get("clause_traces") or []:
        if not isinstance(trace, dict):
            continue
        clause_id = str(trace.get("clause_id") or "")
        status = str(trace.get("manifest_status") or "")
        if clause_id and status:
            preserved_status[clause_id] = status

    emr = {cid for cid, st in preserved_status.items() if st == "emr_blocked" and cid in in_force_ids}
    non_actionable = {
        cid for cid, st in preserved_status.items() if st == "non_actionable" and cid in in_force_ids
    }

    for clause_id in sorted(in_force_ids):
        if clause_id in encoded:
            continue
        if clause_id in emr or clause_id in non_actionable:
            continue
        if preserved_status.get(clause_id) == "tier_c_deferred":
            tier_c.add(clause_id)
            continue
        row = section_frame.filter(pl.col("clause_id") == clause_id).row(0, named=True)
        if _is_emr_blocked_row(row):
            emr.add(clause_id)
        elif _is_non_actionable_row(row):
            non_actionable.add(clause_id)
        else:
            tier_c.add(clause_id)

    encoded -= emr
    encoded -= non_actionable
    tier_c -= emr
    tier_c -= non_actionable

    rules_by_clause: dict[str, list[str]] = {}
    for rule in rules:
        rule_id = str(rule.get("rule_id") or "")
        for cid in rule.get("gate_b_sources") or []:
            rules_by_clause.setdefault(str(cid), []).append(rule_id)

    traces = _rebuild_clause_traces(
        section_frame=section_frame,
        encoded=encoded,
        tier_a=tier_a,
        tier_b=tier_b,
        tier_c=tier_c,
        emr=emr,
        non_actionable=non_actionable,
        rules_by_clause=rules_by_clause,
        gate_b_by_id=gate_b_by_id,
    )

    tier_c_manifest = [
        {
            "clause_id": row["clause_id"],
            "encode_tier": row["encode_tier"],
            "defer_themes": row.get("defer_themes") or infer_defer_themes(
                str(
                    section_frame.filter(pl.col("clause_id") == row["clause_id"])["text_tr"][0]
                    or ""
                )
            ),
            "defer_reason": row.get("defer_reason") or build_defer_reason([]),
            "heuristic_inn": row.get("heuristic_inn") or "",
        }
        for row in traces
        if row.get("manifest_status") == "tier_c_deferred"
    ]

    theme_summary: dict[str, int] = {}
    for row in tier_c_manifest:
        for theme in row.get("defer_themes") or []:
            theme_summary[str(theme)] = theme_summary.get(str(theme), 0) + 1

    section_total = len(traces)
    manifest = {
        **base,
        "section_clause_total": section_total,
        "clause_trace_complete": len(in_force_ids - manifest_traced_clause_ids_from_parts(
            encoded, tier_a, tier_b, tier_c, emr, non_actionable
        )) == 0,
        "manifest_coverage_pct": 100.0 if section_total else 0.0,
        "encoded_clause_ids": sorted(encoded),
        "encoded_clause_count": len(encoded),
        "tier_a_pending_clause_ids": sorted(tier_a),
        "tier_a_pending_count": len(tier_a),
        "tier_b_pending_clause_ids": sorted(tier_b),
        "tier_b_pending_count": len(tier_b),
        "tier_c_deferred_clause_ids": sorted(tier_c),
        "tier_c_deferred_count": len(tier_c),
        "encode_tier_C_deferred_count": len(tier_c),
        "emr_blocked_clause_ids": sorted(emr),
        "emr_blocked_count": len(emr),
        "non_actionable_clause_ids": sorted(non_actionable),
        "non_actionable_count": len(non_actionable),
        "tier_c_manifest": tier_c_manifest,
        "tier_c_defer_themes_summary": dict(
            sorted(theme_summary.items(), key=lambda item: (-item[1], item[0]))
        ),
        "clause_traces": traces,
        "emr_blocked_note": existing.get("emr_blocked_note")
        or (
            "EMR-blocked clauses require clinical assessment (ECOG, mutation panel, "
            "response/progression) not available on DrugClaimLine alone."
        ),
        "tier_c_manifest_note": (
            f"A1 repair — {len(tier_c)} tier-C deferred, {len(emr)} EMR-blocked, "
            f"{len(non_actionable)} non-actionable; {section_total} in-force traces "
            f"(lists synced from traces)."
        ),
    }

    gap = manifest_coverage_gap(manifest, clauses_path=clauses_path, in_force_only=True)
    manifest["a1_coverage_gap"] = gap

    from scripts.sut.prose.manifest_reconcile import reconcile_manifest_payload

    reconcile_manifest_payload(manifest, backfill=True)

    if not dry_run:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return manifest


def manifest_traced_clause_ids_from_parts(
    encoded: set[str],
    tier_a: set[str],
    tier_b: set[str],
    tier_c: set[str],
    emr: set[str],
    non_actionable: set[str],
) -> frozenset[str]:
    return frozenset(encoded | tier_a | tier_b | tier_c | emr | non_actionable)


def main() -> None:
    manifest = repair_4214c_manifest()
    gap = manifest["a1_coverage_gap"]
    print(f"A1 manifest repair: in_force={gap['canonical_count']} traced={gap['traced_count']}")
    print(
        f"  encoded={manifest['encoded_clause_count']} "
        f"tier_c={manifest['tier_c_deferred_count']} "
        f"emr={manifest['emr_blocked_count']} "
        f"non_actionable={manifest['non_actionable_count']}"
    )
    if gap["missing_clause_ids"]:
        print(f"  MISSING: {gap['missing_clause_ids'][:10]}...")
    else:
        print("  clause trace complete for in-force §4.2.14.C")


if __name__ == "__main__":
    main()
