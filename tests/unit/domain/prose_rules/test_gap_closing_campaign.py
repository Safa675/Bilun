"""Regression tests for the §4.2 + gap-closing campaign batches.

Validates: rule structure, provenance integrity (every gate_b_sources clause
exists in the SUT corpus), unique rule_ids, and section coverage for the
drug_combination_4_2, gap_closing_treatment_2, and gap_closing_misc rule sets.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_RULES_DIR = _PROJECT_ROOT / "data/gazette/prose_rules"
_CLAUSES_PATH = _PROJECT_ROOT / "data/gazette/sut_clauses.parquet"

pytestmark = pytest.mark.unit
_REQUIRED = {"rule_id", "sut_section", "condition", "action", "gate_b_sources"}


@pytest.fixture(scope="module")
def clauses_frame() -> set[str]:
    return set(pl.read_parquet(_CLAUSES_PATH)["clause_id"].to_list())


@pytest.fixture(scope="module")
def rule_sets() -> dict[str, list[dict]]:
    out = {}
    for name in ("drug_combination_4_2", "gap_closing_treatment_2", "gap_closing_misc"):
        payload = json.loads((_RULES_DIR / f"{name}.json").read_text(encoding="utf-8"))
        out[name] = payload["rules"]
    return out


def test_all_rules_have_required_keys(rule_sets):
    for name, rules in rule_sets.items():
        assert rules, f"{name}: empty"
        for r in rules:
            missing = _REQUIRED - set(r.keys())
            assert not missing, f"{name}/{r.get('rule_id')}: missing {missing}"


def test_rule_ids_unique_within_campaign(rule_sets):
    all_ids = [r["rule_id"] for rules in rule_sets.values() for r in rules]
    assert len(all_ids) == len(set(all_ids)), "duplicate rule_id across campaign"


def test_provenance_integrity(rule_sets, clauses_frame):
    """Every gate_b_sources clause ID must exist in the SUT corpus."""
    for name, rules in rule_sets.items():
        for r in rules:
            for cid in r.get("gate_b_sources") or []:
                assert cid in clauses_frame, f"{name}/{r['rule_id']}: unknown clause {cid}"


def test_all_rules_have_provenance(rule_sets):
    for name, rules in rule_sets.items():
        for r in rules:
            assert len(r.get("gate_b_sources") or []) >= 1, f"{name}/{r['rule_id']}: no provenance"


def test_drug_combination_has_tier_c_advisory(rule_sets):
    """The §4.2 batch must include Tier C biomarker rules (advisory severity)."""
    tier_c = [r for r in rule_sets["drug_combination_4_2"]
              if r.get("action", {}).get("tier") == "C"]
    assert len(tier_c) >= 10, f"expected ≥10 Tier C advisory rules, got {len(tier_c)}"


def test_campaign_covers_broad_sections(rule_sets):
    sections = {r["sut_section"] for rules in rule_sets.values() for r in rules}
    expected = {"4.2.14.C", "2.2.2.B", "2.5.3.A", "2.6.3", "1.8.5",
                "3.1.1", "4.1.9", "5.2.2", "6.3.2"}
    missing = expected - sections
    assert not missing, f"campaign missing sections: {missing}"


def test_golden_round_trips(rule_sets):
    for name, rules in rule_sets.items():
        golden_path = _RULES_DIR / "golden" / f"{name}.json"
        if not golden_path.exists():
            continue
        golden = json.loads(golden_path.read_text(encoding="utf-8"))
        rule_ids = {r["rule_id"] for r in rules}
        for case in golden["cases"]:
            assert case["expected_rule_id"] in rule_ids, (
                f"{name} golden references unknown rule {case['expected_rule_id']}"
            )
