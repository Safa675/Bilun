"""Track B helpers: deferral non_actionable loader + provenance derivation."""

from __future__ import annotations

from scripts.sut.prose.coverage import _load_non_actionable_clause_ids
from scripts.sut.prose.provenance_golden import provenance_cases_from_rules


def test_non_actionable_ids_load_from_deferral_table() -> None:
    ids = _load_non_actionable_clause_ids()
    assert len(ids) >= 500
    assert all(cid.startswith("C") for cid in ids)


def test_provenance_cases_from_rules_expand_gate_b_sources() -> None:
    rules = [
        {
            "rule_id": "r1",
            "gate_b_sources": ["1.1.(1)", "C000002"],
            "encode_batch": "b1",
        }
    ]
    cases = provenance_cases_from_rules(rules, include_encode_batch=True)
    assert cases == [
        {"clause_id": "1.1.(1)", "expected_rule_id": "r1", "encode_batch": "b1"},
        {"clause_id": "C000002", "expected_rule_id": "r1", "encode_batch": "b1"},
    ]
