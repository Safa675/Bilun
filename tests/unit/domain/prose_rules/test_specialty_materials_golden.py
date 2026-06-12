"""Golden Gate B fixtures for §3.3 specialty materials prose (L4.4)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.bilun.domain.prose_rules.specialty_materials import check_specialty_materials_prose

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[4]
_GOLDEN_PATH = _ROOT / "data/gazette/prose_rules/golden/specialty_materials_gate_b.json"
_PROSE_JSON = _ROOT / "data/gazette/prose_rules/specialty_materials_prose.json"


def _load_golden_cases() -> list[dict]:
    payload = json.loads(_GOLDEN_PATH.read_text(encoding="utf-8"))
    return list(payload["cases"])


@pytest.mark.parametrize("case", _load_golden_cases(), ids=lambda c: c["expected_rule_id"])
def test_gate_b_golden_expected_rule(case: dict) -> None:
    hits = check_specialty_materials_prose([case["material"]])
    assert hits, f"no hit for clause {case['clause_id']}"
    assert hits[0]["rule_id"] == case["expected_rule_id"]


def test_prose_json_required_when_registry_implemented() -> None:
    from scripts.sut.prose.rule_registry import RULE_BY_ID

    entry = RULE_BY_ID["specialty_materials_prose"]
    assert entry.coverage_status == "implemented"
    assert _PROSE_JSON.is_file()
    payload = json.loads(_PROSE_JSON.read_text(encoding="utf-8"))
    assert len(payload.get("rules", [])) >= len(_load_golden_cases())
