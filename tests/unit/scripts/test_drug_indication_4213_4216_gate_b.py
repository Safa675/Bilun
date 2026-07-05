"""Tests for §4.2.13 / §4.2.16 drug indication Gate B export."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"
_RULES = _REPO / "data/gazette/prose_rules/drug_indication_prose.json"
_CORPUS = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4213_4216.csv"
_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4213_4216_manifest.json"


def test_gate_b_exports_4213_4216_candidates() -> None:
    from scripts.sut.prose.drug_indication_4213_4216_gate_b import export_4213_4216_candidates

    frame = export_4213_4216_candidates(_CLAUSES)
    assert frame.height >= 80
    prefixes = set(frame["section_id"].str.slice(0, 6).unique().to_list())
    assert prefixes <= {"4.2.13", "4.2.16"}


def test_gate_b_csv_schema() -> None:
    from scripts.sut.prose.drug_indication_4213_4216_gate_b import export_4213_4216_candidates

    frame = export_4213_4216_candidates(_CLAUSES)
    for col in (
        "clause_id",
        "section_id",
        "deontic_modality",
        "text_tr",
        "encode_tier",
        "encode_priority",
    ):
        assert col in frame.columns
    assert frame.filter(pl.col("encode_tier") == "A").height >= 5


def test_manifest_has_encoded_and_tier_c_trace() -> None:
    from scripts.sut.prose.drug_indication_4213_4216_gate_b import build_4213_4216_manifest
    from scripts.sut.rule_sources import load_legacy_drug_batch

    BATCH_A2_RULES = load_legacy_drug_batch("BATCH_A2_RULES")

    frame = pl.read_csv(_CORPUS) if _CORPUS.is_file() else None
    if frame is None:
        from scripts.sut.prose.drug_indication_4213_4216_gate_b import export_4213_4216_candidates

        frame = export_4213_4216_candidates(_CLAUSES)
    manifest = build_4213_4216_manifest(frame, BATCH_A2_RULES, effective_date="2026-06-27")
    encoded = manifest["encoded_clause_ids"]
    assert len(encoded) >= 12
    assert manifest["tier_c_deferred_count"] >= 20
    assert manifest["rules_in_json"] == len(BATCH_A2_RULES)


def test_gate_b_artifacts_on_disk(tmp_path: Path) -> None:
    from scripts.sut.prose.drug_indication_4213_4216_gate_b import write_gate_b_artifacts

    corpus = tmp_path / _CORPUS.name
    manifest_path = tmp_path / _MANIFEST.name
    write_gate_b_artifacts(
        clauses_path=_CLAUSES,
        rules_path=_RULES,
        corpus_csv=corpus,
        manifest_path=manifest_path,
        effective_date="2026-06-27",
    )
    assert corpus.is_file()
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["encoded_clause_count"] >= 12
