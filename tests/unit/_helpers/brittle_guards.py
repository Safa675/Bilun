"""Guards that survive corpus / synthetic / gazette growth.

Prefer these over magic-number ``assert len(x) == N`` locks. See
``plans/refactor/brittle-test-remediation-plan.md``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl


def soft_floor(actual: int, floor: int, *, label: str) -> None:
    """Assert ``actual >= floor`` with a clear regression message."""
    assert actual >= floor, (
        f"{label}: expected >= {floor} (baseline floor), got {actual}"
    )


def assert_count_matches_list(
    manifest: dict[str, Any],
    list_key: str,
    count_key: str,
) -> None:
    """Assert manifest count field equals len of the paired list field."""
    if list_key not in manifest or count_key not in manifest:
        return
    actual_len = len(manifest[list_key] or [])
    reported = manifest[count_key]
    assert actual_len == reported, (
        f"{list_key} has {actual_len} entries but {count_key}={reported}"
    )


def assert_manifest_consistent(
    manifest: dict[str, Any],
    frame: pl.DataFrame | None = None,
    *,
    rules: list[dict[str, Any]] | None = None,
) -> None:
    """Self-consistency checks for a gate_b manifest.

    - ``section_clause_total == frame.height`` when frame is provided
    - count fields match list lengths
    - encoded IDs ⊆ union of rule ``gate_b_sources`` when rules provided
    - tier A+B+C heights sum to frame.height when ``encode_tier`` present
    """
    if frame is not None and "section_clause_total" in manifest:
        assert manifest["section_clause_total"] == frame.height, (
            f"section_clause_total={manifest['section_clause_total']} "
            f"!= frame.height={frame.height}"
        )

    for list_key, count_key in (
        ("encoded_clause_ids", "encoded_clause_count"),
        ("tier_c_deferred_clause_ids", "tier_c_deferred_count"),
        ("tier_a_pending_clause_ids", "tier_a_pending_count"),
        ("tier_b_pending_clause_ids", "tier_b_pending_count"),
        ("emr_blocked_clause_ids", "emr_blocked_count"),
        ("non_actionable_clause_ids", "non_actionable_count"),
    ):
        assert_count_matches_list(manifest, list_key, count_key)

    if rules is not None and "encoded_clause_ids" in manifest:
        # Dual-read: rules may cite coordinates while manifests list clause_ids.
        if frame is not None:
            from scripts.sut.prose.clause_identity import (
                AmbiguousClauseCiteError,
                NonEncodeEligibleCiteError,
                UnknownClauseCiteError,
                is_clause_id,
                resolve_gate_b_sources_to_clause_ids,
            )

            rule_sources: set[str] = set()
            for rule in rules:
                for raw in rule.get("gate_b_sources") or []:
                    if raw is None or not str(raw).strip():
                        continue
                    try:
                        can_encode_filter = (
                            "clause_type" in frame.columns
                            and "is_in_force" in frame.columns
                            and (
                                "clause_number" in frame.columns
                                or "clause_letter" in frame.columns
                            )
                        )
                        rule_sources.update(
                            resolve_gate_b_sources_to_clause_ids(
                                [raw],
                                frame,
                                in_force_only="is_in_force" in frame.columns,
                                encode_eligible_only=can_encode_filter,
                                allow_ambiguous=False,
                            )
                        )
                    except (
                        AmbiguousClauseCiteError,
                        NonEncodeEligibleCiteError,
                        UnknownClauseCiteError,
                    ):
                        text = str(raw).strip()
                        if is_clause_id(text):
                            rule_sources.add(text)
        else:
            rule_sources = {
                str(cid)
                for rule in rules
                for cid in (rule.get("gate_b_sources") or [])
                if cid is not None and str(cid).strip()
            }
        encoded = {str(c) for c in (manifest.get("encoded_clause_ids") or [])}
        orphaned = encoded - rule_sources
        assert not orphaned, (
            f"{len(orphaned)} encoded clause_ids have no matching rule "
            f"gate_b_source (sample: {sorted(orphaned)[:5]})"
        )

    if frame is not None and "encode_tier" in frame.columns:
        tiers = frame["encode_tier"].value_counts()
        total = int(tiers["count"].sum()) if tiers.height else 0
        assert total == frame.height, (
            f"tier partition sum {total} != frame.height {frame.height}"
        )


def assert_audit_report_consistent(
    report: dict[str, Any],
    manifest: dict[str, Any],
) -> None:
    """Audit report counts must match manifest list lengths; untraced must be empty."""
    assert report.get("untraced_clause_ids") == []
    assert report.get("misclassified_ab_gap_ids") == []
    assert report.get("missing_from_traces") == []
    assert report.get("gaps_missing_export") == []

    if "encoded_clause_ids" in manifest:
        assert report["encoded_count"] == len(manifest["encoded_clause_ids"])
    if "tier_c_deferred_clause_ids" in manifest:
        assert report["tier_c_deferred_count"] == len(
            manifest["tier_c_deferred_clause_ids"]
        )


def parquet_section_count(
    clauses_path: Path,
    prefix: str,
    *,
    exclude_prefix: str = "",
    matcher=None,
) -> int:
    """Count in-force clause rows for a section prefix (delegates to gate_b_audit)."""
    from scripts.sut.prose.gate_b_audit import in_force_clause_ids

    return len(
        in_force_clause_ids(
            clauses_path,
            prefix,
            exclude_prefix=exclude_prefix,
            matcher=matcher,
        )
    )
