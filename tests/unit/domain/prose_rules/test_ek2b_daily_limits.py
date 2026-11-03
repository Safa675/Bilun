"""EK-2/B Açıklama daily caps (#303): a code billed on one day above "Günde bir adet faturalandırılır." and the like.

The Açıklama texts below are copied from the EK-2/B list of 2026-07-07 (the code after each). Prices come from the
catalog-price oracle. The showcase case is the S2 COPD stay: its committed bill keeps the caps (one nebulizer a day,
16 h of oxygen a day) and its v3 draft did not (18 nebulizers in 6 days, 48 h of oxygen in 2 days; review item 6 of
`reports/synthetic-data/2026-10-16-v3-drafts-review.md`).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from scripts.synthetic.cohort import load_showcase_dataset
from src.bilun.domain.billing import claim_audit_exposure
from src.bilun.domain.billing.claim_audit_exposure import recommend_audit_exposure_from_claims
from src.bilun.domain.billing.patient_report import compute_patient_billing_report
from src.bilun.domain.claims.patient_context import PatientClaimContext, build_bill_claim_context
from src.bilun.domain.prose_rules.drg_unbundling import ClaimUnbundlingFinding
from src.bilun.domain.prose_rules.ek2b_daily_limits import daily_limit, detect_ek2b_daily_limit_violations
from tests.fixtures import synthetic_cohort as cohort
from tests.unit._helpers.catalog_prices import list_price, list_text
from tests.unit.domain.billing.test_blood_uplift_wiring import _claim, _proc

pytestmark = pytest.mark.unit

_DAY = date(2026, 3, 9)
_TYPE = "ek2b_daily_limit_exceeded"


def _line(code: str, units: int, line_id: str, *, day: date = _DAY, claim_id: str = "C1", billed: str = "") -> object:
    amount = Decimal(billed or list_text(code, day, units))
    return _proc(
        procedure_line_id=line_id, claim_id=claim_id, procedure_code=code, procedure_name=code, procedure_date=day,
        quantity=units, unit_price_try=amount / units, billed_amount_try=amount, expected_payable_try=amount,
    )


@pytest.mark.parametrize(
    ("aciklama", "cap"),
    [
        ("Günde bir adet faturalandırılır.", (1, "adet")),  # 530350
        ("Günde en fazla üç adet faturalandırılır.", (3, "adet")),  # 530260
        ("Günde altı adetten fazla faturalandırılmaz.", (6, "adet")),  # 530120
        ("Günde üç adetten fazla ve 530080, 530160 ile birlikte faturalandırılmaz.", (3, "adet")),  # 530150
        ("Günde bir defa faturalandırılır.", (1, "adet")),  # 704780
        ("%30’dan büyük vücut yüzey alanında\nGünde en fazla iki adet faturalandırılır.", (2, "adet")),  # 530532
        (
            "Günlük en fazla 16 saat ödenir. Bir saatin altında uygulanması halinde bir adet faturalandırılır. "
            "Epikrizde süre belirtilmelidir.",
            (16, "saat"),
        ),  # 530360
        ("Yatan hasta için günde bir adet faturalandırılır.", None),  # 801542: a condition
        ("Günde en fazla üç farklı anatomik bölge faturalandırılır.", None),  # 700140: another unit
        ("Dört günde bir adet faturalandırılır.", None),  # 530590: an interval
        ("Ayda bir adet faturalandırılır.", None),  # G100091
        ("Günde bir adet faturalandırılır. X tanısında on günde en fazla üç adet faturalandırılır.", None),
    ],
)
def test_only_a_whole_daily_cap_sentence_is_read(aciklama: str, cap: tuple[int, str] | None) -> None:
    limit = daily_limit(aciklama)
    assert (limit and (limit.units, limit.unit)) == cap


def test_the_units_above_the_cap_cost_the_list_price_of_their_day() -> None:
    day2 = _DAY + timedelta(days=1)
    lines = [
        _line("530350", 1, "A"), _line("530350", 1, "B"), _line("530350", 1, "C"),  # 3 lines on one day
        _line("530350", 3, "D", day=day2),  # one line of 3
        _line("530350", 1, "E", day=day2 + timedelta(days=1)),  # at the cap
    ]
    [v] = detect_ek2b_daily_limit_violations(lines)

    price = list_price("530350", _DAY)
    assert (v["type"], v["procedure_line_id"], v["excess_units"]) == (_TYPE, "B", 4)
    assert v["days_over"] == {_DAY.isoformat(): 3, day2.isoformat(): 3}
    assert v["line_risks"] == {"B": price, "C": price, "D": pytest.approx(2 * price)}
    assert v["risk_amount_try"] == pytest.approx(4 * price)
    assert (v["savings_category"], v["savings_basis"], v["sut_section_id"]) == ("audit_exposure", "sourced", "EK-2/B")
    assert "Günde bir adet faturalandırılır." in v["detail"]


def test_a_line_is_at_risk_for_at_most_what_it_billed() -> None:
    [v] = detect_ek2b_daily_limit_violations([_line("530360", 24, "O2", billed="10.00")])
    assert (v["excess_units"], v["risk_amount_try"]) == (8, 10.0)


@pytest.mark.parametrize(
    "lines",
    [
        [_line("530350", 1, "A"), _line("530350", 1, "B", claim_id="C2")],  # two bills of one day
        [_line("530350", 1, "A"), _line("530350", 1, "B", billed="-1.00")],  # a reversal asks no money
        [_line("P530350", 2, "A", billed="100.00")],  # a package code is not its EK-2/B twin
        [_line("510070", 2, "A", billed="100.00")],  # Kuvöz: a bed line's quantity is its day count
        [_line("801720", 2, "A")],  # no cap in its Açıklama
    ],
    ids=["two-claims", "reversal", "package-code", "bed", "no-cap"],
)
def test_lines_the_cap_does_not_read(lines: list) -> None:
    assert detect_ek2b_daily_limit_violations(lines) == []


@pytest.mark.parametrize(("units_counted", "units_at_risk"), [(0, 2), (1.5, 1.5), (3, 0)])
def test_money_an_earlier_row_counts_on_the_line_is_not_counted_twice(monkeypatch, units_counted, units_at_risk):
    price = list_price("530350", _DAY)
    line = _line("530350", 3, "N")  # 3 billed at the list price, 2 above the cap
    counted = {"procedure_line_id": "N", "risk_amount_try": units_counted * price}
    finding = ClaimUnbundlingFinding(claim_id="C1", chapter="Z", bundled_violations=[counted])
    monkeypatch.setattr(claim_audit_exposure, "unbundling_findings_from_claims", lambda ctx: [finding])
    ctx = PatientClaimContext(
        "P1", claims=(_claim(claim_id="C1"),), procedure_lines=(line,), material_lines=(), drug_lines=(), diagnoses=()
    )

    review = recommend_audit_exposure_from_claims(ctx)

    rows = [row["risk_amount_try"] for row in review.rows if row["kind"] == _TYPE]
    assert rows == ([pytest.approx(units_at_risk * price)] if units_at_risk else [])
    assert review.total_try == pytest.approx((units_counted + units_at_risk) * price)


def test_s2_keeps_the_caps_and_its_v3_draft_breaks_them_by_the_list_price_of_the_excess() -> None:
    s2 = cohort.role("showcase_S2")
    bill = build_bill_claim_context(s2.patient_id, s2.claim_id, load_showcase_dataset())
    draft_units = {"530350": 3, "530360": 24}  # 18 nebulizers in 6 days, 48 h of oxygen in 2 days
    draft = replace(
        bill,
        procedure_lines=tuple(
            replace(line, quantity=units, billed_amount_try=line.unit_price_try * units)
            if (units := draft_units.get(line.procedure_code))
            else line
            for line in bill.procedure_lines
        ),
    )
    not_exempt = {"exempt": False, "n_qualifying": 0, "qualifying_diagnoses": []}
    clean, faulty = (
        compute_patient_billing_report(s2.patient_id, claim_context=ctx, copay_exemption=not_exempt)
        for ctx in (bill, draft)
    )

    expected = {"530350": 12 * list_price("530350", _DAY), "530360": 16 * list_price("530360", _DAY)}
    assert [row for row in clean.audit_exposure_rows if row["kind"] == _TYPE] == []
    rows = {row["procedure_code"]: row["risk_amount_try"] for row in faulty.audit_exposure_rows if row["kind"] == _TYPE}
    assert rows == pytest.approx(expected)
    assert faulty.audit_exposure_try - clean.audit_exposure_try == pytest.approx(sum(expected.values()))
    actions = [a for a in faulty.recommended_actions if a["kind"] == _TYPE]
    assert [(a["surface"], a["finding_type"]) for a in actions] == [("audit_exposure", "compliance")] * 2
