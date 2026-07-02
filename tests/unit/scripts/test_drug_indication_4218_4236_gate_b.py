"""Tests for §4.2.18 / §4.2.36 orlistat + Parkinson Gate B export."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"
_CORPUS = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4218_4236.csv"
_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4218_4236_manifest.json"


def test_gate_b_exports_both_section_prefixes() -> None:
    from scripts.sut.prose.drug_indication_4218_4236_gate_b import export_4218_4236_candidates

    frame = export_4218_4236_candidates(_CLAUSES)
    assert frame.height == 11
    assert frame.filter(pl.col("section_id").str.starts_with("4.2.18")).height == 5
    assert frame.filter(pl.col("section_id").str.starts_with("4.2.36")).height == 6


def test_gate_b_tier_counts_per_subsection() -> None:
    from scripts.sut.prose.drug_indication_4218_4236_gate_b import export_4218_4236_candidates

    frame = export_4218_4236_candidates(_CLAUSES)
    s418 = frame.filter(pl.col("section_id").str.starts_with("4.2.18"))
    s436 = frame.filter(pl.col("section_id").str.starts_with("4.2.36"))
    assert s418.filter(pl.col("encode_tier") == "A").height == 1
    assert s418.filter(pl.col("encode_tier") == "C").height == 4
    assert s436.filter(pl.col("encode_tier") == "A").height == 4
    assert s436.filter(pl.col("encode_tier") == "C").height == 2


def test_gate_b_csv_schema() -> None:
    from scripts.sut.prose.drug_indication_4218_4236_gate_b import export_4218_4236_candidates

    frame = export_4218_4236_candidates(_CLAUSES)
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

    BATCH_A5_RULES = load_legacy_drug_batch("drug_indication_4218_4236_batch_rules.py:BATCH_A5_RULES")
    from scripts.sut.prose.drug_indication_4218_4236_gate_b import (
        build_4218_4236_manifest,
        export_4218_4236_candidates,
    )

    frame = pl.read_csv(_CORPUS) if _CORPUS.is_file() else export_4218_4236_candidates(_CLAUSES)
    manifest = build_4218_4236_manifest(frame, BATCH_A5_RULES, effective_date="2026-06-27")
    assert manifest["rules_in_json"] == 5
    assert manifest["encoded_clause_count"] == 5
    assert manifest["tier_c_deferred_count"] == 6
    assert manifest["section_4.2.18_tier_a_count"] == 1
    assert manifest["section_4.2.36_tier_a_count"] == 4


def test_gate_b_artifacts_on_disk(tmp_path: Path) -> None:
    from scripts.sut.rule_sources import load_legacy_drug_batch

    BATCH_A5_RULES = load_legacy_drug_batch("drug_indication_4218_4236_batch_rules.py:BATCH_A5_RULES")
    from scripts.sut.prose.drug_indication_4218_4236_gate_b import write_gate_b_artifacts

    corpus = tmp_path / _CORPUS.name
    manifest_path = tmp_path / _MANIFEST.name
    write_gate_b_artifacts(
        clauses_path=_CLAUSES,
        rules_path=_REPO / "data/gazette/prose_rules/drug_indication_prose.json",
        corpus_csv=corpus,
        manifest_path=manifest_path,
        effective_date="2026-06-27",
        batch_rules=BATCH_A5_RULES,
    )
    assert corpus.is_file()
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["section_clause_total"] == 11
    assert manifest["encoded_clause_count"] == 5
