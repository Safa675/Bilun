"""Unit tests for EK-3B-1 bundling rules (L1.1)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_bundling_code_resolved_match_is_error(monkeypatch) -> None:
    from src.bilun.domain.materials import exclusions as excl
    from src.bilun.domain.materials import catalog_lookup
    from src.bilun.domain.rules import bundling_rules as mod

    bundled_entry = [
        {
            "item_name": "Bistüri ucu veya disposable bistüri",
            "description": "Cerrahi malzemeler",
        }
    ]
    # Phase 2.1: matcher consolidated into exclusions.match_bundled_material;
    # the data lives in exclusions, the resolver in catalog_lookup (imported
    # lazily inside match_bundled_material, so patch at source).
    monkeypatch.setattr(excl, "get_bundled_consumables", lambda: bundled_entry)
    monkeypatch.setattr(
        catalog_lookup,
        "resolve_material_name_by_code",
        lambda code: "Bistüri ucu veya disposable bistüri" if code == "OP1000" else None,
    )
    # bundling_rules still imports resolve_material_name_by_code for the
    # display-name fallback in the code_resolved branch.
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


def test_bundling_fuzzy_name_only_is_unavailable(monkeypatch) -> None:
    from src.bilun.domain.materials import exclusions as excl
    from src.bilun.domain.rules import bundling_rules as mod

    bundled = [{"item_name": "Eldiven", "description": "Cerrahi malzemeler"}]
    # Phase 2.1: matcher lives in exclusions — patch there so the canonical
    # matcher sees the same fixture as the guard in check_bundling_violations.
    monkeypatch.setattr(mod, "get_bundled_consumables", lambda: bundled)
    monkeypatch.setattr(excl, "get_bundled_consumables", lambda: bundled)
    monkeypatch.setattr(mod, "resolve_material_name_by_code", lambda code: None)

    violations = mod.check_bundling_violations(
        [{"name": "Eldvn", "unit_price": 5.0, "quantity": 1}],
    )
    assert violations == []
    assessment = excl.assess_bundled_material("Eldvn")
    assert assessment.status == "unavailable"
    assert assessment.reason == "annex_material_identity_fuzzy"
