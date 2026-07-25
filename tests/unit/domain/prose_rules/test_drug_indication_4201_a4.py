"""Golden tests for combined §4.2.1 A4 batch (post-merge manifest check)."""

from __future__ import annotations

from tests.unit._helpers.brittle_guards import soft_floor

import json
from pathlib import Path

from scripts.sut.prose.manifest_index import encoded_like_clause_ids
from tests.unit._helpers.gate_b_cites import (
    cite_in_sources,
    cites_covered_by_encoded,
    resolve_gate_b_cites_to_clause_ids,
)
from scripts.sut.rule_sources import load_drug_sections_rules

_REPO = Path(__file__).resolve().parents[4]
_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4201_manifest.json"

BATCH_A4_RULES = load_drug_sections_rules(
    ["4.2.1.C-1", "4.2.1.C-2", "4.2.1.C-5", "4.2.1.C-7"]
)

_A4_GATE_B_SOURCES = frozenset(
    clause_id
    for rule in BATCH_A4_RULES
    for clause_id in (rule.get("gate_b_sources") or [])
)

def test_a4_combined_rule_count() -> None:
    soft_floor(len(BATCH_A4_RULES), 75, label='BATCH_A4_RULES')


def test_a4_encoded_clause_ids_in_manifest() -> None:
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    encoded = encoded_like_clause_ids(manifest)
    assert cites_covered_by_encoded(_A4_GATE_B_SOURCES, encoded)
    assert manifest.get("encoded_clause_count", 0) >= len(_A4_GATE_B_SOURCES)
