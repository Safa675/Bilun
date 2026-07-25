"""Unit tests for clause_identity dual-read (god plan Track A1)."""

from __future__ import annotations

import polars as pl
import pytest

from scripts.sut.prose.clause_identity import (
    AmbiguousClauseCiteError,
    UnknownClauseCiteError,
    encoded_clause_ids_from_rules,
    filter_encode_eligible,
    is_clause_coordinate,
    is_clause_id,
    is_encode_eligible_row,
    is_gate_b_source_ref,
    resolve_gate_b_ref_to_clause_ids,
    resolve_gate_b_sources_to_clause_ids,
)


def _frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "clause_id": ["C000001", "C000002", "C000003", "C000004", "C000005"],
            "clause_coordinate": [
                "1.1.(1)",
                "4.2.14.C.a",
                "4.2.14.C.a",
                "1.2",
                None,
            ],
            "clause_type": ["fikra", "bent", "bent", "section_heading", "chapter"],
            "clause_number": [1, None, None, None, None],
            "clause_letter": [None, "a", "a", None, None],
            "is_in_force": [True, True, True, True, True],
        }
    )


def test_ref_classifiers() -> None:
    assert is_clause_id("C000646")
    assert is_clause_id("F000001")
    assert not is_clause_id("4.2.24.B.(3)")
    assert is_clause_coordinate("4.2.24.B.(3)")
    assert is_clause_coordinate("4.2.24.B.(3).a")
    assert is_clause_coordinate("1.1")
    assert not is_clause_coordinate("C000646")
    assert is_gate_b_source_ref("C000646")
    assert is_gate_b_source_ref("1.8.2.(1)")
    assert not is_gate_b_source_ref("not-a-cite")


def test_encode_eligible_predicate() -> None:
    frame = _frame()
    eligible = filter_encode_eligible(frame)
    assert set(eligible["clause_id"].to_list()) == {"C000001", "C000002", "C000003"}
    assert is_encode_eligible_row(frame.row(0, named=True))
    assert not is_encode_eligible_row(frame.row(3, named=True))


def test_resolve_clause_id_passthrough() -> None:
    assert resolve_gate_b_ref_to_clause_ids("C000001", _frame()) == ["C000001"]


def test_resolve_unique_coordinate() -> None:
    assert resolve_gate_b_ref_to_clause_ids("1.1.(1)", _frame()) == ["C000001"]


def test_resolve_ambiguous_coordinate_raises() -> None:
    with pytest.raises(AmbiguousClauseCiteError, match="4.2.14.C.a"):
        resolve_gate_b_ref_to_clause_ids("4.2.14.C.a", _frame())


def test_resolve_ambiguous_allowed() -> None:
    ids = resolve_gate_b_ref_to_clause_ids(
        "4.2.14.C.a",
        _frame(),
        allow_ambiguous=True,
    )
    assert ids == ["C000002", "C000003"]


def test_resolve_unknown_raises() -> None:
    with pytest.raises(UnknownClauseCiteError):
        resolve_gate_b_ref_to_clause_ids("9.9.9.(1)", _frame())


def test_resolve_unknown_clause_id_passthrough() -> None:
    assert resolve_gate_b_ref_to_clause_ids("C999999", _frame()) == ["C999999"]


def test_encoded_clause_ids_from_rules_resolves_coordinates() -> None:
    rules = [
        {"rule_id": "r1", "gate_b_sources": ["C000001", "1.1.(1)"]},
    ]
    assert encoded_clause_ids_from_rules(rules, _frame()) == {"C000001"}


def test_encoded_clause_ids_without_frame_keeps_opaque_strings() -> None:
    rules = [{"rule_id": "r1", "gate_b_sources": ["1.1.(1)", "C000001"]}]
    assert encoded_clause_ids_from_rules(rules, None) == {"1.1.(1)", "C000001"}


def test_resolve_many() -> None:
    assert resolve_gate_b_sources_to_clause_ids(
        ["C000001", "1.1.(1)"],
        _frame(),
    ) == {"C000001"}
