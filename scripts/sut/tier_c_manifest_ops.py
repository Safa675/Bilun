"""Shared manifest updates for Tier-C bucket encode waves."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Literal

import polars as pl

import logging

from scripts.sut.close_algorithmic_gaps import _manifest_for_section
from scripts.sut.prose.drug_indication_gate_b import infer_defer_themes
from scripts.sut.prose.manifest_reconcile import reconcile_manifest_payload

_logger = logging.getLogger(__name__)

_REPO = Path(__file__).resolve().parents[2]
_MANIFEST_DIR = _REPO / "data/gazette/prose_manifests"
_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"

BucketStatus = Literal["encoded", "emr_blocked", "non_actionable"]


from scripts.sut.prose.manifest_index import trace_index_with_shape, write_traces
def _group_by_manifest(clause_ids: set[str], clauses_path: Path = _CLAUSES) -> dict[str, list[str]]:
    clauses = pl.read_parquet(clauses_path).filter(pl.col("is_in_force"))
    section_by_id = {str(r["clause_id"]): str(r["section_id"]) for r in clauses.iter_rows(named=True)}
    by_manifest: dict[str, list[str]] = defaultdict(list)
    for clause_id in clause_ids:
        section = section_by_id.get(clause_id, "")
        by_manifest[_manifest_for_section(section)].append(clause_id)
    return dict(by_manifest)


def update_manifest_bucket(
    clause_ids: set[str],
    *,
    status: BucketStatus,
    clause_to_rules: dict[str, list[str]] | None = None,
    clauses_path: Path = _CLAUSES,
    note_prefix: str,
) -> dict[str, int]:
    """Move clause IDs between tier-C deferral and encoded / emr_blocked / non_actionable."""
    if not clause_ids:
        return {"manifests_touched": 0, "clauses_updated": 0}

    by_manifest = _group_by_manifest(clause_ids, clauses_path)
    clause_text: dict[str, str] = {}
    if status == "emr_blocked":
        frame = pl.read_parquet(clauses_path).filter(pl.col("is_in_force"))
        clause_text = {
            str(r["clause_id"]): str(r.get("in_force_text") or r.get("text_tr") or "")
            for r in frame.iter_rows(named=True)
        }

    stats: dict[str, int | list[str]] = {
        "manifests_touched": 0,
        "clauses_updated": 0,
        "skipped_manifests": [],
    }
    tier_key = {"encoded": "B", "emr_blocked": "C", "non_actionable": "D"}[status]

    for manifest_name, ids in sorted(by_manifest.items()):
        path = _MANIFEST_DIR / manifest_name
        if not path.is_file():
            _logger.warning("tier_c_manifest_ops: missing manifest %s (%d clauses)", manifest_name, len(ids))
            stats["skipped_manifests"].append(manifest_name)  # type: ignore[union-attr]
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        tier_c = {str(c) for c in (payload.get("tier_c_deferred_clause_ids") or [])}
        encoded = {str(c) for c in (payload.get("encoded_clause_ids") or [])}
        emr = {str(c) for c in (payload.get("emr_blocked_clause_ids") or [])}
        non_actionable = {str(c) for c in (payload.get("non_actionable_clause_ids") or [])}

        traces, trace_by_id = trace_index_with_shape(payload)
        updated = 0
        for clause_id in sorted(set(ids)):
            dirty = False
            if clause_id in tier_c:
                tier_c.discard(clause_id)
                dirty = True

            if status == "encoded":
                if clause_id not in encoded:
                    encoded.add(clause_id)
                    dirty = True
                emr.discard(clause_id)
                non_actionable.discard(clause_id)
            elif status == "emr_blocked":
                if clause_id not in emr:
                    emr.add(clause_id)
                    dirty = True
                encoded.discard(clause_id)
                non_actionable.discard(clause_id)
            else:
                if clause_id not in non_actionable:
                    non_actionable.add(clause_id)
                    dirty = True
                encoded.discard(clause_id)
                emr.discard(clause_id)

            if not dirty and clause_id not in trace_by_id:
                continue
            updated += 1

            if clause_id in trace_by_id:
                trace = trace_by_id[clause_id]
                trace["manifest_status"] = status
                trace["encode_tier"] = tier_key
                if status == "encoded":
                    trace["linked_rule_ids"] = sorted(
                        set(trace.get("linked_rule_ids") or [])
                        | set((clause_to_rules or {}).get(clause_id, []))
                    )
                    trace.pop("defer_themes", None)
                    trace.pop("defer_reason", None)
                elif status == "emr_blocked":
                    text = clause_text.get(clause_id, "")
                    themes = infer_defer_themes(text) or ["clinical_pathway"]
                    trace["defer_themes"] = themes
                    trace["defer_reason"] = (
                        "EMR-blocked — clinical assessment fields (ECOG, mutation panel, "
                        "response/progression) required; not encodable on DrugClaimLine alone."
                    )
                    trace.pop("linked_rule_ids", None)
                else:
                    trace["defer_reason"] = (
                        "Non-actionable — structural heading, pathway fragment, or "
                        "navigational prose without encodable billing matcher."
                    )
                    trace.pop("defer_themes", None)
                    trace.pop("linked_rule_ids", None)

        if updated == 0:
            continue

        payload["tier_c_deferred_clause_ids"] = sorted(tier_c)
        payload["tier_c_deferred_count"] = len(tier_c)
        payload["encoded_clause_ids"] = sorted(encoded)
        payload["encoded_clause_count"] = len(encoded)
        payload["emr_blocked_clause_ids"] = sorted(emr)
        payload["emr_blocked_count"] = len(emr)
        write_traces(payload, traces, trace_by_id)
        reconcile_manifest_payload(payload, backfill=True)
        payload[f"{note_prefix}_note"] = f"{note_prefix} updated {updated} clause(s) on {date.today().isoformat()}"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        stats["manifests_touched"] += 1
        stats["clauses_updated"] += updated
    return stats
