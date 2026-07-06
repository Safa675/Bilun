"""Golden Gate B + JSON integrity for §1.8 copay_general_1_8 (D3 batch-1/2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[4]
_PROSE_JSON = _ROOT / "data/gazette/prose_rules/copay_general_1_8.json"
_MANIFEST = _ROOT / "data/gazette/prose_manifests/L1.8_copay_exemption_encoded_manifest.json"
_GOLDEN_BATCH1 = _ROOT / "data/gazette/prose_rules/golden/copay_general_1_8_batch1.json"
_GOLDEN_BATCH2 = _ROOT / "data/gazette/prose_rules/golden/copay_general_1_8_batch2.json"
_BATCH1_MIN_RULES = 17
_BATCH1_MIN_ENCODED = 30


def _load_rules() -> list[dict]:
    payload = json.loads(_PROSE_JSON.read_text(encoding="utf-8"))
    return list(payload.get("rules") or [])


def _rules_by_id() -> dict[str, dict]:
    return {str(rule["rule_id"]): rule for rule in _load_rules()}


def _load_golden_cases() -> list[dict]:
    cases: list[dict] = []
    for path in (_GOLDEN_BATCH1, _GOLDEN_BATCH2):
        payload = json.loads(path.read_text(encoding="utf-8"))
        cases.extend(payload["cases"])
    return cases


def test_prose_json_has_batch1_rule_count() -> None:
    rules = _load_rules()
    assert len(rules) >= _BATCH1_MIN_RULES


def test_all_rules_have_gate_b_sources() -> None:
    for rule in _load_rules():
        sources = rule.get("gate_b_sources") or []
        assert sources, f"missing gate_b_sources on {rule['rule_id']}"


def test_manifest_encoded_clause_ids_include_json_and_compositor() -> None:
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    from_json = sorted(
        {
            clause_id
            for rule in _load_rules()
            for clause_id in (rule.get("gate_b_sources") or [])
        }
    )
    encoded = sorted(manifest.get("encoded_clause_ids") or [])
    for clause_id in from_json:
        assert clause_id in encoded
    assert len(encoded) >= _BATCH1_MIN_ENCODED


@pytest.mark.parametrize("case", _load_golden_cases(), ids=lambda c: c["clause_id"])
def test_gate_b_golden_clause_maps_to_rule(case: dict) -> None:
    rules = _rules_by_id()
    rule = rules[case["expected_rule_id"]]
    assert case["clause_id"] in (rule.get("gate_b_sources") or [])


def test_batch1_organ_transplant_rule_shape() -> None:
    rule = _rules_by_id()["1.8.5.(10).organ_nakli"]
    assert rule["service_type"] == "copay_exemption"
    assert rule["action"]["copay_treatment"] == "no_copay"
    assert rule["gate_b_sources"] == ["C000364"]


def test_batch1_control_exam_waives_visit_copay_only() -> None:
    rule = _rules_by_id()["1.8.5.(4).kontrol_muayenesi"]
    assert rule["action"]["waives_sections"] == ["1.8.1"]
    assert rule["gate_b_sources"] == ["C000358"]


def test_batch2_academy_exemption_rules_waive_visit_drug_material() -> None:
    polis = _rules_by_id()["1.8.5.(18).polis_akademisi"]
    harp = _rules_by_id()["1.8.5.(19).harp_okulu"]
    assert polis["gate_b_sources"] == ["C000372"]
    assert harp["gate_b_sources"] == ["C000373"]
    assert polis["action"]["waives_sections"] == ["1.8.1", "1.8.2", "1.8.3"]
    assert harp["action"]["waives_sections"] == ["1.8.1", "1.8.2", "1.8.3"]


def test_material_service_type_duplicate_does_not_break_dispatch() -> None:
    """W2.5i (LOW, Bugbot): two rules share service_type='material'
    (1.8.3.(1).protez_ortez and 1.8.3.(2)). The dict-comprehension index used
    last-wins, silently dropping 1.8.3.(1).protez_ortez. Both carry identical
    rate tables so dispatch output is unaffected, but the index must be
    deterministic (first-wins, keeping the more-specific condition-gated rule)
    and must not crash on the duplicate. This test pins the rate output and
    guards against a future rule edit that diverges the duplicate rates.
    """
    from src.bilun.domain.prose_rules.copay_general import (
        _rules_by_service_type,
        resolve_material_copay_rate,
    )

    index = _rules_by_service_type()
    # The material key is present (not lost to dedup) and deterministic.
    assert "material" in index
    # Both duplicate rules produce the same rates, so resolve_* returns the
    # canonical rate regardless of which entry the index kept.
    assert resolve_material_copay_rate("sgk_income_recipient") == 0.1
    assert resolve_material_copay_rate("other") == 0.2

