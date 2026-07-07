"""Phase 5 — full §4.2.14.C clause trace manifest (encoded + pending + Tier C deferred)."""

from __future__ import annotations

from typing import Any

import polars as pl

from scripts.sut.prose.drug_indication_gate_b import infer_defer_themes


def _rules_by_clause(rules: list[dict[str, Any]]) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for rule in rules:
        rule_id = str(rule.get("rule_id") or "")
        if not rule_id:
            continue
        for clause_id in rule.get("gate_b_sources") or []:
            cid = str(clause_id)
            index.setdefault(cid, [])
            if rule_id not in index[cid]:
                index[cid].append(rule_id)
    for clause_id in index:
        index[clause_id].sort()
    return index


def build_defer_reason(themes: list[str]) -> str:
    if not themes:
        return (
            "Deferred — multi-step clinical pathway not yet structurable on exact "
            "drug claim lines (Tier C manifest-only)."
        )
    labels = ", ".join(themes)
    return (
        f"Deferred — requires structured ingest for: {labels}. "
        "Batch encode when EMR/report fields support this pathway."
    )


def _manifest_status(
    *,
    clause_id: str,
    encode_tier: str,
    encoded_ids: set[str],
) -> str:
    if clause_id in encoded_ids:
        return "encoded"
    if encode_tier == "A":
        return "tier_a_pending"
    if encode_tier == "B":
        return "tier_b_pending"
    return "tier_c_deferred"


def build_clause_trace(
    gate_b_frame: pl.DataFrame,
    rules: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """One manifest row per §4.2.14.C clause (828 expected)."""
    encoded_ids: set[str] = set()
    for rule in rules:
        encoded_ids.update(str(cid) for cid in (rule.get("gate_b_sources") or []))

    rules_for_clause = _rules_by_clause(rules)
    traces: list[dict[str, Any]] = []

    for row in gate_b_frame.sort("clause_id").iter_rows(named=True):
        clause_id = str(row.get("clause_id") or "")
        encode_tier = str(row.get("encode_tier") or "C")
        text = str(row.get("text_tr") or "")
        status = _manifest_status(
            clause_id=clause_id,
            encode_tier=encode_tier,
            encoded_ids=encoded_ids,
        )
        themes = infer_defer_themes(text) if status == "tier_c_deferred" else []
        entry: dict[str, Any] = {
            "clause_id": clause_id,
            "encode_tier": encode_tier,
            "manifest_status": status,
            "heuristic_inn": str(row.get("heuristic_inn") or ""),
        }
        if status == "encoded":
            entry["linked_rule_ids"] = rules_for_clause.get(clause_id, [])
        elif status == "tier_c_deferred":
            entry["defer_themes"] = themes
            entry["defer_reason"] = build_defer_reason(themes)
        traces.append(entry)

    return traces


def _clause_ids_for_status(traces: list[dict[str, Any]], status: str) -> list[str]:
    return sorted(
        str(row["clause_id"])
        for row in traces
        if row.get("manifest_status") == status
    )


def _theme_summary(traces: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in traces:
        if row.get("manifest_status") != "tier_c_deferred":
            continue
        for theme in row.get("defer_themes") or []:
            counts[str(theme)] = counts.get(str(theme), 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _inn_named_coverage_pct(traces: list[dict[str, Any]]) -> float:
    inn_rows = [row for row in traces if str(row.get("heuristic_inn") or "").strip()]
    if not inn_rows:
        return 0.0
    covered = [
        row
        for row in inn_rows
        if row.get("manifest_status") in {"encoded", "tier_a_pending", "tier_b_pending"}
    ]
    return round(100.0 * len(covered) / len(inn_rows), 1)


def build_phase5_manifest(
    *,
    gate_b_frame: pl.DataFrame,
    rules: list[dict[str, Any]],
    phase1_added: int,
    phase2_added: int,
    batch_clause_ids: dict[str, list[str]],
    gate_b_summary_payload: dict[str, int],
    effective_date: str,
) -> dict[str, Any]:
    traces = build_clause_trace(gate_b_frame, rules)
    section_total = gate_b_frame.height

    encoded_ids = _clause_ids_for_status(traces, "encoded")
    tier_a_pending = _clause_ids_for_status(traces, "tier_a_pending")
    tier_b_pending = _clause_ids_for_status(traces, "tier_b_pending")
    tier_c_deferred = _clause_ids_for_status(traces, "tier_c_deferred")

    return {
        "manifest_version": "canonical-v1",
        "section_id": "4.2.14.C",
        "effective_date": effective_date,
        "rule_set_id": "drug_indication_4.2.14.C",
        "rules_in_json": len(rules),
        "section_clause_total": section_total,
        "encoded_clause_count": len(encoded_ids),
        "tier_a_pending_count": len(tier_a_pending),
        "tier_b_pending_count": len(tier_b_pending),
        "tier_c_deferred_count": len(tier_c_deferred),
        "encoded_clause_ids": encoded_ids,
        "tier_a_pending_clause_ids": tier_a_pending,
        "tier_b_pending_clause_ids": tier_b_pending,
        "tier_c_deferred_clause_ids": tier_c_deferred,
        "emr_blocked_clause_ids": [],
        "non_actionable_clause_ids": [],
        "emr_blocked_count": 0,
        "non_actionable_count": 0,
        "clause_traces": traces,
    }
