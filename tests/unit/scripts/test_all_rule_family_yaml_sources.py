"""Parity tests for prose rule YAML source families."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from scripts.sut.rule_sources import (
    RULE_FAMILY_YAML_DIRS,
    load_rule_family_yaml_rules,
    rule_family_yaml_paths,
)

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_RULES_DIR = _REPO / "data/gazette/prose_rules"


def _runtime_rules(rule_set_id: str) -> list[dict]:
    payload = json.loads((_RULES_DIR / f"{rule_set_id}.json").read_text(encoding="utf-8"))
    rules = payload.get("rules") or []
    assert isinstance(rules, list)
    return rules


@pytest.mark.parametrize("rule_set_id", sorted(RULE_FAMILY_YAML_DIRS))
def test_yaml_sources_match_runtime_rule_json(rule_set_id: str) -> None:
    runtime_rules = _runtime_rules(rule_set_id)
    yaml_rules = load_rule_family_yaml_rules(rule_set_id)

    runtime_ids = [str(rule["rule_id"]) for rule in runtime_rules]
    yaml_ids = [str(rule["rule_id"]) for rule in yaml_rules]

    assert Counter(yaml_ids) == Counter(runtime_ids)
    assert len(yaml_rules) == len(runtime_rules)

    runtime_by_id = {str(rule["rule_id"]): rule for rule in runtime_rules}
    for rule in yaml_rules:
        assert rule == runtime_by_id[str(rule["rule_id"])]


@pytest.mark.parametrize("rule_set_id", sorted(RULE_FAMILY_YAML_DIRS))
def test_yaml_file_count_matches_runtime_sections(rule_set_id: str) -> None:
    runtime_rules = _runtime_rules(rule_set_id)
    expected_groups = {
        str(rule.get("sut_section") or "__no_sut_section__") for rule in runtime_rules
    }

    if rule_set_id == "drug_indication_prose":
        yaml_rules = load_rule_family_yaml_rules(rule_set_id)
        yaml_sections = {str(r.get("sut_section") or "__no_sut_section__") for r in yaml_rules}
        assert yaml_sections == expected_groups
    else:
        assert len(rule_family_yaml_paths(rule_set_id)) == len(expected_groups)
