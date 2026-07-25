"""Unit tests for the migrated June 2026 fact-check audit rollup."""

from __future__ import annotations

import pytest

from src.bilun.domain.sut.fact_check_audit import (
    AUDIT_TOTAL_UNITS,
    FACT_CHECK_AUDIT_UNITS,
    build_rule_fact_check_index,
    fact_check_rollup,
)
from src.bilun.domain.sut.rule_registry import RULE_REGISTRY
from tests.unit._helpers.brittle_guards import soft_floor

pytestmark = pytest.mark.unit

_ALLOWED_VERDICTS = frozenset(
    {
        "COMPLIANT",
        "PARTIAL",
        "HEURISTIC",
        "NEEDS_CLAIM_LINES",
        "WRONG",
        "OUT_OF_SCOPE",
    }
)


def test_audit_unit_count_matches_constant() -> None:
    # Same-module constant identity (not a magic census of the world).
    assert len(FACT_CHECK_AUDIT_UNITS) == AUDIT_TOTAL_UNITS
    soft_floor(AUDIT_TOTAL_UNITS, 20, label="fact_check audit units")


def test_rollup_verdict_counts_match_master() -> None:
    rollup = fact_check_rollup()
    counts = rollup["by_verdict"]
    assert set(counts) <= _ALLOWED_VERDICTS
    assert sum(counts.values()) == len(FACT_CHECK_AUDIT_UNITS)
    soft_floor(counts.get("COMPLIANT", 0), 8, label="COMPLIANT")
    soft_floor(counts.get("PARTIAL", 0), 10, label="PARTIAL")
    assert counts.get("WRONG", 0) == 0
    assert counts.get("NEEDS_CLAIM_LINES", 0) == 0
    assert rollup["audit_closed"] == "2026-06"


def test_registry_entries_carry_fact_check_when_mapped() -> None:
    by_id = {entry.rule_id: entry for entry in RULE_REGISTRY}
    assert by_id["copay_rate_ek2c1"].fact_check_verdict == "COMPLIANT"
    assert "L2.4" in by_id["copay_rate_ek2c1"].fact_check_units
    assert by_id["pricing_ek2b"].fact_check_verdict == "COMPLIANT"
    assert by_id["billing_documents"].fact_check_verdict is None


def test_rule_index_matches_registry_enrichment() -> None:
    index = build_rule_fact_check_index()
    for entry in RULE_REGISTRY:
        if entry.rule_id not in index:
            assert entry.fact_check_verdict is None
            continue
        meta = index[entry.rule_id]
        assert entry.fact_check_verdict == meta["fact_check_verdict"]
        assert entry.fact_check_units == meta["fact_check_units"]


def test_drug_indication_prose_has_supplemental_fact_check() -> None:
    by_id = {entry.rule_id: entry for entry in RULE_REGISTRY}
    entry = by_id["drug_indication_prose"]
    assert entry.fact_check_verdict == "PARTIAL"
    assert "SUT-4.2.14.C" in entry.fact_check_units
    assert "4.2.14.C" in (entry.fact_check_note or "")
