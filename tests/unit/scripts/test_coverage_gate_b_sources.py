"""Unit tests for coverage.py gate_b_sources dual-read resolve."""

from __future__ import annotations

import polars as pl

from scripts.sut.prose.coverage import _resolve_rule_json_gate_b_sources


def _frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "clause_id": ["C000001", "C000002", "C000003"],
            "clause_coordinate": ["1.1.(1)", "4.2.14.C.a", "4.2.14.C.a"],
            "clause_type": ["fikra", "bent", "bent"],
            "clause_number": [1, None, None],
            "clause_letter": [None, "a", "a"],
            "is_in_force": [True, True, True],
        }
    )


def test_resolve_without_frame_keeps_opaque_strings() -> None:
    payload = {
        "rules": [
            {"rule_id": "r1", "gate_b_sources": ["C000001", "1.1.(1)"]},
        ]
    }
    assert _resolve_rule_json_gate_b_sources(payload, None) == {
        "C000001",
        "1.1.(1)",
    }


def test_resolve_with_frame_maps_unique_coordinate() -> None:
    payload = {
        "rules": [
            {"rule_id": "r1", "gate_b_sources": ["C000099", "1.1.(1)"]},
        ]
    }
    assert _resolve_rule_json_gate_b_sources(payload, _frame()) == {
        "C000099",
        "C000001",
    }


def test_resolve_skips_ambiguous_coordinate() -> None:
    payload = {
        "rules": [
            {
                "rule_id": "r1",
                "gate_b_sources": ["C000001", "4.2.14.C.a", "1.1.(1)"],
            },
        ]
    }
    # Ambiguous 4.2.14.C.a skipped; C* + unique coordinate kept.
    assert _resolve_rule_json_gate_b_sources(payload, _frame()) == {
        "C000001",
    }


def test_resolve_skips_unknown_coordinate() -> None:
    payload = {
        "rules": [
            {"rule_id": "r1", "gate_b_sources": ["9.9.9.(1)", "C000001"]},
        ]
    }
    assert _resolve_rule_json_gate_b_sources(payload, _frame()) == {"C000001"}
