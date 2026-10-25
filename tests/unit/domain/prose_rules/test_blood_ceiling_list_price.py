"""The blood-component ceiling is the price list's, never the bill's (Safa675/Bilun#336).

SUT 2.2.2.B-1.(1).e (C000694) and 4.6.(4) (C007927): inside a diagnosis-based package a blood component is billed
apart at a share of its puan, 36 % for 705371/705430/705440, 24 % for 705372/705373, 20 % for 705441 and 28 % for
705442/705443. The ceiling is that share of the component's EK-2/B list price on the line's date, times its quantity.
Before #336 it was the share of the line's own payable (or billed) amount, which a bill sets equal to the billed
amount: a correct bill at its share then showed an audit exposure of the rest (1028.19 a 705371 unit), and the
uplift for an under-billed unit could never fire.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.billing.claim_audit_exposure import compute_audit_exposure_from_claims
from src.bilun.domain.claims.models import ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.blood_uplift import (
    detect_blood_component_underbilling_opportunities,
)
from src.bilun.domain.prose_rules.drg_unbundling import detect_blood_component_violations
from src.bilun.domain.prose_rules.session_pricing import (
    blood_component_max_billable_try,
    compute_session_adjusted_itemized_total,
)
from tests.unit.domain.billing.test_blood_uplift_wiring import _claim

pytestmark = pytest.mark.unit

_DAY = date(2026, 9, 17)  # the list of 2026-07-07 is in force
# EK-2/B list prices of the eight components on _DAY and their shares (C000694), written out as an oracle.
_LIST_AND_SHARE = {
    "705371": (Decimal("4462.64"), Decimal("0.36")),
    "705430": (Decimal("1134.70"), Decimal("0.36")),
    "705440": (Decimal("1134.70"), Decimal("0.36")),
    "705372": (Decimal("1947.88"), Decimal("0.24")),
    "705373": (Decimal("1650.27"), Decimal("0.24")),
    "705441": (Decimal("2564.25"), Decimal("0.20")),
    "705442": (Decimal("6216.49"), Decimal("0.28")),
    "705443": (Decimal("8744.78"), Decimal("0.28")),
}


def _cents(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding="ROUND_HALF_UP")


def _line(code: str = "705371", *, billed: str, payable: str | None = None, unit: str | None = None,
          quantity: int = 1, day: date = _DAY, line_id: str = "blood") -> ProcedureClaimLine:
    """A blood unit whose payable and unit price equal what it bills unless told otherwise (a real export)."""
    return ProcedureClaimLine(
        procedure_line_id=line_id, claim_id="CLM-BLOOD", patient_id="P1", episode_id="E1",
        procedure_date=day, procedure_code=code, procedure_name="Kan bileşeni", procedure_category="islem",
        quantity=quantity, unit_price_try=Decimal(unit if unit is not None else billed),
        billed_amount_try=Decimal(billed), expected_payable_try=Decimal(payable if payable is not None else billed),
        is_package_included=False, package_code="", surcharge_applicable=False, copay_rate_applicable=True,
        denial_reason_expected="", rule_trace_expected="",
    )


def _package(day: date = _DAY) -> ProcedureClaimLine:
    # the removal package of S42 (P612500), billed on the same claim and episode
    return replace(_line(billed="20000"), procedure_line_id="package", procedure_code="P612500",
                   procedure_name="Parsiyel protez çıkarılması", procedure_category="paket", procedure_date=day)


def _ctx(*lines: ProcedureClaimLine) -> PatientClaimContext:
    claim = _claim(admission_date=_DAY, discharge_date=_DAY, claim_start_date=_DAY, claim_end_date=_DAY)
    return PatientClaimContext("P1", (claim,), tuple(lines), (), (), ())


@pytest.mark.parametrize("code", sorted(_LIST_AND_SHARE))
def test_a_component_billed_at_its_share_inside_a_package_is_clean_when_payable_equals_billed(code: str) -> None:
    listed, share = _LIST_AND_SHARE[code]
    line = _line(code, billed=str(_cents(listed * share)))
    assert detect_blood_component_violations([_package(), line]) == []
    assert detect_blood_component_underbilling_opportunities([_package(), line]) == []
    assert compute_audit_exposure_from_claims(_ctx(_package(), line)) == 0


@pytest.mark.parametrize("code", sorted(_LIST_AND_SHARE))
def test_a_component_billed_in_full_inside_a_package_is_at_risk_for_all_but_its_share(code: str) -> None:
    listed, share = _LIST_AND_SHARE[code]
    (row,) = detect_blood_component_violations([_package(), _line(code, billed=str(listed))])
    assert row["allowed_fraction"] == pytest.approx(float(share))
    assert row["max_billable_try"] == float(_cents(listed * share))
    assert row["actual_billed_try"] == float(listed)
    assert row["risk_amount_try"] == float(_cents(listed - listed * share))
    assert row["rule_id"] == "blood_component_partial_bill" and row["sut_section"] == "2.2.2.B-1.e"


def test_s42s_red_cells_billed_in_full_are_at_risk_for_2856_10_a_unit_and_at_their_share_for_nothing() -> None:
    """The bills of S42 (patient 5, C000694): two 705371 units beside the removal package P612500."""
    faulty = [_line(billed="4462.64", line_id="u1"), _line(billed="4462.64", line_id="u2")]
    clean = [_line(billed="1606.55", line_id="u1"), _line(billed="1606.55", line_id="u2")]
    rows = detect_blood_component_violations([_package(), *faulty])
    assert [(r["max_billable_try"], r["risk_amount_try"]) for r in rows] == [(1606.55, 2856.09)] * 2
    assert compute_audit_exposure_from_claims(_ctx(_package(), *faulty)) == pytest.approx(5712.18)
    assert detect_blood_component_violations([_package(), *clean]) == []
    assert compute_audit_exposure_from_claims(_ctx(_package(), *clean)) == 0


@pytest.mark.parametrize("stated", ["99999.00", "1.00", "0"])
def test_the_ceiling_reads_neither_the_lines_payable_nor_its_unit_price(stated: str) -> None:
    line = _line(billed="4462.64", payable=stated, unit=stated)
    (row,) = detect_blood_component_violations([_package(), line])
    assert (row["max_billable_try"], row["risk_amount_try"]) == (1606.55, 2856.09)
    under = _line(billed="1000.00", payable=stated, unit=stated)
    (hit,) = detect_blood_component_underbilling_opportunities([_package(), under])
    assert (hit["max_billable_try"], hit["recoverable_uplift_try"]) == (1606.55, 606.55)
    assert blood_component_max_billable_try(line, package_context=True) == pytest.approx(4462.64 * 0.36)


def test_an_under_billed_unit_with_payable_equal_to_billed_is_an_sgk_uplift() -> None:
    """The issue's case: payable == billed, billed below the share; the uplift used to be dark for any such bill."""
    (hit,) = detect_blood_component_underbilling_opportunities([_package(), _line(billed="1000.00")],
                                                              claim_id="CLM-BLOOD")
    assert hit["type"] == "blood_component_underbilling" and hit["savings_category"] == "sgk_uplift"
    assert (hit["max_billable_try"], hit["actual_billed_try"], hit["recoverable_uplift_try"]) == (
        1606.55, 1000.0, 606.55)
    assert detect_blood_component_violations([_package(), _line(billed="1000.00")]) == []


def test_the_ceiling_is_the_share_of_the_whole_lines_quantity() -> None:
    two = _line(billed="3213.10", quantity=2)  # 2 x 1606.55
    assert detect_blood_component_violations([_package(), two]) == []
    (row,) = detect_blood_component_violations([_package(), replace(two, billed_amount_try=Decimal("8925.28"),
                                                                      expected_payable_try=Decimal("8925.28"))])
    assert (row["max_billable_try"], row["risk_amount_try"]) == (3213.10, 5712.18)  # 2 x 4462.64 x 0.36 = 3213.1008
    (hit,) = detect_blood_component_underbilling_opportunities([_package(), replace(two, billed_amount_try=Decimal(
        "1606.55"), expected_payable_try=Decimal("1606.55"))])
    assert hit["recoverable_uplift_try"] == 1606.55  # 3213.10 - 1606.55


def test_the_list_price_is_the_one_in_force_on_the_lines_date() -> None:
    old = date(2024, 6, 1)  # 705371 lists 2279.77 that day (the list of 2024-05-11)
    line = _line(billed="2279.77", payable="4462.64", day=old)
    (row,) = detect_blood_component_violations([_package(old), line])
    assert (row["max_billable_try"], row["risk_amount_try"]) == (820.72, 1459.05)  # 2279.77 x 0.36 = 820.7172


def test_a_component_whose_list_price_is_unknown_is_not_assessed(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.bilun.domain import catalog

    monkeypatch.setattr(catalog, "lookup_procedure_code",
                        lambda *a, **k: {"match_type": "none", "entry": None, "candidates": []})
    # a payable above the share must not stand in for the missing list price
    full, under = _line(billed="4462.64"), _line(billed="10.00", payable="4462.64")
    assert blood_component_max_billable_try(full, package_context=True) is None
    assert detect_blood_component_violations([_package(), full]) == []
    assert detect_blood_component_underbilling_opportunities([_package(), under]) == []


def test_outside_a_package_a_component_billed_in_full_raises_nothing() -> None:
    """S24's shape (patient 15): red cells on an itemized bill are billed at their full list price."""
    lines = [_line(billed="4462.64", line_id="u1"), _line(billed="4462.64", line_id="u2")]
    assert detect_blood_component_violations(lines) == []
    assert detect_blood_component_underbilling_opportunities(lines) == []
    assert blood_component_max_billable_try(lines[0], package_context=False) is None
    assert compute_audit_exposure_from_claims(_ctx(*lines)) == 0


def test_the_itemized_total_beside_a_package_caps_a_component_at_its_share_of_the_list_price() -> None:
    """A unit billed at its share counts its share (it was cut to 36 % of its share, 578.36); one billed in full
    counts its share too."""
    at_share = _line(billed="1606.55")
    total, _ = compute_session_adjusted_itemized_total([_package(), at_share], cross_specialty=False)
    assert total == 1606.55
    total, _ = compute_session_adjusted_itemized_total([_package(), _line(billed="4462.64")], cross_specialty=False)
    assert total == 1606.55
    total, _ = compute_session_adjusted_itemized_total([_line(billed="4462.64")], cross_specialty=False)
    assert total == 4462.64  # no package on the claim: the component keeps its full price
