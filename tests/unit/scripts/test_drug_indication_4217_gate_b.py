"""Tests for §4.2.17 osteoporosis drug indication Gate B export."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"
_RULES = _REPO / "data/gazette/prose_rules/drug_indication_prose.json"
_CORPUS = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4217.csv"
_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4217_manifest.json"

_SECTION = "4217"


def test_gate_b_exports_4217_candidates() -> None:
    from scripts.sut.prose.gate_b_generic import export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    frame = export_candidates(_CLAUSES, ALL_SECTIONS[_SECTION])
    assert frame.height >= 20
    assert frame["section_id"].str.starts_with("4.2.17").all()


def test_gate_b_csv_schema() -> None:
    from scripts.sut.prose.gate_b_generic import export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    frame = export_candidates(_CLAUSES, ALL_SECTIONS[_SECTION])
    for col in (
        "clause_id",
        "section_id",
        "deontic_modality",
        "text_tr",
        "encode_tier",
        "encode_priority",
    ):
        assert col in frame.columns
    assert frame.filter(pl.col("encode_tier") == "A").height >= 8


def test_manifest_has_encoded_and_tier_c_trace() -> None:
    from scripts.sut.rule_sources import load_legacy_drug_batch
    from scripts.sut.prose.gate_b_generic import build_manifest, export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    BATCH_A3_RULES = load_legacy_drug_batch("BATCH_A3_RULES")

    frame = export_candidates(_CLAUSES, ALL_SECTIONS[_SECTION])
    manifest = build_manifest(frame, BATCH_A3_RULES, ALL_SECTIONS[_SECTION], resolve_clauses=pl.read_parquet(_CLAUSES),
        effective_date="2026-06-27")
    encoded = manifest["encoded_clause_ids"]
    assert len(encoded) >= 9
    assert manifest["tier_c_deferred_count"] >= 5
    assert manifest["rules_in_json"] == len(BATCH_A3_RULES)


def test_gate_b_artifacts_on_disk(tmp_path: Path) -> None:
    from scripts.sut.prose.gate_b_generic import write_artifacts
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    corpus = tmp_path / _CORPUS.name
    manifest_path = tmp_path / _MANIFEST.name
    write_artifacts(section=ALL_SECTIONS[_SECTION],
        clauses_path=_CLAUSES,
        rules_path=_RULES,
        corpus_csv=corpus,
        manifest_path=manifest_path,
        effective_date="2026-06-27",
        write_corpus=True,
    )
    assert corpus.is_file()
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["encoded_clause_count"] >= 9
