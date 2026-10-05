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


def _source_census() -> pl.DataFrame:
    return pl.read_parquet(_CLAUSES).filter(
        (pl.col("section_id") == "4.2.14.C") & pl.col("is_in_force")
    ).select("clause_id", "section_id", "text_tr")


def test_4214c_section_registered() -> None:
    assert "4214c" in ALL_SECTIONS
    section = ALL_SECTIONS["4214c"]
    assert section.manifest_section_id == "4.2.14.C"
    assert section.parquet_in_force_only is True


def test_4214c_export_is_in_force_only() -> None:
    section = ALL_SECTIONS["4214c"]
    frame = export_candidates(_CLAUSES, section)
    source = _source_census()
    assert frame.height == source.height == source["clause_id"].n_unique()
    assert frame.select(source.columns).sort("clause_id").equals(source.sort("clause_id"))


def test_4214c_write_artifacts_partitions_in_force(tmp_path: Path) -> None:
    section = ALL_SECTIONS["4214c"]
    _frame, manifest = write_artifacts(
        clauses_path=_CLAUSES,
        section=section,
        effective_date="2026-07-25",
        rules_path=_RULES,
        manifest_path=tmp_path / _MANIFEST.name,
        write_corpus=False,
    )
    source = _source_census()
    in_force = set(source["clause_id"].to_list())
    assert manifest["section_clause_total"] == source.height == len(in_force)
    assert _frame.select(source.columns).sort("clause_id").equals(source.sort("clause_id"))
    assert manifest.get("clause_trace_complete") is True
    buckets = (
        set(manifest.get("encoded_clause_ids") or [])
        | set(manifest.get("emr_blocked_clause_ids") or [])
        | set(manifest.get("non_actionable_clause_ids") or [])
        | set(manifest.get("tier_c_deferred_clause_ids") or [])
        | set(manifest.get("tier_a_pending_clause_ids") or [])
        | set(manifest.get("tier_b_pending_clause_ids") or [])
    )
    assert buckets == in_force
    trace_ids = [trace["clause_id"] for trace in manifest["clause_traces"]]
    assert set(trace_ids) == in_force
    assert len(trace_ids) == len(in_force)
    assert manifest["encoded_clause_count"] == len(manifest["encoded_clause_ids"])
