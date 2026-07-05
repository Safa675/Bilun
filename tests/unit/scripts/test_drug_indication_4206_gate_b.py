"""Tests for §4.2.6 growth hormone drug indication Gate B export."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"
_CORPUS = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4206.csv"
_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4206_manifest.json"

_A2_ENCODED = {
    "C003941",
    "C003965",
    "C003966",
    "C003982",
    "C004016",
    "C004030",
    "C004033",
}
_A2_TIER_A_ENCODED = _A2_ENCODED - {"C003965"}
_A6_ENCODED = {"C003998", "C004003", "C004039"}
_ALL_ENCODED = _A6_ENCODED | _A2_ENCODED
_ALL_TIER_A_ENCODED = _A6_ENCODED | _A2_TIER_A_ENCODED


def test_gate_b_exports_4206_candidates() -> None:
    from scripts.sut.prose.drug_indication_4206_gate_b import export_4206_candidates

    frame = export_4206_candidates(_CLAUSES)
    assert frame.height >= 40
    assert frame["section_id"].str.starts_with("4.2.6.").all()
    assert not frame["section_id"].str.starts_with("4.2.60").any()


def test_gate_b_csv_schema() -> None:
    from scripts.sut.prose.drug_indication_4206_gate_b import export_4206_candidates

    frame = export_4206_candidates(_CLAUSES)
    for col in (
        "clause_id",
        "section_id",
        "deontic_modality",
        "text_tr",
        "encode_tier",
        "encode_priority",
    ):
        assert col in frame.columns
    tier_a = set(frame.filter(pl.col("encode_tier") == "A")["clause_id"].to_list())
    assert _ALL_TIER_A_ENCODED <= tier_a


def test_manifest_has_encoded_and_tier_c_trace() -> None:
    from scripts.sut.prose.drug_indication_4206_gate_b import (
        _all_4206_batch_rules,
        build_4206_manifest,
        export_4206_candidates,
    )

    frame = pl.read_csv(_CORPUS) if _CORPUS.is_file() else export_4206_candidates(_CLAUSES)
    rules = _all_4206_batch_rules()
    manifest = build_4206_manifest(frame, rules, effective_date="2026-06-27")
    encoded = set(manifest["encoded_clause_ids"])
    assert encoded == _ALL_ENCODED
    assert manifest["tier_c_deferred_count"] >= 28
    assert manifest["tier_a_pending_count"] == 2
    assert manifest["tier_b_pending_count"] == 0
    assert manifest["rules_in_json"] == len(rules)


def test_gate_b_artifacts_on_disk(tmp_path: Path) -> None:
    from scripts.sut.prose.drug_indication_4206_gate_b import (
        _all_4206_batch_rules,
        write_gate_b_artifacts,
    )

    corpus = tmp_path / _CORPUS.name
    manifest_path = tmp_path / _MANIFEST.name
    write_gate_b_artifacts(
        clauses_path=_CLAUSES,
        rules=_all_4206_batch_rules(),
        corpus_csv=corpus,
        manifest_path=manifest_path,
        effective_date="2026-06-27",
    )
    assert corpus.is_file()
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["encoded_clause_count"] == len(_ALL_ENCODED)
    assert manifest["section_id"] == "4.2.6"
    assert set(manifest["encoded_clause_ids"]) == _ALL_ENCODED
