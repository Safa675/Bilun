"""Shared honest-gap audit helpers for the gate_b shim modules.

The rich audit schema (gap_count / tier_c_deferred_count / misclassified_ab_gap_ids /
promotion_count / etc.) and the "gap = ~has_rule_encoding" definition are what the
existing tests assert on. ``gate_b_generic.audit_gap_parity`` uses a simpler schema
and a different gap column (``has_algorithmic_gap``), so the shim modules delegate
here instead to preserve byte-for-byte test behaviour.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

import polars as pl

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.prose.drug_indication_gate_b import (  # noqa: E402
    _encode_tier,
    _heuristic_inn,
    infer_defer_themes,
)
from scripts.sut.prose.gate_b_generic import normalize_tr  # noqa: E402

_MOTOR = "drug_indication_prose"
_DEONTIC_MODALITIES = frozenset(
    {"MUST_BILL", "MUST_NOT_BILL", "NO_PAY", "MAY_BILL", "PROHIBITED", "REGULATORY_ACTION"}
)


def _section_mask(section_prefix: str, exclude_prefix: str, *, matcher=None):
    """Build a polars mask for section_id matching.

    If ``matcher`` is given (a callable section_id -> bool, applied via map_elements)
    it is used for regex-boundary sections (e.g. 4201's ^4\\.2\\.1(?:[^0-9]|$)).
    Otherwise falls back to starts_with(prefix) + optional exclusion.
    """
    if matcher is not None:
        mask = pl.col("section_id").map_elements(matcher, return_dtype=pl.Boolean)
        if exclude_prefix:
            mask = mask & ~pl.col("section_id").str.starts_with(exclude_prefix)
        return mask
    mask = pl.col("section_id").str.starts_with(section_prefix)
    if exclude_prefix:
        mask = mask & ~pl.col("section_id").str.starts_with(exclude_prefix)
    return mask


def gap_clause_ids(
    clauses_path: Path, section_prefix: str, *, exclude_prefix: str = "", matcher=None
) -> frozenset[str]:
    """Motor-bound clause IDs with ``has_rule_encoding=false`` in a section."""
    coverage_path = clauses_path.parent / "sut_clause_coverage.parquet"
    if not coverage_path.is_file():
        return frozenset()
    coverage = pl.read_parquet(coverage_path)
    mask = (pl.col("primary_rule_id") == _MOTOR) & _section_mask(
        section_prefix, exclude_prefix, matcher=matcher
    )
    motor = coverage.filter(mask & ~pl.col("has_rule_encoding"))
    return frozenset(str(row) for row in motor["clause_id"].to_list())


def in_force_clause_ids(
    clauses_path: Path, section_prefix: str, *, matcher=None
) -> frozenset[str]:
    """Motor-bound in-force clause IDs for a section (no encoding filter)."""
    coverage_path = clauses_path.parent / "sut_clause_coverage.parquet"
    if not coverage_path.is_file():
        return frozenset()
    coverage = pl.read_parquet(coverage_path)
    motor = coverage.filter(
        (pl.col("primary_rule_id") == _MOTOR)
        & _section_mask(section_prefix, "", matcher=matcher)
    )
    return frozenset(str(row) for row in motor["clause_id"].to_list())


def _manifest_status_ids(
    manifest: dict[str, Any], *, section_prefix: str = ""
) -> dict[str, frozenset[str]]:
    """Status id sets from manifest LIST fields (matches legacy behaviour).

    The legacy modules read ``encoded_clause_ids`` / ``tier_c_deferred_clause_ids``
    etc. directly (not from clause_traces), which counts encoded ids even when a
    clause is absent from the exported frame (e.g. a §4.2.1 clause covered by an
    exclusion rule). When ``section_prefix`` is set, the encoded set is intersected
    with section-scoped trace ids to keep multi-section audits (4227) bounded.
    """
    encoded = frozenset(str(cid) for cid in manifest.get("encoded_clause_ids") or [])
    tier_c = frozenset(str(cid) for cid in manifest.get("tier_c_deferred_clause_ids") or [])
    tier_a = frozenset(str(cid) for cid in manifest.get("tier_a_pending_clause_ids") or [])
    tier_b = frozenset(str(cid) for cid in manifest.get("tier_b_pending_clause_ids") or [])
    if section_prefix:
        scope_ids = frozenset(
            str(t.get("clause_id") or "")
            for t in (manifest.get("clause_traces") or [])
            if str(t.get("section_id") or "").startswith(section_prefix)
        )
        encoded = encoded & scope_ids
        tier_c = tier_c & scope_ids
        tier_a = tier_a & scope_ids
        tier_b = tier_b & scope_ids
    return {
        "encoded": encoded,
        "tier_c_deferred": tier_c,
        "tier_a_pending": tier_a,
        "tier_b_pending": tier_b,
    }


def default_scan_promotions(
    frame: pl.DataFrame, encoded_clause_ids: Any
) -> list[dict[str, Any]]:
    """Best-effort Tier A/B promotion scan (raw_tier / deontic+inn+report signals)."""
    encoded = {str(cid) for cid in encoded_clause_ids}
    promotions: list[dict[str, Any]] = []
    tier_c = frame.filter(pl.col("encode_tier") == "C") if frame.height else frame
    for row in tier_c.iter_rows(named=True):
        clause_id = str(row.get("clause_id") or "")
        if clause_id in encoded:
            continue
        text = str(row.get("text_tr") or "")
        deontic = str(row.get("deontic_modality") or "")
        inn = _heuristic_inn(text)
        normalized = normalize_tr(text)
        raw_tier = _encode_tier(text, inn)
        reasons: list[str] = []
        if raw_tier in {"A", "B"}:
            reasons.append(f"raw_tier={raw_tier}")
        if deontic in _DEONTIC_MODALITIES and inn and (
            "rapor" in normalized or "recete" in normalized
        ):
            reasons.append("deontic_inn_report")
        if reasons:
            promotions.append(
                {
                    "clause_id": clause_id,
                    "section_id": str(row.get("section_id") or ""),
                    "heuristic_inn": inn,
                    "reasons": reasons,
                    "text_tr": text,
                }
            )
    return promotions


def audit_gap_parity(
    clauses_path: Path,
    manifest: dict[str, Any],
    *,
    section_prefix: str,
    exclude_prefix: str = "",
    frame: pl.DataFrame | None = None,
    fallback_frame: Callable[[], pl.DataFrame] | None = None,
    scan: Callable[[pl.DataFrame, Any], list[dict[str, Any]]] = default_scan_promotions,
    include_pending_honest: bool = True,
    misclassified_against_encoded: bool = False,
    matcher=None,
    scope_statuses: bool = False,
) -> dict[str, Any]:
    """Honest-gap parity audit returning the rich schema the tests assert on."""
    gap_ids = gap_clause_ids(
        clauses_path, section_prefix, exclude_prefix=exclude_prefix, matcher=matcher
    )
    statuses = _manifest_status_ids(
        manifest, section_prefix=section_prefix if scope_statuses else ""
    )
    trace_ids = {
        str(t.get("clause_id") or "")
        for t in (manifest.get("clause_traces") or [])
        if str(t.get("section_id") or "").startswith(section_prefix)
    }

    honest = statuses["encoded"] | statuses["tier_c_deferred"]
    if include_pending_honest:
        honest = honest | statuses["tier_a_pending"] | statuses["tier_b_pending"]
    if include_pending_honest:
        untraced_pool = gap_ids - honest
    else:
        untraced_pool = gap_ids - honest - statuses["tier_a_pending"] - statuses["tier_b_pending"]
    untraced = sorted(untraced_pool)

    misclass_source = statuses["encoded"] if misclassified_against_encoded else (
        statuses["tier_a_pending"] | statuses["tier_b_pending"]
    )
    misclassified_ab = sorted(misclass_source & gap_ids)
    missing_from_traces = sorted(gap_ids - trace_ids)
    encoded_still_gap = sorted(gap_ids & statuses["encoded"])

    resolved_frame = (
        frame if frame is not None else (fallback_frame() if fallback_frame else pl.DataFrame())
    )
    export_ids = set(resolved_frame["clause_id"].to_list()) if resolved_frame.height else set()
    gaps_missing_export = sorted(gap_ids - export_ids)

    promotions = (
        scan(resolved_frame, statuses["encoded"]) if resolved_frame.height else []
    )

    defer_reason_gaps = [
        str(t.get("clause_id") or "")
        for t in (manifest.get("clause_traces") or [])
        if t.get("manifest_status") == "tier_c_deferred"
        and (not t.get("defer_reason") or t.get("defer_themes") is None)
    ]

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
        "defer_reason_gaps": defer_reason_gaps,
        "defer_reason_gap_count": len(defer_reason_gaps),
        "promotion_candidates": promotions,
        "promotion_count": len(promotions),
    }


def repair_untraced(
    manifest: dict[str, Any],
    frame: pl.DataFrame,
    *,
    gap_ids: frozenset[str],
) -> tuple[dict[str, Any], int]:
    """Inject tier_c_deferred traces for gap IDs missing honest coverage."""
    statuses = _manifest_status_ids(manifest)
    honest = statuses["encoded"] | statuses["tier_c_deferred"]
    pending = statuses["tier_a_pending"] | statuses["tier_b_pending"]
    missing = gap_ids - honest - pending if gap_ids else frozenset()

    trace_by_id = {str(t["clause_id"]): dict(t) for t in manifest.get("clause_traces") or []}
    frame_by_id = {str(r["clause_id"]): r for r in frame.iter_rows(named=True)} if frame.height else {}
    repaired = 0

    for clause_id in sorted(missing):
        row = frame_by_id.get(clause_id)
        text = str((row or {}).get("text_tr") or "")
        themes = infer_defer_themes(text) if text else []
        labels = ", ".join(themes) if themes else "clinical_pathway"
        trace_by_id[clause_id] = {
            "clause_id": clause_id,
            "section_id": str((row or {}).get("section_id") or ""),
            "encode_tier": str((row or {}).get("encode_tier") or "C"),
            "manifest_status": "tier_c_deferred",
            "heuristic_inn": str((row or {}).get("heuristic_inn") or ""),
            "defer_themes": themes,
            "defer_reason": (
                f"Deferred — requires structured ingest for: {labels}. "
                "Tier C manifest-only until EMR fields support pathway."
            ),
        }
        repaired += 1

    if not repaired:
        return manifest, 0

    tier_c = sorted(
        cid for cid, trace in trace_by_id.items()
        if trace.get("manifest_status") == "tier_c_deferred"
    )
    updated = dict(manifest)
    updated["clause_traces"] = [trace_by_id[cid] for cid in sorted(trace_by_id)]
    updated["tier_c_deferred_clause_ids"] = tier_c
    updated["tier_c_deferred_count"] = len(tier_c)
    return updated, repaired


def normalize_defer_reasons(
    manifest: dict[str, Any], frame: pl.DataFrame
) -> tuple[dict[str, Any], int]:
    """Ensure every tier_c_deferred trace has defer_reason + defer_themes."""
    frame_by_id = {str(r["clause_id"]): r for r in frame.iter_rows(named=True)} if frame.height else {}
    traces = [dict(t) for t in manifest.get("clause_traces") or []]
    fixed = 0

    for trace in traces:
        if trace.get("manifest_status") != "tier_c_deferred":
            continue
        clause_id = str(trace.get("clause_id") or "")
        row = frame_by_id.get(clause_id)
        text = str((row or {}).get("text_tr") or "")
        needs_reason = not trace.get("defer_reason")
        needs_themes = trace.get("defer_themes") is None
        if not needs_reason and not needs_themes:
            continue
        themes = trace.get("defer_themes")
        if themes is None:
            themes = infer_defer_themes(text) if text else []
            trace["defer_themes"] = themes
        if needs_reason:
            labels = ", ".join(themes) if themes else "clinical_pathway"
            trace["defer_reason"] = (
                f"Deferred — requires structured ingest for: {labels}. "
                "Tier C manifest-only until EMR fields support pathway."
            )
        fixed += 1

    if not fixed:
        return manifest, 0

    updated = dict(manifest)
    updated["clause_traces"] = traces
    return updated, fixed
