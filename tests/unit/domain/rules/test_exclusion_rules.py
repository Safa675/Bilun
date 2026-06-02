"""Unit tests for EK-3B-2 exclusion rules (L1.2)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_exclusion_by_resolved_code(monkeypatch) -> None:
    from src.bilun.domain.rules import exclusion_rules as mod

    monkeypatch.setattr(
        mod,
        "get_non_reimbursable_materials",
        lambda: [{"material_name": "Viskosüplemantasyon ürünleri (SUT ve eki listelerde belirtilenler hariç)"}],
    )
    monkeypatch.setattr(
        mod,
        "resolve_material_name_by_code",
        lambda code: (
            "Viskosüplemantasyon ürünleri (SUT ve eki listelerde belirtilenler hariç)"
            if code == "VISCO1"
            else None
        ),
    )

    violations = mod.check_exclusion_violations(
        [{"name": "Line label", "code": "VISCO1", "unit_price": 100.0, "quantity": 1}],
    )
    assert len(violations) == 1
    assert violations[0]["match_kind"] == "code_resolved"
    assert violations[0]["risk_amount"] == 100.0


def test_ek3b2_catalog_has_thirteen_rows() -> None:
    import pandas as pd

    from src.bilun.domain.constants import EK3B2_NON_REIMBURSABLE_PATH

    assert EK3B2_NON_REIMBURSABLE_PATH.exists()
    df = pd.read_parquet(EK3B2_NON_REIMBURSABLE_PATH)
    assert len(df) == 13
