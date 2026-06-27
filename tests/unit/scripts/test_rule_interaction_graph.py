"""Tests for encoded-clause rule interaction graph builder."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from scripts.sut.build_rule_interaction_graph import build_rule_interaction_graph

_REPO = Path(__file__).resolve().parents[3]


def test_build_rule_interaction_graph_has_nodes_and_edges() -> None:
    graph = build_rule_interaction_graph()
    assert graph["node_count"] > 0
    assert graph["node_count"] == len(graph["nodes"])
    assert len(graph["edges"]) == graph["edge_count"]
    assert all("id" in n for n in graph["nodes"])
    edge_types = {e["type"] for e in graph["edges"]}
    assert edge_types <= {"same_billing_context", "same_rule_set"}


def test_graph_node_count_near_encoding_baseline() -> None:
    graph = build_rule_interaction_graph()
    cov_path = _REPO / "data" / "gazette" / "sut_clause_coverage.parquet"
    if not cov_path.is_file():
        return
    encoded = pl.read_parquet(cov_path).filter(pl.col("has_rule_encoding") == True).height  # noqa: E712
    assert abs(graph["node_count"] - encoded) / max(encoded, 1) < 0.15
