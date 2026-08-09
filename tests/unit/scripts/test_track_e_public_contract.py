"""Track E — public contract is clause_coordinate; C* is opaque/collision-only."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from scripts.sut.prose.clause_identity import is_clause_coordinate, is_clause_id
from src.bilun.domain.constants import SUT_CLAUSES_PATH
from src.bilun.domain.sut import rules_catalog as rc

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[3]
_DEFERRAL = _ROOT / "data" / "gazette" / "prose_rules" / "deferral_table.yaml"
_SCHEMA = _ROOT / "data" / "gazette" / "prose_rules" / "schemas" / "base_rule_set.schema.json"
_CANONICAL = (
    _ROOT / "data" / "gazette" / "prose_manifests" / "schemas" / "canonical_v1.schema.json"
)

_needs_clauses = pytest.mark.skipif(
    not SUT_CLAUSES_PATH.exists(), reason="sut_clauses.parquet missing"
)


def test_rule_schema_accepts_coordinates_and_documents_c_star_policy() -> None:
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    gate = schema["$defs"]["rule"]["properties"]["gate_b_sources"]
    assert "coordinate" in (gate.get("description") or "").lower() or "C*" in (
        gate.get("description") or ""
    )
    patterns = [item.get("pattern") for item in gate["items"]["anyOf"]]
    assert any(p and p.startswith("^[CF]") for p in patterns)  # collision / opaque
    assert any(p and p.startswith("^[0-9]") for p in patterns)  # public coordinate


def test_canonical_manifest_exposes_encoded_clause_coordinates() -> None:
    schema = json.loads(_CANONICAL.read_text(encoding="utf-8"))
    props = schema["properties"]
    assert "encoded_clause_coordinates" in props
    assert "opaque" in (props["encoded_clause_ids"].get("description") or "").lower()


def test_deferral_table_has_coordinates_for_every_entry() -> None:
    payload = yaml.safe_load(_DEFERRAL.read_text(encoding="utf-8"))
    entries = payload.get("entries") or []
    assert entries
    missing = [
        e.get("clause_id")
        for e in entries
        if not str(e.get("clause_coordinate") or "").strip()
    ]
    assert not missing, f"deferral rows missing clause_coordinate: {missing[:5]}"


@_needs_clauses
def test_api_lookup_by_coordinate_does_not_require_c_star() -> None:
    rc.reset_cache()
    by_id = rc.get_clause("C000003")
    assert by_id is not None
    coord = by_id.get("clause_coordinate")
    assert coord and is_clause_coordinate(str(coord))
    by_coord = rc.get_clause(str(coord))
    assert by_coord is not None
    assert by_coord["clause_key"] == by_id["clause_key"]


def test_deferral_list_exposes_coordinates() -> None:
    rc.reset_cache()
    rows, total = rc.list_deferrals(limit=20)
    assert total > 0
    assert any(r.get("clause_coordinate") for r in rows)


def test_is_clause_id_still_recognizes_opaque_keys() -> None:
    assert is_clause_id("C000003")
    assert is_clause_id("F000001")
    assert not is_clause_id("2.2.1.(1)")
