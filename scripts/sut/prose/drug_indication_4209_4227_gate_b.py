"""§4.2.9 ESA / §4.2.27 coagulation Gate B — thin shim delegating to gate_b_generic.

Was ~510 lines; now delegates to the generic engine via gate_b_sections.py. The
§4.2.27 honest-gap audit delegates to gate_b_audit, preserving the legacy schema.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl

from scripts.sut.prose.gate_b_audit import (
    gap_clause_ids as _gap_ids,
    in_force_clause_ids as _in_force_ids,
)
from scripts.sut.prose.gate_b_sections import ALL_SECTIONS
from scripts.sut.prose.gate_b_shim import (
    shim_build_manifest,
    shim_export_candidates,
    shim_write_artifacts,
)

_SECTION = "4209_4227"
_SECTION_4227 = "4.2.27"


def _gap_clause_ids_4227(clauses_path: Path) -> frozenset[str]:
    """Motor-bound §4.2.27 clause IDs with ``has_rule_encoding=false``."""
    return _gap_ids(clauses_path, _SECTION_4227)


def _in_force_clause_ids_4227(clauses_path: Path) -> frozenset[str]:
    """In-force §4.2.27 clause IDs (no encoding filter)."""
    return _in_force_ids(clauses_path, _SECTION_4227)


def _with_defer_themes(frame: pl.DataFrame) -> pl.DataFrame:
    """Back-compat: legacy export emitted a ``defer_themes`` csv column."""
    if frame.is_empty() or "defer_themes" in frame.columns:
        return frame
    from scripts.sut.prose.drug_indication_gate_b import infer_defer_themes

    rows = []
    for r in frame.iter_rows(named=True):
        themes = infer_defer_themes(str(r.get("text_tr") or "")) if r.get("encode_tier") == "C" else []
        rows.append(",".join(themes) if themes else "")
    return frame.with_columns(pl.Series("defer_themes", rows))


def export_4209_4227_candidates(
    clauses_path: Path, *, encoded_clause_ids: frozenset[str] | None = None
) -> pl.DataFrame:
    frame = shim_export_candidates(_SECTION, clauses_path, encoded_clause_ids=encoded_clause_ids)
    return _with_defer_themes(frame)


def build_4209_4227_manifest(
    gate_b_frame: pl.DataFrame, rules: list[dict[str, Any]], *, effective_date: str
) -> dict[str, Any]:
    return shim_build_manifest(_SECTION, gate_b_frame, rules, effective_date=effective_date)


def audit_4227_gap_parity(
    clauses_path: Path,
    manifest: dict[str, Any],
    *,
    gate_b_frame: pl.DataFrame | None = None,
) -> dict[str, Any]:
    """Parity audit: every §4.2.27 coverage gap must be honestly traced.

    Section-scoped to §4.2.27: all manifest statuses count as honest coverage,
    so untraced_before == untraced_after (post-repair parity target = 0).
    """
    gap_ids = _gap_clause_ids_4227(clauses_path)
    trace_ids = {
        str(t.get("clause_id") or "")
        for t in (manifest.get("clause_traces") or [])
        if str(t.get("section_id") or "").startswith(_SECTION_4227)
    }
    statuses = {
        s: frozenset(
            str(t["clause_id"])
            for t in (manifest.get("clause_traces") or [])
            if str(t.get("section_id") or "").startswith(_SECTION_4227)
            and t.get("manifest_status") == s
        )
        for s in ("encoded", "tier_c_deferred", "tier_a_pending", "tier_b_pending")
    }
    honest = statuses["encoded"] | statuses["tier_c_deferred"] | statuses["tier_a_pending"] | statuses["tier_b_pending"]
    untraced = sorted(gap_ids - honest)
    missing_from_traces = sorted(gap_ids - trace_ids)
    frame = gate_b_frame if gate_b_frame is not None else export_4209_4227_candidates(clauses_path)
    export_ids_4227 = (
        set(frame.filter(pl.col("section_id").str.starts_with(_SECTION_4227))["clause_id"].to_list())
        if frame.height
        else set()
    )
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


def write_gate_b_artifacts(
    *,
    clauses_path: Path,
    rules_path: Path,
    corpus_csv: Path,
    manifest_path: Path,
    effective_date: str,
    batch_rules: list[dict[str, Any]] | None = None,
) -> tuple[pl.DataFrame, dict[str, Any]]:
    frame, manifest = shim_write_artifacts(
        _SECTION,
        clauses_path=clauses_path,
        rules_path=rules_path,
        corpus_csv=corpus_csv,
        manifest_path=manifest_path,
        effective_date=effective_date,
        batch_rules=batch_rules,
    )
    # Legacy write injected a §4.2.27 gap-audit summary into the manifest.
    import json

    audit = audit_4227_gap_parity(clauses_path, manifest, gate_b_frame=_with_defer_themes(frame))
    manifest["section_4.2.27_gap_audit"] = {
        "untraced_before": audit["untraced_before"],
        "untraced_after": audit["untraced_after"],
        "gap_count": audit["gap_count"],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return frame, manifest
