"""Golden Gate B + JSON integrity for §2.2 payment_method_2_2 (C2 batches)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[4]
_PROSE_JSON = _ROOT / "data/gazette/prose_rules/payment_method_2_2.json"
_MANIFEST = _ROOT / "data/gazette/prose_manifests/L2.2_payment_method_encoded_manifest.json"
_GOLDEN_BATCH1 = _ROOT / "data/gazette/prose_rules/golden/payment_method_2_2_batch1.json"
_GOLDEN_BATCH2 = _ROOT / "data/gazette/prose_rules/golden/payment_method_2_2_batch2.json"
_GOLDEN_BATCH3 = _ROOT / "data/gazette/prose_rules/golden/payment_method_2_2_batch3.json"
_GOLDEN_BATCH4 = _ROOT / "data/gazette/prose_rules/golden/payment_method_2_2_batch4.json"
_BATCH4_MIN_RULES = 39
_BATCH4_MIN_ENCODED = 38


def _load_rules() -> list[dict]:
    payload = json.loads(_PROSE_JSON.read_text(encoding="utf-8"))
    return list(payload.get("rules") or [])


def _rules_by_id() -> dict[str, dict]:
    return {str(rule["rule_id"]): rule for rule in _load_rules()}


def _load_golden_cases(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload["cases"])


def test_prose_json_has_batch4_rule_count() -> None:
    rules = _load_rules()
    assert len(rules) >= _BATCH4_MIN_RULES


def test_all_rules_have_gate_b_sources() -> None:
    for rule in _load_rules():
        sources = rule.get("gate_b_sources") or []
        assert sources, f"missing gate_b_sources on {rule['rule_id']}"


def test_manifest_encoded_clause_ids_match_json() -> None:
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    from_json = sorted(
        {
            clause_id
            for rule in _load_rules()
            for clause_id in (rule.get("gate_b_sources") or [])
        }
    )
    encoded = sorted(manifest.get("encoded_clause_ids") or manifest.get("encoded_clause_ids") or [])
    assert encoded == from_json
    assert len(encoded) >= _BATCH4_MIN_ENCODED


@pytest.mark.parametrize(
    "case",
    _load_golden_cases(_GOLDEN_BATCH1)
    + _load_golden_cases(_GOLDEN_BATCH2)
    + _load_golden_cases(_GOLDEN_BATCH3)
    + _load_golden_cases(_GOLDEN_BATCH4),
    ids=lambda c: c["clause_id"],
)
def test_gate_b_golden_clause_maps_to_rule(case: dict) -> None:
    rules = _rules_by_id()
    rule = rules[case["expected_rule_id"]]
    assert case["clause_id"] in (rule.get("gate_b_sources") or [])


def test_batch1_itemized_basis_rule_shape() -> None:
    rule = _rules_by_id()["2.2.2.A(1).itemized_basis"]
    assert rule["action"]["payment_method"] == "itemized"
    assert rule["gate_b_sources"] == ["C000639"]


def test_batch3_home_health_daily_cap_rule_shape() -> None:
    rule = _rules_by_id()["2.2.1.B-3.(1).home_health_daily_cap"]
    assert rule["action"]["max_bill_count"] == 1
    assert rule["gate_b_sources"] == ["C000618"]


def test_resolve_payment_method_is_memoized() -> None:
    """Phase 1: identical input tuples are served from the lru_cache.

    The inner cached function should record a hit on the second call with the
    same args, confirming the 5N–9N re-derivation is collapsed to N.
    """
    from src.bilun.domain.prose_rules.payment_method import (
        _resolve_payment_method_cached,
        resolve_payment_method,
    )

    _resolve_payment_method_cached.cache_clear()
    first = resolve_payment_method("520030", care_setting="inpatient")
    second = resolve_payment_method("520030", care_setting="inpatient")
    assert first is second  # cached → identical object
    info = _resolve_payment_method_cached.cache_info()
    assert info.hits >= 1, f"expected cache hit, got {info}"
    _resolve_payment_method_cached.cache_clear()
