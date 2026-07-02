"""§4.2.10 lysosomal storage disease Gate B — thin shim delegating to gate_b_generic.

Was ~565 lines; now delegates to the generic engine via gate_b_sections.py. The
honest-gap audit + Tier A/B promotion scan delegate to gate_b_audit.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl

from scripts.sut.prose.gate_b_audit import (
    audit_gap_parity as _audit_gap_parity,
    default_scan_promotions,
    gap_clause_ids as _gap_ids,
    repair_untraced as _repair,
)
from scripts.sut.prose.gate_b_shim import (
    shim_build_manifest,
    shim_export_candidates,
    shim_write_artifacts,
)

_SECTION = "4210"
_SECTION_PREFIX = "4.2.10"
_EXCLUDE_PREFIX = "4.2.100"


def export_4210_candidates(
    clauses_path: Path, *, encoded_clause_ids: frozenset[str] | None = None
) -> pl.DataFrame:
    return shim_export_candidates(_SECTION, clauses_path, encoded_clause_ids=encoded_clause_ids)


def build_4210_manifest(
    gate_b_frame: pl.DataFrame, rules: list[dict[str, Any]], *, effective_date: str
) -> dict[str, Any]:
    return shim_build_manifest(_SECTION, gate_b_frame, rules, effective_date=effective_date)


def _combined_4210_batch_rules() -> list[dict[str, Any]]:
    """Load the consolidated §4.2.10 batch rules (all sub-section clusters)."""
    from scripts.sut.rule_sources import load_drug_sections_rules

    return load_drug_sections_rules(
        [
            "4.2.10.A", "4.2.10.A-3", "4.2.10.A-4", "4.2.10.B-2", "4.2.10.B-3",
            "4.2.10.C-1", "4.2.10.C-2", "4.2.10.C-3", "4.2.10.D-2", "4.2.10.Ç-2",
        ]
    )


def scan_4210_tier_ab_promotions(
    gate_b_frame: pl.DataFrame, *, encoded_clause_ids: frozenset[str] | set[str]
) -> list[dict[str, Any]]:
    return default_scan_promotions(gate_b_frame, encoded_clause_ids)


def audit_4210_gap_parity(
    clauses_path: Path,
    manifest: dict[str, Any],
    *,
    gate_b_frame: pl.DataFrame | None = None,
) -> dict[str, Any]:
    return _audit_gap_parity(
        clauses_path,
        manifest,
        section_prefix=_SECTION_PREFIX,
        exclude_prefix=_EXCLUDE_PREFIX,
        frame=gate_b_frame,
        fallback_frame=lambda: export_4210_candidates(clauses_path),
        scan=lambda f, e: scan_4210_tier_ab_promotions(f, encoded_clause_ids=e),
    )


def run_4210_audit(
    clauses_path: Path, rules: list[dict[str, Any]], *, effective_date: str
) -> dict[str, Any]:
    frame = export_4210_candidates(clauses_path)
    manifest = build_4210_manifest(frame, rules, effective_date=effective_date)
    before = audit_4210_gap_parity(clauses_path, manifest, gate_b_frame=frame)
    manifest, repaired = _repair(
        manifest,
        frame,
        gap_ids=_gap_ids(clauses_path, _SECTION_PREFIX, exclude_prefix=_EXCLUDE_PREFIX),
    )
    after = audit_4210_gap_parity(clauses_path, manifest, gate_b_frame=frame)
    return {
        **after,
        "repaired_untraced": repaired,
        "untraced_before": before["untraced_before"],
        "untraced_after": len(after["untraced_clause_ids"]) + len(after["misclassified_ab_gap_ids"]),
    }


def write_gate_b_artifacts(
    *,
    clauses_path: Path,
    rules: list[dict[str, Any]],
    corpus_csv: Path,
    manifest_path: Path,
    effective_date: str,
) -> tuple[pl.DataFrame, dict[str, Any]]:
    return shim_write_artifacts(
        _SECTION,
        clauses_path=clauses_path,
        rules=rules,
        corpus_csv=corpus_csv,
        manifest_path=manifest_path,
        effective_date=effective_date,
    )
