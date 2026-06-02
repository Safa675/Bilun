"""Temporal EK-2B/EK-2C catalog membership (P0.1)."""

from __future__ import annotations

from datetime import date

import pytest

pytestmark = pytest.mark.unit


def test_procedure_annex_membership_respects_as_of_date(monkeypatch) -> None:
    from src.bilun.domain.prose_rules import catalog_membership as cm

    cm.get_ek2b_codes_as_of.cache_clear()
    cm.get_ek2c_codes_as_of.cache_clear()
    cm._ek2c_entry_map_asof.cache_clear()

    monkeypatch.setattr(
        cm,
        "get_ek2b_codes_as_of",
        lambda key: frozenset({"111111", "222222"}),
    )
    monkeypatch.setattr(
        cm,
        "get_ek2c_codes_as_of",
        lambda key: frozenset({"111111"}) if key == "2020-01-01" else frozenset(),
    )

    old_membership = cm.procedure_annex_membership("111111", as_of_date=date(2020, 1, 1))
    new_membership = cm.procedure_annex_membership("222222", as_of_date=date(2024, 6, 1))

    assert old_membership == (True, True)
    assert new_membership == (True, False)


def test_resolve_payment_method_passes_as_of_to_membership(monkeypatch) -> None:
    from src.bilun.domain.prose_rules import payment_method as pm

    seen: list[date | None] = []

    def _membership(code: str, *, as_of_date=None):
        seen.append(as_of_date)
        return True, True

    def _has_star(code: str, *, as_of_date=None):
        return False

    monkeypatch.setattr(pm, "procedure_annex_membership", _membership)
    monkeypatch.setattr(pm, "procedure_has_star", _has_star)

    service = date(2023, 5, 15)
    pm.resolve_payment_method(
        "610070",
        care_setting="inpatient",
        facility_tier="2_basamak_kamu",
        as_of_date=service,
    )
    assert seen == [service]


def test_prose_drg_locked_codes_loaded_from_json() -> None:
    from src.bilun.domain.prose_rules.payment_method import _load_payment_method_rules
    from src.bilun.domain.prose_rules.catalog_membership import procedure_prose_drg_locked
    from src.bilun.domain.prose_rules.ek2c_prose_drg_locked import load_prose_drg_locked_code_set

    rules = _load_payment_method_rules()
    assert "prose_drg_locked_codes" in rules
    assert isinstance(rules["prose_drg_locked_codes"], list)
    assert len(load_prose_drg_locked_code_set()) > 0
    assert procedure_prose_drg_locked("604250") is True
