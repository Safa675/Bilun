"""Tests for §4.2.35 / §4.2.37 neuropathic pain + acromegaly Gate B export."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"
_CORPUS = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4235_4237.csv"
_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4235_4237_manifest.json"


def test_gate_b_exports_4235_4237_candidates() -> None:
    from scripts.sut.prose.drug_indication_4235_4237_gate_b import export_4235_4237_candidates

    frame = export_4235_4237_candidates(_CLAUSES)
    assert frame.height == 26
    assert frame.filter(pl.col("section_id").str.starts_with("4.2.35")).height == 17
    assert frame.filter(pl.col("section_id").str.starts_with("4.2.37")).height == 9


def test_gate_b_tier_counts() -> None:
    from scripts.sut.prose.drug_indication_4235_4237_gate_b import export_4235_4237_candidates

    frame = export_4235_4237_candidates(_CLAUSES)
    tier = frame.group_by("encode_tier").len().sort("encode_tier")
    counts = {row["encode_tier"]: row["len"] for row in tier.iter_rows(named=True)}
    assert counts == {"A": 5, "B": 1, "C": 20}

    s4235 = frame.filter(pl.col("section_id").str.starts_with("4.2.35"))
    s4235_tiers = {
        row["encode_tier"]: row["len"]
        for row in s4235.group_by("encode_tier").len().iter_rows(named=True)
    }
    assert s4235_tiers == {"A": 2, "B": 1, "C": 14}

    s4237 = frame.filter(pl.col("section_id").str.starts_with("4.2.37"))
    s4237_tiers = {
        row["encode_tier"]: row["len"]
        for row in s4237.group_by("encode_tier").len().iter_rows(named=True)
    }
    assert s4237_tiers == {"A": 3, "C": 6}


def test_gate_b_csv_schema() -> None:
    from scripts.sut.prose.drug_indication_4235_4237_gate_b import export_4235_4237_candidates

    frame = export_4235_4237_candidates(_CLAUSES)
    for col in (
        "clause_id",
        "section_id",
        "deontic_modality",
        "text_tr",
        "encode_tier",
        "encode_priority",
        "heuristic_inn",
    ):
        assert col in frame.columns


def test_manifest_has_encoded_and_tier_c_trace() -> None:
    from scripts.sut.prose.drug_indication_4235_4237_batch_rules import BATCH_A5_RULES
    from scripts.sut.prose.drug_indication_4235_4237_gate_b import (
        build_4235_4237_manifest,
        export_4235_4237_candidates,
    )

    frame = export_4235_4237_candidates(_CLAUSES)
    manifest = build_4235_4237_manifest(frame, BATCH_A5_RULES, effective_date="2026-06-27")
    encoded = set(manifest["gate_b_sources_encoded"])
    assert encoded == {
        "C006694",
        "C006697",
        "C006705",
        "C006715",
        "C006716",
        "C006718",
    }
    assert manifest["tier_c_deferred_count"] == 20
    assert manifest["tier_a_pending_count"] == 0
    assert manifest["tier_b_pending_count"] == 0
    assert manifest["rules_in_json"] == 5
    assert manifest["section_4.2.35_clause_total"] == 17
    assert manifest["section_4.2.37_clause_total"] == 9


def test_gate_b_artifacts_on_disk() -> None:
    from scripts.sut.prose.drug_indication_4235_4237_batch_rules import BATCH_A5_RULES
    from scripts.sut.prose.drug_indication_4235_4237_gate_b import write_gate_b_artifacts

    write_gate_b_artifacts(
        clauses_path=_CLAUSES,
        corpus_csv=_CORPUS,
        manifest_path=_MANIFEST,
        effective_date="2026-06-27",
        batch_rules=BATCH_A5_RULES,
    )
    assert _CORPUS.is_file()
    assert _MANIFEST.is_file()
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["encoded_clause_count"] == 6
    assert manifest["section_clause_total"] == 26
