"""Unit tests for claim validation orchestrator (L1.3)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_validate_claim_bundling_violation(monkeypatch) -> None:
    from src.bilun.domain.rule_engine import validate_claim

    monkeypatch.setattr(
        "src.bilun.domain.rule_engine.check_bundling_violations",
        lambda materials, procedure_code=None: [
            {
                "severity": "warning",
                "material_name": materials[0]["name"],
                "message": "Bundled consumable billed separately",
                "savings_try": 12.5,
            }
        ],
    )
    monkeypatch.setattr(
        "src.bilun.domain.rule_engine.check_exclusion_violations",
        lambda materials: [],
    )
    monkeypatch.setattr(
        "src.bilun.domain.rule_engine.estimate_material_costs",
        lambda materials: [],
    )
    monkeypatch.setattr(
        "src.bilun.domain.rule_engine.check_material_bundling_prose",
        lambda materials, procedure_code=None: [],
    )
    monkeypatch.setattr(
        "src.bilun.domain.rule_engine.check_specialty_materials_prose",
        lambda materials: [],
    )

    result = validate_claim(
        {
            "claim_id": "CLM-1",
            "procedure_code": "520030",
            "materials": [{"name": "Bistüri ucu", "unit_price": 12.5, "quantity": 1}],
        }
    )
    assert result.n_bundling_violations == 1
    assert result.total_savings_try == 12.5
    assert result.is_valid is True


def test_validate_claim_exclusion_makes_invalid(monkeypatch) -> None:
    from src.bilun.domain.rule_engine import validate_claim

    monkeypatch.setattr(
        "src.bilun.domain.rule_engine.check_bundling_violations",
        lambda materials, procedure_code=None: [],
    )
    monkeypatch.setattr(
        "src.bilun.domain.rule_engine.check_exclusion_violations",
        lambda materials: [
            {
                "severity": "error",
                "material_name": materials[0]["name"],
                "message": "Non-reimbursable material",
                "risk_amount": 50.0,
            }
        ],
    )
    monkeypatch.setattr(
        "src.bilun.domain.rule_engine.estimate_material_costs",
        lambda materials: [],
    )
    monkeypatch.setattr(
        "src.bilun.domain.rule_engine.check_material_bundling_prose",
        lambda materials, procedure_code=None: [],
    )
    monkeypatch.setattr(
        "src.bilun.domain.rule_engine.check_specialty_materials_prose",
        lambda materials: [],
    )

    result = validate_claim(
        {
            "claim_id": "CLM-2",
            "materials": [{"name": "Excluded item", "unit_price": 50.0}],
        }
    )
    assert result.n_exclusion_violations == 1
    assert result.total_risk_try == 50.0
    assert result.is_valid is False
