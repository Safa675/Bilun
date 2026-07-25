"""Tests for §4.2.35 / §4.2.37 neuropathic pain + acromegaly Gate B export."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from tests.unit._helpers.brittle_guards import (
    assert_audit_report_consistent,
    assert_manifest_consistent,
    soft_floor,
)

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"
_CORPUS = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4235_4237.csv"
_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4235_4237_manifest.json"

_SECTION = "4235_4237"


def test_gate_b_exports_4235_4237_candidates() -> None:
    from scripts.sut.prose.gate_b_generic import export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    frame = export_candidates(_CLAUSES, ALL_SECTIONS[_SECTION])
    soft_floor(frame.height, 18, label="test_drug_indication_4235_4237_gate_b frame.height")
    soft_floor(frame.filter(pl.col("section_id").str.starts_with("4.2.35")).height, 11, label="test_drug_indication_4235_4237_gate_b 4.2.35")
    soft_floor(frame.filter(pl.col("section_id").str.starts_with("4.2.37")).height, 6, label="test_drug_indication_4235_4237_gate_b 4.2.37")


def test_gate_b_tier_counts() -> None:
    from scripts.sut.prose.gate_b_generic import export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    frame = export_candidates(_CLAUSES, ALL_SECTIONS[_SECTION])
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
        "heuristic_inn",
    ):
        assert col in frame.columns


def test_manifest_has_encoded_and_tier_c_trace() -> None:
    from scripts.sut.prose.gate_b_generic import build_manifest, export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS
    from scripts.sut.rule_sources import load_legacy_drug_batch

    BATCH_A5_RULES = load_legacy_drug_batch("drug_indication_4235_4237_batch_rules.py:BATCH_A5_RULES")

    frame = export_candidates(_CLAUSES, ALL_SECTIONS[_SECTION])
    manifest = build_manifest(frame, BATCH_A5_RULES, ALL_SECTIONS[_SECTION], resolve_clauses=pl.read_parquet(_CLAUSES),
        effective_date="2026-06-27")
    encoded = set(manifest["encoded_clause_ids"])
    on_disk = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    # Fresh build is a subset of on-disk (reconciliation may expand encoded beyond the batch).
    on_disk_encoded = set(on_disk.get("encoded_clause_ids") or on_disk.get("encoded_clause_ids") or [])
    assert encoded <= on_disk_encoded
    assert "C006717" in encoded
    soft_floor(int(manifest["tier_c_deferred_count"]), 9, label="test_drug_indication_4235_4237_gate_b tier_c_deferred")
    assert manifest["tier_a_pending_count"] == 0
    assert manifest["tier_b_pending_count"] == 0
    soft_floor(int(manifest["rules_in_json"]), 3, label="test_drug_indication_4235_4237_gate_b rules_in_json")
    assert manifest["section_4.2.35_clause_total"] == 17
    assert manifest["section_4.2.37_clause_total"] == 9


def test_gate_b_artifacts_on_disk(tmp_path: Path) -> None:
    from scripts.sut.prose.gate_b_generic import write_artifacts
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS
    from scripts.sut.rule_sources import load_legacy_drug_batch

    BATCH_A5_RULES = load_legacy_drug_batch("drug_indication_4235_4237_batch_rules.py:BATCH_A5_RULES")

    corpus = tmp_path / _CORPUS.name
    manifest_path = tmp_path / _MANIFEST.name
    write_artifacts(section=ALL_SECTIONS[_SECTION],
        clauses_path=_CLAUSES,
        corpus_csv=corpus,
        manifest_path=manifest_path,
        effective_date="2026-06-27",
        batch_rules=BATCH_A5_RULES,
        write_corpus=True,
    )
    assert corpus.is_file()
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["encoded_clause_count"] == len(manifest["encoded_clause_ids"]) == 7
    soft_floor(int(manifest["section_clause_total"]), 18, label="test_drug_indication_4235_4237_gate_b section_clause_total")