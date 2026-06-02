"""Unit tests for EK-3B-1 bundling rules (L1.1)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_bundling_code_resolved_match_is_error(monkeypatch) -> None:
    from src.bilun.domain.rules import bundling_rules as mod

    monkeypatch.setattr(
        mod,
        "get_bundled_consumables",
        lambda: [
            {
                "item_name": "Bistüri ucu veya disposable bistüri",
                "description": "Cerrahi malzemeler",
            }
        ],
    )
    monkeypatch.setattr(
        mod,
        "resolve_material_name_by_code",
        lambda code: "Bistüri ucu veya disposable bistüri" if code == "OP1000" else None,
    )

    violations = mod.check_bundling_violations(
        [{"name": "Other label", "code": "OP1000", "unit_price": 10.0, "quantity": 1}],
        procedure_code="520030",
    )
    assert len(violations) == 1
    assert violations[0]["severity"] == "error"
    assert violations[0]["match_kind"] == "code_resolved"
    assert violations[0]["savings_try"] == 10.0


def test_bundling_fuzzy_name_only_is_warning(monkeypatch) -> None:
    from src.bilun.domain.rules import bundling_rules as mod

    monkeypatch.setattr(
        mod,
        "get_bundled_consumables",
        lambda: [{"item_name": "Eldiven", "description": "Cerrahi malzemeler"}],
    )
    monkeypatch.setattr(mod, "resolve_material_name_by_code", lambda code: None)

    violations = mod.check_bundling_violations(
        [{"name": "Eldvn", "unit_price": 5.0, "quantity": 1}],
    )
    assert len(violations) == 1
    assert violations[0]["match_kind"] == "name_fuzzy"
    assert violations[0]["severity"] == "warning"
