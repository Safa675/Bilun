"""Unit tests for Track E stale_clause_refs dual-read."""

from __future__ import annotations

import polars as pl
import pytest

from scripts.agent.stale_clause_refs import classify_refs

pytestmark = pytest.mark.unit


def test_classify_refs_resolves_coordinates_without_tier4() -> None:
    refs = pl.DataFrame(
        {
            "rule_set_id": ["demo", "demo"],
            "rule_id": ["r1", "r2"],
            "gate_b_ref": ["2.2.1.(1)", "C999999"],
        }
    )
    clauses = pl.DataFrame(
        {
            "clause_id": ["C000001"],
            "clause_coordinate": ["2.2.1.(1)"],
            "is_in_force": [True],
            "is_superseded_marker": [False],
            "had_struck_content": [False],
        }
    )
    out = classify_refs(refs, clauses)
    coord_row = out.filter(pl.col("gate_b_ref") == "2.2.1.(1)")
    assert coord_row.height == 1
    assert coord_row["tier"][0] == "OK"
    assert coord_row["clause_id"][0] == "C000001"
    dangling = out.filter(pl.col("gate_b_ref") == "C999999")
    assert dangling.height == 1
    assert dangling["tier"][0] == "TIER 4"
