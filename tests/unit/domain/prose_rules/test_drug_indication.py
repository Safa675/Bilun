"""Unit tests for §4.2 drug indication prose loader (Tier 3a seed)."""

from __future__ import annotations

from src.bilun.domain.prose_rules.drug_indication import (
    list_drug_indication_rules,
    load_drug_indication_rules,
)


def test_load_drug_indication_rules_seed() -> None:
    payload = load_drug_indication_rules()
    assert payload["rule_set_id"] == "drug_indication_prose"
    assert payload["sut_anchors"] == ["4.2"]
    assert list_drug_indication_rules() == []
