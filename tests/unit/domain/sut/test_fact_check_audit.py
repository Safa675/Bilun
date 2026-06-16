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

pytestmark = pytest.mark.unit


def test_audit_has_28_units() -> None:
    assert len(FACT_CHECK_AUDIT_UNITS) == AUDIT_TOTAL_UNITS == 28


def test_rollup_verdict_counts_match_master() -> None:
    rollup = fact_check_rollup()
    counts = rollup["by_verdict"]
    assert counts["COMPLIANT"] == 10
    assert counts["PARTIAL"] == 17
    assert counts["HEURISTIC"] == 1
    assert counts["NEEDS_CLAIM_LINES"] == 0
    assert counts["WRONG"] == 0
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
