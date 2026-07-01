"""Tests for §4.2.9 ESA / §4.2.27 coagulation Gate B export."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"
_CORPUS = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4209_4227.csv"
_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4209_4227_manifest.json"


def test_gate_b_exports_both_section_prefixes() -> None:
    from scripts.sut.prose.drug_indication_4209_4227_gate_b import export_4209_4227_candidates

    frame = export_4209_4227_candidates(_CLAUSES)
    assert frame.filter(pl.col("section_id").str.starts_with("4.2.9")).height >= 30
    assert frame.filter(pl.col("section_id").str.starts_with("4.2.27")).height == 69


def test_gate_b_4227_in_force_export() -> None:
    from scripts.sut.prose.drug_indication_4209_4227_gate_b import (
        _gap_clause_ids_4227,
        _in_force_clause_ids_4227,
        export_4209_4227_candidates,
    )

    in_force = _in_force_clause_ids_4227(_CLAUSES)
    frame = export_4209_4227_candidates(_CLAUSES)
    export_427 = set(
        frame.filter(pl.col("section_id").str.starts_with("4.2.27"))["clause_id"].to_list()
    )
    assert export_427 == set(in_force)
    gaps = _gap_clause_ids_4227(_CLAUSES)
    assert len(gaps) == 31
    assert gaps - export_427 == set()


def test_gate_b_tier_a_counts() -> None:
    from scripts.sut.prose.drug_indication_4209_4227_gate_b import export_4209_4227_candidates

    frame = export_4209_4227_candidates(_CLAUSES)
    s429 = frame.filter(pl.col("section_id").str.starts_with("4.2.9"))
    s427 = frame.filter(pl.col("section_id").str.starts_with("4.2.27"))
    assert s429.filter(pl.col("encode_tier") == "A").height >= 7
    assert s427.filter(pl.col("encode_tier") == "A").height >= 13


def test_gate_b_csv_schema() -> None:
    from scripts.sut.prose.drug_indication_4209_4227_gate_b import export_4209_4227_candidates

    frame = export_4209_4227_candidates(_CLAUSES)
    for col in (
        "clause_id",
        "section_id",
        "deontic_modality",
        "text_tr",
        "encode_tier",
        "encode_priority",
        "defer_themes",
    ):
        assert col in frame.columns


def test_manifest_has_encoded_and_tier_c_trace() -> None:
    from scripts.sut.rule_sources import load_legacy_drug_batch

    BATCH_A6_RULES = load_legacy_drug_batch("drug_indication_4209_4227_batch_rules.py:BATCH_A6_RULES")
    from scripts.sut.prose.drug_indication_4209_4227_gate_b import (
        audit_4227_gap_parity,
        build_4209_4227_manifest,
        export_4209_4227_candidates,
    )
    from scripts.sut.rule_sources import load_legacy_drug_batch

    BATCH_A8_RULES = load_legacy_drug_batch("drug_indication_4227_a8_batch_rules.py:BATCH_A8_RULES")
    combined = BATCH_A6_RULES + BATCH_A8_RULES
    frame = export_4209_4227_candidates(_CLAUSES)
    manifest = build_4209_4227_manifest(frame, combined, effective_date="2026-06-27")
    audit = audit_4227_gap_parity(_CLAUSES, manifest, gate_b_frame=frame)
    assert manifest["rules_in_json"] == len(combined)
    assert manifest["section_4.2.27_clause_total"] == 69
    assert audit["untraced_after"] == 0
    assert manifest["tier_c_deferred_count"] >= 40
    assert manifest["section_4.2.9_tier_a_count"] >= 7
    assert manifest["section_4.2.27_tier_a_count"] >= 13


def test_gate_b_artifacts_on_disk(tmp_path: Path) -> None:
    from scripts.sut.rule_sources import load_legacy_drug_batch

    BATCH_A6_RULES = load_legacy_drug_batch("drug_indication_4209_4227_batch_rules.py:BATCH_A6_RULES")
    from scripts.sut.prose.drug_indication_4209_4227_gate_b import write_gate_b_artifacts
    from scripts.sut.rule_sources import load_legacy_drug_batch

    BATCH_A8_RULES = load_legacy_drug_batch("drug_indication_4227_a8_batch_rules.py:BATCH_A8_RULES")
    corpus = tmp_path / "corpus.csv"
    manifest = tmp_path / "manifest.json"
    combined = BATCH_A6_RULES + BATCH_A8_RULES
    write_gate_b_artifacts(
        clauses_path=_CLAUSES,
        rules_path=_REPO / "data/gazette/prose_rules/drug_indication_prose.json",
        corpus_csv=corpus,
        manifest_path=manifest,
        effective_date="2026-06-27",
        batch_rules=combined,
    )
    assert corpus.is_file()
    assert manifest.is_file()
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["rules_in_json"] == len(combined)
    assert payload["section_4.2.27_clause_total"] == 69
    assert payload["section_id"] == "4.2.9,4.2.27"
