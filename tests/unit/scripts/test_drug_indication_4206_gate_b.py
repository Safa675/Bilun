"""Tests for §4.2.6 growth hormone drug indication Gate B export."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polars as pl
import pytest

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"
_CORPUS = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4206.csv"
_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4206_manifest.json"

_SECTION = "4206"

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


def _all_4206_batch_rules() -> list[dict[str, Any]]:
    from scripts.sut.rule_sources import load_legacy_drug_batch

    return [
        *load_legacy_drug_batch("drug_indication_4206_batch_rules.py:BATCH_A6_RULES"),
        *load_legacy_drug_batch("drug_indication_4206_a2_batch_rules.py:BATCH_A2_RULES"),
    ]


def test_gate_b_exports_4206_candidates() -> None:
    from scripts.sut.prose.gate_b_shim import shim_export_candidates

    frame = shim_export_candidates(_SECTION, _CLAUSES)
    assert frame.height >= 40
    assert frame["section_id"].str.starts_with("4.2.6.").all()
    assert not frame["section_id"].str.starts_with("4.2.60").any()


def test_gate_b_csv_schema() -> None:
    from scripts.sut.prose.gate_b_shim import shim_export_candidates

    frame = shim_export_candidates(_SECTION, _CLAUSES)
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
    from scripts.sut.prose.gate_b_shim import shim_build_manifest, shim_export_candidates

    frame = shim_export_candidates(_SECTION, _CLAUSES)
    rules = _all_4206_batch_rules()
    manifest = shim_build_manifest(_SECTION, frame, rules, resolve_clauses=pl.read_parquet(_CLAUSES),
        effective_date="2026-06-27")
    encoded = set(manifest["encoded_clause_ids"])
    assert encoded == _ALL_ENCODED
    assert manifest["tier_c_deferred_count"] >= 28
    assert manifest["tier_a_pending_count"] == 2
    assert manifest["tier_b_pending_count"] == 0
    assert manifest["rules_in_json"] == len(rules)


def test_gate_b_artifacts_on_disk(tmp_path: Path) -> None:
    from scripts.sut.prose.gate_b_shim import shim_write_artifacts

    corpus = tmp_path / _CORPUS.name
    manifest_path = tmp_path / _MANIFEST.name
    shim_write_artifacts(
        _SECTION,
        clauses_path=_CLAUSES,
        rules=_all_4206_batch_rules(),
        corpus_csv=corpus,
        manifest_path=manifest_path,
        effective_date="2026-06-27",
        write_corpus=True,
    )
    assert corpus.is_file()
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["encoded_clause_count"] == len(_ALL_ENCODED)
    assert manifest["section_id"] == "4.2.6"
    assert set(manifest["encoded_clause_ids"]) == _ALL_ENCODED
