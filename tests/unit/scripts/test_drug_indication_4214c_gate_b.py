"""§4.2.14.C Gate B via generic GateBSection (Track C — replaces a1/phase5)."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from scripts.sut.prose.gate_b_generic import export_candidates, write_artifacts
from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

_PROJECT = Path(__file__).resolve().parents[3]
_CLAUSES = _PROJECT / "data/gazette/sut_clauses.parquet"
_RULES = _PROJECT / "data/gazette/prose_rules/drug_indication_prose.json"
_MANIFEST = _PROJECT / "data/gazette/prose_manifests/L4.2_drug_indication_4.2.14.C_manifest.json"


def test_4214c_section_registered() -> None:
    assert "4214c" in ALL_SECTIONS
    section = ALL_SECTIONS["4214c"]
    assert section.manifest_section_id == "4.2.14.C"
    assert section.parquet_in_force_only is True


def test_4214c_export_is_in_force_only() -> None:
    section = ALL_SECTIONS["4214c"]
    frame = export_candidates(_CLAUSES, section)
    assert frame.height == 642
    clauses = pl.read_parquet(_CLAUSES)
    in_force = set(
        clauses.filter(
            (pl.col("section_id") == "4.2.14.C") & (pl.col("is_in_force") == True)  # noqa: E712
        )["clause_id"].to_list()
    )
    assert set(frame["clause_id"].to_list()) == in_force


def test_4214c_write_artifacts_partitions_in_force() -> None:
    section = ALL_SECTIONS["4214c"]
    _frame, manifest = write_artifacts(
        clauses_path=_CLAUSES,
        section=section,
        effective_date="2026-07-25",
        rules_path=_RULES,
        manifest_path=_MANIFEST,
        write_corpus=False,
    )
    assert manifest["section_clause_total"] == 642
    assert manifest.get("clause_trace_complete") is True
    buckets = (
        set(manifest.get("encoded_clause_ids") or [])
        | set(manifest.get("emr_blocked_clause_ids") or [])
        | set(manifest.get("non_actionable_clause_ids") or [])
        | set(manifest.get("tier_c_deferred_clause_ids") or [])
        | set(manifest.get("tier_a_pending_clause_ids") or [])
        | set(manifest.get("tier_b_pending_clause_ids") or [])
    )
    assert len(buckets) == 642
    assert manifest["encoded_clause_count"] == len(manifest["encoded_clause_ids"])
