"""Unit tests for claim-line material pricing."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_price_material_lines_uses_billed_amount_when_code_present() -> None:
    from src.bilun.domain.analytics.materials import price_material_lines

    lines = price_material_lines(
        [
            {
                "name": "Koroner stent",
                "code": "KR1150",
                "unit_price": 800.0,
                "quantity": 1,
            }
        ]
    )

    assert len(lines) == 1
    line = lines[0]
    assert line.material_code == "KR1150"
    assert line.unit_price == 800.0
    assert line.total_price == 800.0
    assert line.source == "billed_amount"
    assert line.exactness_status == "exact"


def test_price_material_lines_without_code_is_missing_exact_inputs() -> None:
    from src.bilun.domain.analytics.materials import price_material_lines

    lines = price_material_lines(
        [{"name": "Bistüri ucu", "unit_price": 12.5, "quantity": 2}]
    )

    assert len(lines) == 1
    line = lines[0]
    assert line.source == "missing_code"
    assert line.exactness_status == "missing_exact_inputs"
    assert line.total_price == 25.0
    assert "material code required" in line.notes


def test_price_material_lines_does_not_fuzzy_match_by_name(monkeypatch) -> None:
    from src.bilun.domain.analytics.materials import price_material_lines

    monkeypatch.setattr(
        "src.bilun.domain.materials.catalog_lookup.lookup_ek3_list_price_try",
        lambda code: 999.0 if code == "REALCODE" else None,
    )

    lines = price_material_lines(
        [
            {
                "name": "Koroner stent",
                "code": "UNKNOWN",
                "unit_price": 0.0,
                "quantity": 1,
            }
        ]
    )

    assert lines[0].source == "ek3_catalog_miss"
    assert lines[0].exactness_status == "missing_exact_inputs"
    assert lines[0].total_price == 0.0


def test_validate_claim_returns_material_lines(monkeypatch) -> None:
    from src.bilun.domain.rule_engine import validate_claim

    monkeypatch.setattr(
        "src.bilun.domain.rule_engine.check_bundling_violations",
        lambda materials, procedure_code=None: [],
    )
    monkeypatch.setattr(
        "src.bilun.domain.rule_engine.check_exclusion_violations",
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
            "claim_id": "CLM-3",
            "materials": [
                {"name": "Stent", "code": "KR1150", "unit_price": 100.0, "quantity": 2}
            ],
        }
    )

    assert len(result.material_lines) == 1
    assert result.material_lines[0].total_price == 200.0
    assert result.total_claim_amount == 200.0
