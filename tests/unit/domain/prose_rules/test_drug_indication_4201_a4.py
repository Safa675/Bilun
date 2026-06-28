"""Golden tests for combined §4.2.1 A4 batch (post-merge manifest check)."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.sut.prose.drug_indication_4201_a4_batch_rules import BATCH_A4_RULES

_REPO = Path(__file__).resolve().parents[4]
_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4201_manifest.json"

_A4_GATE_B_SOURCES = frozenset(
    clause_id
    for rule in BATCH_A4_RULES
    for clause_id in (rule.get("gate_b_sources") or [])
)


def test_a4_combined_rule_count() -> None:
    assert len(BATCH_A4_RULES) == 21


def test_a4_gate_b_sources_encoded_in_manifest() -> None:
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    encoded = frozenset(manifest.get("encoded_clause_ids") or [])
    assert _A4_GATE_B_SOURCES <= encoded
    assert manifest.get("encoded_clause_count", 0) >= len(_A4_GATE_B_SOURCES)
