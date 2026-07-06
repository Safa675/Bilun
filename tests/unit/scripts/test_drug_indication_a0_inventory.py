"""Phase A0 inventory — gap refresh CSV + manifest vs coverage summary."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.sut.prose.drug_indication_a0_inventory import (
    _DEFAULT_GAP_CSV,
    _DEFAULT_SUMMARY,
    build_a0_summary,
    build_gap_refresh_frame,
)

_REPO = Path(__file__).resolve().parents[3]
_COVERAGE = _REPO / "data/gazette/sut_clause_coverage.parquet"
_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4.2.14.C_manifest.json"
_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"
_RULES = _REPO / "data/gazette/prose_rules/drug_indication_prose.json"


def test_a0_summary_json_exists_and_tier_counts_sane() -> None:
    assert _DEFAULT_SUMMARY.is_file(), "run drug_indication_a0_inventory.py first"
    payload = json.loads(_DEFAULT_SUMMARY.read_text(encoding="utf-8"))

    assert payload["motor"] == "drug_indication_prose"
    assert payload["total_clauses"] >= 2300
    assert payload["has_rule_encoding_true"] >= 500
    assert payload["has_rule_encoding_false"] >= 1800

    tiers = payload["encode_tier_counts"]
    assert set(tiers) <= {"A", "B", "C"}
    assert sum(tiers.values()) == payload["total_clauses"]
    assert tiers.get("C", 0) > tiers.get("A", 0)

    prefixes = payload["unencoded_by_section_prefix"]
    assert set(prefixes) == {"4.2.14.C", "4.2.13", "4.2.16", "4.2.33", "rest"}
    assert sum(prefixes.values()) == payload["has_rule_encoding_false"]


def test_gap_refresh_csv_columns_and_row_count() -> None:
    # Phase 7.4: the committed CSV was deleted (stale pre-Phase-5 artifact).
    # The frame builder still works from live data; only the file-existence
    # check is skipped.
    frame = build_gap_refresh_frame(
        _COVERAGE,
        manifest_path=_MANIFEST,
        clauses_path=_CLAUSES,
        rules_path=_RULES,
    )
    expected_cols = {
        "clause_id",
        "section_id",
        "text_excerpt",
        "deontic_modality",
        "encode_tier",
        "in_manifest",
        "has_rule_encoding",
    }
    assert expected_cols <= set(frame.columns)
    assert frame.height >= 2300
    assert frame.filter(frame["encode_tier"].is_in(["A", "B", "C"])).height == frame.height


def test_build_a0_summary_matches_gap_frame() -> None:
    gap = build_gap_refresh_frame(
        _COVERAGE,
        manifest_path=_MANIFEST,
        clauses_path=_CLAUSES,
        rules_path=_RULES,
    )
    summary = build_a0_summary(gap, manifest_path=_MANIFEST)
    assert summary["total_clauses"] == gap.height
    assert summary["manifest_clause_count"] >= 600
