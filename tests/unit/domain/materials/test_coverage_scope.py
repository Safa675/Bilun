"""L1.4 — material bundling coverage scope boundary."""

from src.bilun.domain.materials.coverage_scope import (
    EK3B1_ROW_COUNT,
    material_bundling_coverage_scope,
    prose_coverage_tier,
    prose_engine_status,
    prose_rule_count,
)
from src.bilun.domain.rule_engine import validate_claim


def test_prose_engine_status_implemented_when_json_present() -> None:
    assert prose_rule_count() >= 7
    assert prose_engine_status() == "implemented"
    assert prose_coverage_tier() == "partial"


def test_material_bundling_coverage_scope_implemented() -> None:
    scope = material_bundling_coverage_scope()
    assert scope["prose_engine_status"] == "implemented"
    assert scope["prose_coverage_tier"] == "partial"
    assert scope["prose_rules_implemented"] >= 22
    assert scope["prose_rule_id"] == "material_bundling_prose"
    assert "3.1" in scope["prose_section_prefixes"]
    assert scope["ek3b1_row_count"] == EK3B1_ROW_COUNT
    assert scope.get("prose_effective_date")
    assert scope["medula_overlap_classification"] == "additive"
    assert scope.get("medula_savings_note")
    assert scope.get("gate_b_deferred_clauses", 0) >= 0


def test_validate_claim_includes_coverage_scope() -> None:
    result = validate_claim(
        {
            "claim_id": "T",
            "materials": [{"name": "Test malzeme", "unit_price": 1.0, "quantity": 1}],
        }
    )
    assert result.coverage_scope["prose_engine_status"] == "implemented"
    assert result.coverage_scope["prose_coverage_tier"] == "partial"
