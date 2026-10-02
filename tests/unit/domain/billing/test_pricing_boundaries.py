"""Regression boundaries for dated tariffs, package audit, quantities and CBC days."""
from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from src.bilun.domain.billing.claim_audit_exposure import compute_audit_exposure_from_claims
from src.bilun.domain.billing.claim_lab import _optimize_lab_billing_from_claims
from src.bilun.domain.billing.claim_materials import precheck_materials_from_claims
from src.bilun.domain.billing.lab_bill_merge import compute_lab_and_capture_gap_from_claims
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.drg_unbundling import (
    detect_blood_component_violations,
    detect_session_point_violations,
)
from src.bilun.domain.prose_rules.session_pricing import (
    compute_session_adjusted_itemized_total,
    compute_session_point_factors,
)
from src.bilun.domain.prose_rules.session_uplift import detect_session_underbilling_opportunities
from tests.unit.domain.billing.test_blood_uplift_wiring import _claim, _proc
from tests.unit.domain.billing.test_claim_materials_precheck import _material_line

pytestmark = pytest.mark.unit
_DAY = date(2024, 6, 1)


def _context(lines=(), materials=(), claims=None):
    return PatientClaimContext(
        "P1", tuple(claims or [_claim()]), tuple(lines), tuple(materials), (), ()
    )


def _historical_lines():
    return [
        _proc(procedure_line_id="primary", procedure_code="P610070", procedure_date=_DAY,
              procedure_specialty_code="general_surgery", unit_price_try=Decimal("9663.36"),
              expected_payable_try=Decimal("9663.36"), billed_amount_try=Decimal("9663.36")),
        _proc(procedure_line_id="secondary", procedure_code="P609830", procedure_date=_DAY,
              procedure_specialty_code="general_surgery", unit_price_try=Decimal("8006.39"),
              expected_payable_try=Decimal("8006.39"), billed_amount_try=Decimal("2001.60")),
    ]


def test_historical_primary_is_preserved_at_audit_uplift_and_strategy_boundaries():
    lines = _historical_lines()
    assert detect_session_point_violations(lines, cross_specialty=False) == []
    assert detect_session_underbilling_opportunities(lines, cross_specialty=False) == []
    total, _ = compute_session_adjusted_itemized_total(lines, cross_specialty=False)
    assert total == 11664.96


def test_real_catalog_ranking_reverses_only_after_tariff_change():
    codes = ["P610070", "P609830"]
    old = compute_session_point_factors(codes, same_incision=True, as_of_date=_DAY)
    new = compute_session_point_factors(codes, same_incision=True, as_of_date=date(2026, 10, 1))
    assert [f.procedure_code for f in old.factors if f.is_primary] == ["610070"]
    assert [f.procedure_code for f in new.factors if f.is_primary] == ["609830"]


@pytest.mark.parametrize("candidate", [False, True])
def test_itemized_blood_does_not_create_package_fraction_audit_exposure(candidate):
    line = _proc(procedure_code="705430", billed_amount_try=Decimal("1134.71"),
                 expected_payable_try=Decimal("1134.71"), unit_price_try=Decimal("1134.71"))
    ctx = _context([line], claims=[_claim(package_candidate=candidate)])
    assert detect_blood_component_violations([line]) == []
    assert compute_audit_exposure_from_claims(ctx) == 0


def test_blood_package_audit_requires_matching_claim_and_episode():
    blood = _proc(billed_amount_try=Decimal("1000"))
    package = _proc(procedure_line_id="package", procedure_category="paket", procedure_code="P610070")
    assert len(detect_blood_component_violations([package, blood])) == 1
    for foreign in (replace(package, claim_id="OTHER"), replace(package, episode_id="OTHER")):
        assert detect_blood_component_violations([foreign, blood]) == []


@pytest.mark.parametrize("quantity", [1, 2, 5])
@pytest.mark.parametrize("foreign,unit_ceiling", [(False, 120), (True, 100)])
def test_material_quantity_kdv_at_precheck_boundary(monkeypatch, quantity, foreign, unit_ceiling):
    from src.bilun.domain.billing import claim_materials

    monkeypatch.setattr(claim_materials, "lookup_ek3_list_price_try", lambda code: 100)
    line = replace(_material_line(), quantity=quantity, foreign_facility=foreign,
                   billed_amount_try=Decimal(unit_ceiling * quantity))
    assert precheck_materials_from_claims(_context(materials=[line])).kdv_price_reviews == []
    over = replace(line, billed_amount_try=line.billed_amount_try + Decimal("0.02"))
    rows = precheck_materials_from_claims(_context(materials=[over])).kdv_price_reviews
    assert len(rows) == 1
    assert rows[0]["gazette_ceiling_try"] == unit_ceiling * quantity


def _cbc(day, line_id, *, claim_id="CLM-BLOOD", code="L107020", name="Hemogram"):
    return _proc(procedure_line_id=line_id, claim_id=claim_id, procedure_date=day,
                 procedure_code=code, procedure_name=name, procedure_category="laboratuvar",
                 billed_amount_try=Decimal("100"))


def test_daily_cbc_bundles_are_not_collapsed_in_direct_or_per_bill_boundary(monkeypatch):
    from src.bilun.domain.billing import claim_lab

    monkeypatch.setattr(claim_lab, "_hemogram_gazette_price", lambda day: 100)
    ctx = _context([_cbc(_DAY, "one"), _cbc(_DAY + timedelta(days=1), "two")])
    assert _optimize_lab_billing_from_claims(ctx).hemogram_bundling_savings == 0
    assert compute_lab_and_capture_gap_from_claims(ctx, None)[0].hemogram_bundling_savings == 0


def test_same_day_cbc_components_remain_bundled_with_day_specific_tariff(monkeypatch):
    from src.bilun.domain.billing import claim_lab

    days = []
    def price(day):
        days.append(day)
        return 100 if day == str(_DAY) else 150
    monkeypatch.setattr(claim_lab, "_hemogram_gazette_price", price)
    lines = [
        _cbc(day, f"{day}-{name}", code=code, name=name)
        for day in (_DAY, _DAY + timedelta(days=1))
        for code, name in (("L101010", "Hemoglobin"), ("L101020", "Hematokrit"))
    ]
    result = _optimize_lab_billing_from_claims(_context(lines))
    assert result.hemogram_bundling_savings == 150
    assert len(result.flagged_tests) == 2
    assert days == [str(_DAY), str(_DAY + timedelta(days=1))]
    # Same date/episode in another bill is never part of the bundle.
    ctx = _context([lines[0], replace(lines[1], claim_id="OTHER")])
    assert _optimize_lab_billing_from_claims(ctx).hemogram_bundling_savings == 0


def test_pre_history_points_do_not_borrow_current_tariffs():
    from src.bilun.domain.prose_rules.session_pricing import _procedure_point_score

    assert _procedure_point_score("P610070", as_of_date=date(1900, 1, 1)) == 1.0
    assert _procedure_point_score("P609830", as_of_date=date(1900, 1, 1)) == 1.0
    assert _procedure_point_score("P609830", as_of_date=date(2026, 10, 1)) > 27000
    result = compute_session_point_factors(
        ["P610070", "P609830"], same_incision=True, as_of_date=date(1900, 1, 1)
    )
    assert result.metadata["historical_catalog_unavailable"] is True
    assert all(f.point_factor == 1.0 for f in result.factors)
    lines = [replace(line, procedure_date=date(1900, 1, 1)) for line in _historical_lines()]
    assert detect_session_point_violations(lines, cross_specialty=False) == []
    assert detect_session_underbilling_opportunities(lines, cross_specialty=False) == []


def test_membership_and_ek2b_ranking_receive_same_service_date(monkeypatch):
    from src.bilun.domain import catalog
    from src.bilun.domain.prose_rules import session_pricing

    seen = []
    def membership(code, *, as_of_date=None):
        seen.append(("membership", as_of_date))
        return (True, code == "100001" and as_of_date == _DAY)
    def entry(code, *, as_of_date=None):
        seen.append(("ek2c", as_of_date))
        return {"puan": 100} if code == "100001" and as_of_date == _DAY else None
    def lookup(code, visit_date=None):
        seen.append(("ek2b", visit_date))
        return {"entry": {"puan": 10 if code == "100002" else 100}}
    monkeypatch.setattr(session_pricing, "procedure_annex_membership", membership)
    monkeypatch.setattr(session_pricing, "get_ek2c_entry", entry)
    monkeypatch.setattr(catalog, "lookup_procedure_code", lookup)
    old = compute_session_point_factors(["100001", "100002"], same_incision=True, as_of_date=_DAY)
    assert old.rule_id == "2.2.2.B.c"
    assert {value for _, value in seen} == {_DAY}
    seen.clear()
    new_day = _DAY + timedelta(days=1)
    new = compute_session_point_factors(["100001", "100002"], same_incision=True, as_of_date=new_day)
    assert new.rule_id == "2.2.2.A.(5)"
    assert {value for _, value in seen} == {new_day}


@pytest.mark.parametrize("mismatch", ["patient", "claim", "episode", "unbilled", "candidate_code"])
def test_all_blood_fraction_consumers_require_actual_matching_package(mismatch):
    from src.bilun.domain.prose_rules.blood_uplift import (
        detect_blood_component_underbilling_opportunities,
    )

    blood = _proc(procedure_code="705441", billed_amount_try=Decimal("50"))
    package = _proc(procedure_line_id="package", procedure_code="P610070",
                    procedure_category="paket", procedure_date=date(2026, 1, 11))
    changes = {
        "patient": {"patient_id": "FOREIGN"}, "claim": {"claim_id": "FOREIGN"},
        "episode": {"episode_id": "FOREIGN"}, "unbilled": {"billed_amount_try": Decimal(0)},
        "candidate_code": {"procedure_category": "islem", "package_code": "P610070",
                           "billed_amount_try": Decimal(0), "expected_payable_try": Decimal(0)},
    }
    lines = [blood, replace(package, **changes[mismatch])]
    assert detect_blood_component_violations(lines) == []
    assert detect_blood_component_underbilling_opportunities(lines) == []
    total, _ = compute_session_adjusted_itemized_total(lines, cross_specialty=False)
    assert total == 1000


def test_itemized_session_and_hypothetical_strategy_do_not_use_package_blood_cap():
    blood = _proc(procedure_code="705441", billed_amount_try=Decimal("100"),
                  procedure_specialty_code="surgery")
    primary = _proc(procedure_line_id="primary", procedure_code="P610070",
                    procedure_specialty_code="surgery", billed_amount_try=Decimal("1000"))
    lines = [primary, blood]
    rows = detect_session_underbilling_opportunities(lines, cross_specialty=False)
    assert rows[0]["expected_billed_try"] == 300  # §4.6 package cap would be 200.
    total, _ = compute_session_adjusted_itemized_total(lines, same_incision=False, cross_specialty=False)
    assert total == 1500


def test_material_quantity_preserves_unit_rounding_and_one_cent_tolerance(monkeypatch):
    from src.bilun.domain.billing import claim_materials
    from src.bilun.domain.pricing.material_kdv import ek3_payable_ceiling_try

    monkeypatch.setattr(claim_materials, "lookup_ek3_list_price_try", lambda code: 100.01)
    unit_ceiling = Decimal(str(ek3_payable_ceiling_try(100.01)))
    line = replace(_material_line(), quantity=3,
                   billed_amount_try=unit_ceiling * 3 + Decimal("0.01"))
    assert precheck_materials_from_claims(_context(materials=[line])).kdv_price_reviews == []
    over = replace(line, billed_amount_try=line.billed_amount_try + Decimal("0.01"))
    row = precheck_materials_from_claims(_context(materials=[over])).kdv_price_reviews[0]
    assert row["gazette_ceiling_try"] == float(unit_ceiling * 3)


def test_cbc_before_catalog_history_does_not_invent_a_zero_price():
    ctx = _context([_cbc(date(1900, 1, 1), "one"), _cbc(date(1900, 1, 1), "two")])
    assert _optimize_lab_billing_from_claims(ctx).flagged_tests == []


@pytest.mark.parametrize("missing", [None, 0, "catalog_missing"])
def test_cbc_missing_tariff_does_not_crash_or_recover_whole_bill(monkeypatch, missing):
    from src.bilun.domain.billing import claim_lab

    def price(*args):
        if missing == "catalog_missing":
            raise FileNotFoundError("No dated catalog")
        return missing
    monkeypatch.setattr(claim_lab, "get_ek2b_price_for_date", price)
    ctx = _context([_cbc(_DAY, "one"), _cbc(_DAY, "two")])
    result = _optimize_lab_billing_from_claims(ctx)
    assert result.hemogram_bundling_savings == 0
    assert result.flagged_tests == []
