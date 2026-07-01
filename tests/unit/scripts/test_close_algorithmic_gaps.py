"""Regression tests for close_algorithmic_gaps — encoded clauses must not re-defer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_MANIFEST_DIR = _REPO / "data/gazette/prose_manifests"
_RULES_JSON = _REPO / "data/gazette/prose_rules/drug_indication_prose.json"


def test_apply_tier_c_defer_skips_gate_b_encoded_clauses(tmp_path: Path) -> None:
    from scripts.sut.close_algorithmic_gaps import _apply_tier_c_defer
    from scripts.sut.prose.coverage import _load_gate_b_sources_from_rules_json

    if not _RULES_JSON.is_file():
        pytest.skip("drug_indication_prose.json not on disk")

    gate_b_encoded = _load_gate_b_sources_from_rules_json(_RULES_JSON)
    if not gate_b_encoded:
        pytest.skip("no gate_b_sources in rules JSON")

    sample_encoded = sorted(gate_b_encoded)[0]
    manifest_path = tmp_path / "test_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "encoded_clause_ids": [sample_encoded],
                "tier_c_deferred_clause_ids": [],
                "clause_traces": [
                    {
                        "clause_id": sample_encoded,
                        "manifest_status": "encoded",
                        "encode_tier": "A",
                    },
                    {
                        "clause_id": "C999999",
                        "manifest_status": "tier_a_pending",
                        "encode_tier": "A",
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    added = _apply_tier_c_defer(
        manifest_path,
        [sample_encoded, "C999999"],
        {"C999999": "sample defer text for tier c pathway"},
    )

    assert added == 1
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    deferred = set(payload.get("tier_c_deferred_clause_ids") or [])
    assert sample_encoded not in deferred
    assert "C999999" in deferred
    traces = {str(t["clause_id"]): t for t in payload.get("clause_traces") or []}
    assert traces["C999999"]["manifest_status"] == "tier_c_deferred"
    assert sample_encoded in set(payload.get("encoded_clause_ids") or [])


def test_apply_tier_c_defer_noop_when_all_clauses_already_encoded(tmp_path: Path) -> None:
    from scripts.sut.close_algorithmic_gaps import _apply_tier_c_defer

    manifest_path = tmp_path / "noop_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "encoded_clause_ids": ["C000100"],
                "tier_c_deferred_clause_ids": [],
                "clause_traces": [
                    {
                        "clause_id": "C000100",
                        "manifest_status": "encoded",
                        "encode_tier": "B",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    added = _apply_tier_c_defer(manifest_path, ["C000100"], {})
    assert added == 0


def test_true_unencoded_gaps_excludes_gate_b_sources() -> None:
    from scripts.sut.close_algorithmic_gaps import _true_unencoded_gaps
    from scripts.sut.prose.coverage import _load_gate_b_sources_from_rules_json

    coverage_path = _REPO / "data/gazette/sut_clause_coverage.parquet"
    if not coverage_path.is_file() or not _RULES_JSON.is_file():
        pytest.skip("coverage parquet or rules JSON missing")

    import pandas as pd

    gate_b = _load_gate_b_sources_from_rules_json(_RULES_JSON)
    coverage = pd.read_parquet(coverage_path)
    gaps = _true_unencoded_gaps(coverage)
    if gaps.empty or not gate_b:
        pytest.skip("no gaps or gate_b sources to compare")
    overlap = set(gaps["clause_id"].astype(str)) & gate_b
    assert overlap == set(), f"gate_b encoded clauses in gap set: {sorted(overlap)[:5]}"
