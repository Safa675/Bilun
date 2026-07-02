#!/usr/bin/env python3
"""Audit prose manifest bucket lists against clause_traces (source of truth)."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_DEFAULT_MANIFEST_DIR = _REPO / "data/gazette/prose_manifests"

_STATUS_TO_LIST_KEY: dict[str, str] = {
    "encoded": "encoded_clause_ids",
    "tier_c_deferred": "tier_c_deferred_clause_ids",
    "emr_blocked": "emr_blocked_clause_ids",
    "non_actionable": "non_actionable_clause_ids",
    "tier_a_pending": "tier_a_pending_clause_ids",
    "tier_b_pending": "tier_b_pending_clause_ids",
}

_BUCKET_LIST_KEYS: tuple[str, ...] = tuple(_STATUS_TO_LIST_KEY.values())


@dataclass
class ManifestParityIssue:
    manifest: str
    kind: str
    detail: str
    sample_ids: list[str] = field(default_factory=list)


@dataclass
class ManifestParityReport:
    manifests_scanned: int = 0
    manifests_with_traces: int = 0
    issues: list[ManifestParityIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues


def _trace_index(payload: dict[str, Any] | list[Any]) -> dict[str, dict[str, Any]]:
    if not isinstance(payload, dict):
        return {}  # list-type manifests (header clause-id arrays) have no traces
    traces = payload.get("clause_traces")
    if isinstance(traces, list):
        return {str(t.get("clause_id")): t for t in traces if isinstance(t, dict) and t.get("clause_id")}
    if isinstance(traces, dict):
        return {str(k): v for k, v in traces.items() if isinstance(v, dict)}
    return {}


def audit_manifest_payload(manifest_name: str, payload: Any) -> list[ManifestParityIssue]:
    """Return parity issues for a single manifest JSON payload."""
    if not isinstance(payload, dict):
        return []  # non-dict manifests (e.g. header clause-id arrays) have no traces to audit
    issues: list[ManifestParityIssue] = []
    trace_by_id = _trace_index(payload)
    if not trace_by_id:
        return issues

    trace_ids = set(trace_by_id)
    status_counts: dict[str, int] = {}
    for clause_id, trace in trace_by_id.items():
        status = str(trace.get("manifest_status") or "")
        status_counts[status] = status_counts.get(status, 0) + 1
        list_key = _STATUS_TO_LIST_KEY.get(status)
        if list_key is None:
            issues.append(
                ManifestParityIssue(
                    manifest=manifest_name,
                    kind="unknown_trace_status",
                    detail=f"clause {clause_id} has unmapped manifest_status={status!r}",
                    sample_ids=[clause_id],
                )
            )
            continue
        bucket_ids = {str(c) for c in (payload.get(list_key) or [])}
        if clause_id not in bucket_ids:
            issues.append(
                ManifestParityIssue(
                    manifest=manifest_name,
                    kind="trace_missing_from_list",
                    detail=f"{clause_id} status={status} not in {list_key}",
                    sample_ids=[clause_id],
                )
            )

    union_list_ids: set[str] = set()
    for list_key in _BUCKET_LIST_KEYS:
        ids = {str(c) for c in (payload.get(list_key) or [])}
        stale = sorted(ids - trace_ids)
        if stale:
            issues.append(
                ManifestParityIssue(
                    manifest=manifest_name,
                    kind="stale_list_ids",
                    detail=f"{len(stale)} id(s) in {list_key} not present in clause_traces",
                    sample_ids=stale[:5],
                )
            )
        wrong_status: list[str] = []
        for clause_id in ids & trace_ids:
            expected_key = _STATUS_TO_LIST_KEY.get(str(trace_by_id[clause_id].get("manifest_status") or ""))
            if expected_key != list_key:
                wrong_status.append(clause_id)
        if wrong_status:
            issues.append(
                ManifestParityIssue(
                    manifest=manifest_name,
                    kind="list_status_mismatch",
                    detail=f"{len(wrong_status)} id(s) in {list_key} with different trace status",
                    sample_ids=sorted(wrong_status)[:5],
                )
            )
        union_list_ids |= ids

    if union_list_ids != trace_ids:
        only_lists = sorted(union_list_ids - trace_ids)
        only_traces = sorted(trace_ids - union_list_ids)
        if only_lists or only_traces:
            issues.append(
                ManifestParityIssue(
                    manifest=manifest_name,
                    kind="union_mismatch",
                    detail=(
                        f"union(bucket_lists)={len(union_list_ids)} vs traces={len(trace_ids)} "
                        f"(only_in_lists={len(only_lists)}, only_in_traces={len(only_traces)})"
                    ),
                    sample_ids=(only_lists or only_traces)[:5],
                )
            )

    for list_key, count_key in (
        ("encoded_clause_ids", "encoded_clause_count"),
        ("tier_c_deferred_clause_ids", "tier_c_deferred_count"),
        ("emr_blocked_clause_ids", "emr_blocked_count"),
        ("non_actionable_clause_ids", "non_actionable_count"),
        ("tier_a_pending_clause_ids", "tier_a_pending_count"),
        ("tier_b_pending_clause_ids", "tier_b_pending_count"),
    ):
        actual = len(payload.get(list_key) or [])
        declared = payload.get(count_key)
        if declared is not None and int(declared) != actual:
            issues.append(
                ManifestParityIssue(
                    manifest=manifest_name,
                    kind="count_field_drift",
                    detail=f"{count_key}={declared} but len({list_key})={actual}",
                )
            )

    section_total = payload.get("section_clause_total")
    if section_total is not None and len(trace_by_id) != int(section_total):
        issues.append(
            ManifestParityIssue(
                manifest=manifest_name,
                kind="trace_total_mismatch",
                detail=f"section_clause_total={section_total} but len(clause_traces)={len(trace_by_id)}",
            )
        )

    if payload.get("clause_trace_complete") and issues:
        issues.append(
            ManifestParityIssue(
                manifest=manifest_name,
                kind="false_complete_flag",
                detail="clause_trace_complete=true but parity checks failed",
            )
        )

    return issues


def audit_manifest_path(path: Path) -> list[ManifestParityIssue]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return audit_manifest_payload(path.name, payload)


def audit_manifest_dir(
    manifest_dir: Path = _DEFAULT_MANIFEST_DIR,
    *,
    glob_pattern: str = "*.json",
) -> ManifestParityReport:
    report = ManifestParityReport()
    for path in sorted(manifest_dir.glob(glob_pattern)):
        report.manifests_scanned += 1
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not _trace_index(payload):
            continue
        report.manifests_with_traces += 1
        report.issues.extend(audit_manifest_payload(path.name, payload))
    return report


def audit_drug_manifests(manifest_dir: Path = _DEFAULT_MANIFEST_DIR) -> ManifestParityReport:
    """Audit L4.2 drug + anti-VEGF manifests that carry clause_traces."""
    report = ManifestParityReport()
    patterns = ("L4.2_drug_indication_*.json", "L4.33_anti_vegf_*.json")
    seen: set[Path] = set()
    for pattern in patterns:
        for path in sorted(manifest_dir.glob(pattern)):
            if path in seen:
                continue
            seen.add(path)
            report.manifests_scanned += 1
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not _trace_index(payload):
                continue
            report.manifests_with_traces += 1
            report.issues.extend(audit_manifest_payload(path.name, payload))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest-dir",
        type=Path,
        default=_DEFAULT_MANIFEST_DIR,
        help="Directory containing prose manifest JSON files",
    )
    parser.add_argument(
        "--drug-only",
        action="store_true",
        help="Only audit L4.2 drug + L4.33 anti-VEGF manifests",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        help="Write full report JSON to this path",
    )
    args = parser.parse_args()

    report = (
        audit_drug_manifests(args.manifest_dir)
        if args.drug_only
        else audit_manifest_dir(args.manifest_dir)
    )
    payload = {
        "ok": report.ok,
        "manifests_scanned": report.manifests_scanned,
        "manifests_with_traces": report.manifests_with_traces,
        "issue_count": len(report.issues),
        "issues": [asdict(i) for i in report.issues],
    }
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
