"""§4.2.13 viral hepatitis Gate B — thin shim delegating to gate_b_generic.

Was ~640 lines; now delegates to the generic engine via gate_b_sections.py. The
§4.2.13 honest-gap audit delegates to gate_b_audit (section-scoped). The corpus is
written to its own CSV, while the manifest merges into the shared 4213+4216 file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polars as pl

from scripts.sut.prose.gate_b_audit import (
    audit_gap_parity as _audit_gap_parity,
    default_scan_promotions,
)
from scripts.sut.prose.gate_b_shim import (
    shim_build_manifest,
    shim_export_candidates,
    shim_write_artifacts,
)

_SECTION = "4213"
_SECTION_PREFIX = "4.2.13"


def export_4213_candidates(
    clauses_path: Path, *, encoded_clause_ids: frozenset[str] | None = None
) -> pl.DataFrame:
    return shim_export_candidates(_SECTION, clauses_path, encoded_clause_ids=encoded_clause_ids)


def build_4213_manifest(
    gate_b_frame: pl.DataFrame, rules: list[dict[str, Any]], *, effective_date: str
) -> dict[str, Any]:
    return shim_build_manifest(_SECTION, gate_b_frame, rules, effective_date=effective_date)


def scan_4213_tier_ab_promotions(
    gate_b_frame: pl.DataFrame, *, encoded_clause_ids: frozenset[str] | set[str]
) -> list[dict[str, Any]]:
    return default_scan_promotions(gate_b_frame, encoded_clause_ids)


def audit_4213_gap_parity(
    clauses_path: Path,
    manifest: dict[str, Any],
    *,
    gate_b_frame: pl.DataFrame | None = None,
) -> dict[str, Any]:
    return _audit_gap_parity(
        clauses_path,
        manifest,
        section_prefix=_SECTION_PREFIX,
        frame=gate_b_frame,
        fallback_frame=lambda: export_4213_candidates(clauses_path),
        scan=lambda f, e: scan_4213_tier_ab_promotions(f, encoded_clause_ids=e),
        scope_statuses=True,
        misclassified_against_encoded=True,
    )


def run_4213_audit(
    clauses_path: Path, rules_path: Path, *, effective_date: str
) -> dict[str, Any]:
    payload = json.loads(rules_path.read_text(encoding="utf-8"))
    rules_4213 = [
        r for r in (payload.get("rules") or [])
        if str(r.get("sut_section") or "").startswith(_SECTION_PREFIX)
    ]
    frame = export_4213_candidates(clauses_path)
    manifest = build_4213_manifest(frame, rules_4213, effective_date=effective_date)
    before = audit_4213_gap_parity(clauses_path, manifest, gate_b_frame=frame)
    return {
        **before,
        "untraced_before": before["untraced_before"],
        "untraced_after": len(before["untraced_clause_ids"]) + len(before["misclassified_ab_gap_ids"]),
        "repaired_untraced": 0,
        "promoted_clause_ids": sorted({p["clause_id"] for p in before["promotion_candidates"]}),
    }


def write_gate_b_artifacts(
    *,
    clauses_path: Path,
    corpus_csv: Path,
    shared_manifest_path: Path,
    effective_date: str,
    rules_path: Path | None = None,
    rules: list[dict[str, Any]] | None = None,
) -> tuple[pl.DataFrame, dict[str, Any]]:
    """Write corpus CSV; merge §4.2.13 traces into the shared 4213+4216 manifest."""
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    section = ALL_SECTIONS[_SECTION]
    if rules is None and rules_path is not None:
        payload = json.loads(rules_path.read_text(encoding="utf-8"))
        rules = [
            r for r in (payload.get("rules") or [])
            if any(str(r.get("sut_section") or "").startswith(p) for p in section.match.prefixes)
        ]
    rules = rules or []

    frame = shim_export_candidates(_SECTION, clauses_path)
    manifest = shim_build_manifest(_SECTION, frame, rules, effective_date=effective_date)

    corpus_csv.parent.mkdir(parents=True, exist_ok=True)
    shared_manifest_path.parent.mkdir(parents=True, exist_ok=True)

    # Merge §4.2.13 traces into the shared manifest, preserving existing §4.2.16 traces.
    shared: dict[str, Any] = {}
    if shared_manifest_path.is_file():
        shared = json.loads(shared_manifest_path.read_text(encoding="utf-8"))
    prior_traces = [
        t for t in (shared.get("clause_traces") or [])
        if not str(t.get("section_id") or "").startswith(_SECTION_PREFIX)
    ]
    merged_traces = prior_traces + list(manifest.get("clause_traces") or [])
    shared.update(manifest)
    shared["clause_traces"] = merged_traces

    frame_4213 = shim_export_candidates(
        _SECTION, clauses_path, encoded_clause_ids=frozenset(manifest["encoded_clause_ids"])
    )
    frame_4213.write_csv(corpus_csv)
    shared_manifest_path.write_text(
        json.dumps(shared, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return frame_4213, shared
