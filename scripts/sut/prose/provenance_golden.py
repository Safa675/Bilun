"""Derive provenance golden cases from rule gate_b_sources (Track B3).

Provenance goldens are not an authored source of truth — they restate
``gate_b_sources``. Prefer deriving cases at test/compile time.
"""

from __future__ import annotations

from typing import Any


def provenance_cases_from_rules(
    rules: list[dict[str, Any]],
    *,
    include_encode_batch: bool = False,
) -> list[dict[str, Any]]:
    """Build ``{clause_id, expected_rule_id[, encode_batch]}`` cases from rules."""
    cases: list[dict[str, Any]] = []
    for rule in rules:
        rule_id = str(rule.get("rule_id") or "")
        if not rule_id:
            continue
        batch = rule.get("encode_batch")
        for src in rule.get("gate_b_sources") or []:
            if src is None or not str(src).strip():
                continue
            case: dict[str, Any] = {
                "clause_id": str(src),
                "expected_rule_id": rule_id,
            }
            if include_encode_batch and batch is not None:
                case["encode_batch"] = batch
            cases.append(case)
    cases.sort(key=lambda c: (c["clause_id"], c["expected_rule_id"]))
    return cases
