"""§4.2.1 rheumatology/biologic Gate B — thin shim delegating to gate_b_generic.

This file was ~680 lines of duplicate logic; now delegates to the generic engine
via the config table in gate_b_sections.py. The audit/scan/repair helpers delegate
to gate_b_audit, which preserves the rich audit schema the tests assert on.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import polars as pl

from scripts.sut.prose.gate_b_audit import (
    audit_gap_parity as _audit_gap_parity,
    gap_clause_ids as _gap_ids,
    in_force_clause_ids as _in_force_ids,
    normalize_defer_reasons as _normalize_defer,
    repair_untraced as _repair,
)
from scripts.sut.prose.gate_b_sections import ALL_SECTIONS
from scripts.sut.prose.gate_b_shim import (
    shim_build_manifest,
    shim_export_candidates,
    shim_write_artifacts,
)

_SECTION = "4201"
_SECTION_PREFIX = "4.2.1"


def is_421_proper(section_id: str) -> bool:
    """True for §4.2.1 proper — excludes 4.2.10–4.2.19 false prefix matches."""
    return ALL_SECTIONS[_SECTION].match.matches(section_id)


def _in_force_clause_ids(clauses_path: Path) -> frozenset[str]:
    """In-force §4.2.1 proper clause IDs (regex boundary) from coverage parquet."""
    return _in_force_ids(clauses_path, _SECTION_PREFIX, matcher=is_421_proper)


def export_4201_candidates(
    clauses_path: Path, *, encoded_clause_ids: frozenset[str] | None = None
) -> pl.DataFrame:
    return shim_export_candidates(_SECTION, clauses_path, encoded_clause_ids=encoded_clause_ids)


def build_4201_manifest(
    gate_b_frame: pl.DataFrame, rules: list[dict[str, Any]], *, effective_date: str
) -> dict[str, Any]:
    return shim_build_manifest(_SECTION, gate_b_frame, rules, effective_date=effective_date)


def scan_4201_tier_ab_promotions(
    gate_b_frame: pl.DataFrame, *, encoded_clause_ids: frozenset[str] | set[str]
) -> list[dict[str, Any]]:
    from scripts.sut.prose.gate_b_audit import default_scan_promotions

    return default_scan_promotions(gate_b_frame, encoded_clause_ids)


def _scan(frame: pl.DataFrame, encoded: Any) -> list[dict[str, Any]]:
    """Positional-arg adapter for gate_b_audit.audit_gap_parity."""
    return scan_4201_tier_ab_promotions(frame, encoded_clause_ids=encoded)


def audit_4201_gap_parity(
    clauses_path: Path,
    manifest: dict[str, Any],
    *,
    gate_b_frame: pl.DataFrame | None = None,
) -> dict[str, Any]:
    return _audit_gap_parity(
        clauses_path,
        manifest,
        section_prefix=_SECTION_PREFIX,
        matcher=is_421_proper,
        frame=gate_b_frame,
        fallback_frame=lambda: export_4201_candidates(clauses_path),
        scan=_scan,
    )


def run_4201_audit(
    clauses_path: Path, rules_path: Path, *, effective_date: str
) -> dict[str, Any]:
    payload = json.loads(rules_path.read_text(encoding="utf-8"))
    rules = [r for r in (payload.get("rules") or []) if is_421_proper(str(r.get("sut_section") or ""))]
    frame = export_4201_candidates(clauses_path)
    manifest = build_4201_manifest(frame, rules, effective_date=effective_date)
    before = audit_4201_gap_parity(clauses_path, manifest, gate_b_frame=frame)
    manifest, repaired = _repair(manifest, frame, gap_ids=_gap_ids(clauses_path, _SECTION_PREFIX, matcher=is_421_proper))
    manifest, defer_fixed = _normalize_defer(manifest, frame)
    after = audit_4201_gap_parity(clauses_path, manifest, gate_b_frame=frame)
    return {
        **after,
        "repaired_untraced": repaired,
        "defer_reason_fixed": defer_fixed,
        "untraced_before": before["untraced_before"],
        "untraced_after": len(after["untraced_clause_ids"]) + len(after["misclassified_ab_gap_ids"]),
        "promoted_clause_ids": sorted({p["clause_id"] for p in after["promotion_candidates"]}),
    }


def normalize_4201_defer_reasons(
    manifest: dict[str, Any], gate_b_frame: pl.DataFrame
) -> tuple[dict[str, Any], int]:
    return _normalize_defer(manifest, gate_b_frame)


def write_gate_b_artifacts(
    *,
    clauses_path: Path,
    corpus_csv: Path,
    manifest_path: Path,
    effective_date: str,
    rules_path: Path | None = None,
    batch_rules: list[dict[str, Any]] | None = None,
) -> tuple[pl.DataFrame, dict[str, Any]]:
    return shim_write_artifacts(
        _SECTION,
        clauses_path=clauses_path,
        rules_path=rules_path,
        corpus_csv=corpus_csv,
        manifest_path=manifest_path,
        effective_date=effective_date,
        batch_rules=batch_rules,
    )
