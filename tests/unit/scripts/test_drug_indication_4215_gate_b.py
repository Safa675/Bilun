"""Tests for §4.2.15 antithrombotic drug indication Gate B export."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from tests.unit._helpers.brittle_guards import soft_floor

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"
_CORPUS = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4215.csv"
_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4215_manifest.json"

_SECTION = "4215"

_PILOT_SOURCES = frozenset({
    "C005840",
    "C005841",
    "C005842",
    "C005843",
    "C005844",
    "C005846",
    "C005849",
    "C005899",
})


def test_gate_b_exports_4215_candidates() -> None:
    from scripts.sut.prose.gate_b_generic import export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    frame = export_candidates(_CLAUSES, ALL_SECTIONS[_SECTION])
    assert frame.height >= 50
    assert frame["section_id"].str.starts_with("4.2.15.").all()


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
        "signal_score",
    ):
        assert col in frame.columns
    tier_a = frame.filter(pl.col("encode_tier") == "A")
    assert tier_a.height >= 10


def test_manifest_has_encoded_and_tier_c_trace() -> None:
    from scripts.sut.prose.gate_b_generic import build_manifest, export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS
    from scripts.sut.rule_sources import load_legacy_drug_batch

    BATCH_A15_RULES = load_legacy_drug_batch("BATCH_A15_RULES")

    frame = export_candidates(_CLAUSES, ALL_SECTIONS[_SECTION])
    manifest = build_manifest(frame, BATCH_A15_RULES, ALL_SECTIONS[_SECTION], resolve_clauses=pl.read_parquet(_CLAUSES),
        effective_date="2026-06-27")
    encoded = set(manifest["encoded_clause_ids"])
    assert encoded == _PILOT_SOURCES
    assert manifest["tier_c_deferred_count"] >= 40
    soft_floor(int(manifest["tier_a_pending_count"]), 2, label="4215 tier_a_pending")
    assert manifest["rules_in_json"] == len(BATCH_A15_RULES)


def test_gate_b_artifacts_on_disk(tmp_path: Path) -> None:
    from scripts.sut.prose.gate_b_generic import write_artifacts
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS
    from scripts.sut.rule_sources import load_legacy_drug_batch

    BATCH_A15_RULES = load_legacy_drug_batch("BATCH_A15_RULES")

    corpus = tmp_path / _CORPUS.name
    manifest_path = tmp_path / _MANIFEST.name
    write_artifacts(section=ALL_SECTIONS[_SECTION],
        clauses_path=_CLAUSES,
        rules=BATCH_A15_RULES,
        corpus_csv=corpus,
        manifest_path=manifest_path,
        effective_date="2026-06-27",
        write_corpus=True,
    )
    assert corpus.is_file()
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["encoded_clause_count"] == 8
    assert manifest["section_id"] == "4.2.15"