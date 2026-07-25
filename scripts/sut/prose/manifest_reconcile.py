#!/usr/bin/env python3
"""Rebuild manifest bucket ID lists from clause_traces (source of truth)."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.audit_manifest_parity import (  # noqa: E402
    _BUCKET_LIST_KEYS,
    _STATUS_TO_LIST_KEY,
    audit_manifest_payload,
)
from scripts.sut.prose.drug_indication_gate_b import infer_defer_themes  # noqa: E402
from scripts.sut.prose.gate_b_generic import build_defer_reason  # noqa: E402

_MANIFEST_DIR = _PROJECT_ROOT / "data/gazette/prose_manifests"

_DEFER_REASON_BY_STATUS: dict[str, str] = {
    "emr_blocked": (
        "EMR-blocked — clinical assessment fields (ECOG, mutation panel, "
        "response/progression) required; not encodable on DrugClaimLine alone."
    ),
    "non_actionable": (
        "Non-actionable — structural heading, pathway fragment, or "
        "navigational prose without encodable billing matcher."
    ),
}


from scripts.sut.prose.manifest_index import trace_index_with_shape, write_traces  # noqa: E402
def _backfill_trace_metadata(trace: dict[str, Any]) -> None:
    status = str(trace.get("manifest_status") or "")
    text = str(trace.get("text_tr") or trace.get("text_excerpt") or "")

    if status == "tier_c_deferred":
        if not trace.get("defer_themes"):
            trace["defer_themes"] = infer_defer_themes(text) or ["clinical_pathway"]
        if not trace.get("defer_reason"):
            trace["defer_reason"] = build_defer_reason(list(trace.get("defer_themes") or []))
    elif status in _DEFER_REASON_BY_STATUS:
        if not trace.get("defer_reason"):
            trace["defer_reason"] = _DEFER_REASON_BY_STATUS[status]
        if status == "emr_blocked" and not trace.get("defer_themes"):
            trace["defer_themes"] = infer_defer_themes(text) or ["clinical_pathway"]
    elif status == "encoded":
        trace.pop("defer_themes", None)
        trace.pop("defer_reason", None)


def reconcile_manifest_payload(payload: dict[str, Any], *, backfill: bool = True) -> dict[str, int]:
    """Rebuild bucket lists from traces. Returns per-bucket counts."""
    traces, trace_by_id = trace_index_with_shape(payload)
    if not trace_by_id:
        return {}

    buckets: dict[str, list[str]] = {key: [] for key in _BUCKET_LIST_KEYS}

    for clause_id in sorted(trace_by_id):
        trace = trace_by_id[clause_id]
        if backfill:
            _backfill_trace_metadata(trace)
        status = str(trace.get("manifest_status") or "")
        list_key = _STATUS_TO_LIST_KEY.get(status)
        if list_key is None:
            continue
        buckets[list_key].append(clause_id)

    for list_key, ids in buckets.items():
        payload[list_key] = ids

    # Canonical-v1: drop the legacy gate_b_sources_encoded alias entirely.
    payload.pop("gate_b_sources_encoded", None)

    payload["encoded_clause_count"] = len(buckets["encoded_clause_ids"])
    payload["tier_c_deferred_count"] = len(buckets["tier_c_deferred_clause_ids"])
    payload["emr_blocked_count"] = len(buckets["emr_blocked_clause_ids"])
    payload["non_actionable_count"] = len(buckets["non_actionable_clause_ids"])
    payload["tier_a_pending_count"] = len(buckets["tier_a_pending_clause_ids"])
    payload["tier_b_pending_count"] = len(buckets["tier_b_pending_clause_ids"])

    # Legacy alias used in §4.2.14.C header
    payload["encode_tier_C_deferred_count"] = payload["tier_c_deferred_count"]

    trace_total = len(trace_by_id)
    payload["section_clause_total"] = trace_total
    parity_issues = audit_manifest_payload("__inline__", payload)
    payload["clause_trace_complete"] = not parity_issues
    if parity_issues:
        payload["parity_errors"] = [asdict(i) for i in parity_issues]
    else:
        payload.pop("parity_errors", None)

    section_total = trace_total
    if section_total:
        payload["manifest_coverage_pct"] = round(100.0 * trace_total / section_total, 1)
    payload["encoded_clause_pct"] = (
        round(100.0 * payload["encoded_clause_count"] / section_total, 1) if section_total else 0.0
    )

    write_traces(payload, traces, trace_by_id)
    return {key: len(ids) for key, ids in buckets.items()}


def reconcile_manifest_path(path: Path, *, write: bool = True, backfill: bool = True) -> dict[str, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    counts = reconcile_manifest_payload(payload, backfill=backfill)
    if write and counts:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return counts


@dataclass
class ReconcileRunReport:
    manifests_touched: int = 0
    manifests_skipped: int = 0
    per_manifest: dict[str, dict[str, int]] = field(default_factory=dict)
    skipped_missing: list[str] = field(default_factory=list)


def reconcile_drug_manifests(
    manifest_dir: Path = _MANIFEST_DIR,
    *,
    write: bool = True,
    backfill: bool = True,
) -> ReconcileRunReport:
    report = ReconcileRunReport()
    patterns = ("L4.2_drug_indication_*.json", "L4.33_anti_vegf_*.json")
    seen: set[Path] = set()
    for pattern in patterns:
        for path in sorted(manifest_dir.glob(pattern)):
            if path in seen:
                continue
            seen.add(path)
            payload = json.loads(path.read_text(encoding="utf-8"))
            _, trace_by_id = trace_index_with_shape(payload)
            if not trace_by_id:
                report.manifests_skipped += 1
                continue
            counts = reconcile_manifest_path(path, write=write, backfill=backfill)
            report.manifests_touched += 1
            report.per_manifest[path.name] = counts
    return report


def write_reconciled_manifest(
    path: Path,
    payload: dict[str, Any],
    *,
    backfill: bool = True,
) -> dict[str, int]:
    """Reconcile bucket lists from traces, then persist manifest JSON."""
    counts = reconcile_manifest_payload(payload, backfill=backfill)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-dir", type=Path, default=_MANIFEST_DIR)
    parser.add_argument("--dry-run", action="store_true", help="Do not write manifest files")
    parser.add_argument("--no-backfill", action="store_true")
    args = parser.parse_args()

    report = reconcile_drug_manifests(
        args.manifest_dir,
        write=not args.dry_run,
        backfill=not args.no_backfill,
    )
    print(
        json.dumps(
            {
                "manifests_touched": report.manifests_touched,
                "manifests_skipped": report.manifests_skipped,
                "dry_run": args.dry_run,
                "per_manifest": report.per_manifest,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
