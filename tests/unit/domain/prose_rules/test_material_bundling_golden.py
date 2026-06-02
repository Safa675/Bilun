"""Golden Gate B fixtures for material bundling prose (Phase 3)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.bilun.domain.prose_rules.material_bundling import check_material_bundling_prose

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[4]
_GOLDEN_PATH = _ROOT / "data/gazette/prose_rules/golden/material_bundling_gate_b.json"
_PROSE_JSON = _ROOT / "data/gazette/prose_rules/material_bundling_prose.json"


def _load_golden_cases() -> list[dict]:
    payload = json.loads(_GOLDEN_PATH.read_text(encoding="utf-8"))
    return list(payload["cases"])


@pytest.mark.parametrize("case", _load_golden_cases(), ids=lambda c: c["clause_id"])
def test_gate_b_golden_expected_rule(case: dict) -> None:
    hits = check_material_bundling_prose([case["material"]])
    assert hits, f"no hit for clause {case['clause_id']}"
    assert hits[0]["rule_id"] == case["expected_rule_id"]


def test_prose_json_required_when_registry_implemented() -> None:
    from scripts.sut.prose.rule_registry import RULE_BY_ID

    entry = RULE_BY_ID["material_bundling_prose"]
    assert entry.coverage_status == "implemented"
    assert _PROSE_JSON.is_file()
    payload = json.loads(_PROSE_JSON.read_text(encoding="utf-8"))
    assert len(payload.get("rules", [])) >= len(_load_golden_cases())
