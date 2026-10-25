"""Both bed motors on the same bills: no bed day where the SUT says the bed is already paid or may not be billed.

Follow-up of the day-bed change (tasks/todo.md, 2026-10-19). A one-date `yatis` claim that bills 530000 (EK-2/B: "Yatak,
yemek, hasta vizit hizmetlerini kapsar. 510120, 530003 ile birlikte faturalandırılmaz.") or hemodialysis 704210 / 704230
(SUT §2.4.4.D-1.(11): "gündüz yatak ücreti fiyata dâhil") showed a 44.45 TL day bed; a stay of several dates showed the
510010 / Kuvöz days an ER bed (530000) or a special room (510100, 510110) had paid already. The bills are built in memory
and run through `compute_patient_billing_report`; prices are those of the 2026-07-07 list (510010 222.35, 510070
440.98, 510120 44.45), read back from the engine's own rows in the invariants.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest

from src.bilun.domain.billing.patient_report import compute_patient_billing_report
from src.bilun.domain.billing.types import BillingActionReport
from src.bilun.domain.claims.models import ClaimDiagnosis
from src.bilun.domain.claims.patient_context import PatientClaimContext
from tests.unit.domain.billing.test_blood_uplift_wiring import _claim, _proc

pytestmark = pytest.mark.unit

_NOT_EXEMPT = {"exempt": False, "n_qualifying": 0, "qualifying_diagnoses": []}
_START = date(2026, 7, 10)
_ADULT = ("kardiyoloji", "I10")
_NEWBORN = ("yenidoğan", "Z38.0")
_ICU_UNIT = ("Yoğun Bakım", "I21.0")
_NICU = ("Yenidoğan Yoğun Bakım", "P22.0")


def _stay(claim_id: str, who: tuple[str, str], first: int, last: int, *, claim_type: str = "yatis"):
    start, end = _START + timedelta(days=first), _START + timedelta(days=last)
    claim = _claim(
        claim_id=claim_id, claim_type=claim_type, department=who[0], primary_icd10=who[1], admission_date=start,
        discharge_date=end, claim_start_date=start, claim_end_date=end,
    )
    exam = _proc(
        procedure_line_id=f"{claim_id}-EXAM", claim_id=claim_id, procedure_code="520010", procedure_name="Muayene",
        billed_amount_try=Decimal("10"), procedure_date=start,
    )
    diagnosis = ClaimDiagnosis(
        diagnosis_id=f"DX-{claim_id}", claim_id=claim_id, patient_id="P1", episode_id="E1", icd10_code=who[1],
        is_primary=True, diagnosis_role="primary", diagnosis_date=start, exemption_eligible=False,
    )
    return claim, [exam], diagnosis


def _line(claim_id: str, code: str, day: int, billed: str, *, quantity: int = 1, category: str = "islem"):
    return _proc(
        procedure_line_id=f"{claim_id}-{code}-{day}-{billed}", claim_id=claim_id, procedure_code=code,
        procedure_name=code, quantity=quantity, billed_amount_try=Decimal(billed), procedure_category=category,
        procedure_date=_START + timedelta(days=day),
    )


def _context(*stays, lines=()) -> PatientClaimContext:
    claims = tuple(s[0] for s in stays)
    procedure_lines = tuple(line for s in stays for line in s[1]) + tuple(lines)
    return PatientClaimContext(
        patient_id="P1", claims=claims, procedure_lines=procedure_lines, material_lines=(), drug_lines=(),
        diagnoses=tuple(s[2] for s in stays),
    )


def _report(ctx: PatientClaimContext, claim_id: str | None = None) -> BillingActionReport:
    if claim_id is not None:
        ctx = ctx.slice_for_claim(claim_id)
    return compute_patient_billing_report("P1", claim_context=ctx, copay_exemption=_NOT_EXEMPT)


def _std(report: BillingActionReport, claim_id: str = "CLM") -> dict[str, Any] | None:
    return next((o for o in report.yatak_puani.opportunities if o["claim_id"] == claim_id), None)


def _newborn(report: BillingActionReport, claim_id: str = "CLM") -> dict[str, Any] | None:
    return next((o for o in report.yenidogan_yatak.opportunities if o["claim_id"] == claim_id), None)


def _bed_rows(report: BillingActionReport) -> list[dict[str, Any]]:
    return [a for a in report.recommended_actions if a["surface"] in ("yatak_puani", "yenidogan_yatak")]


def _assert_invariants(report: BillingActionReport) -> None:
    """Headline = the money rows; no row above its own expected charge; the bed motors never both own a day."""
    counted = [
        Decimal(str(a["sgk_uplift_try"]))
        for a in report.recommended_actions
        if a["sgk_uplift_try"] is not None and a["surface"] != "care_setting_review"
    ]
    assert sum(counted, Decimal("0")).quantize(Decimal("0.01")) == Decimal(str(report.sgk_uplift_try)).quantize(
        Decimal("0.01")
    )
    for o in report.yatak_puani.opportunities:
        assert 0.0 <= o["recoverable_uplift_try"] <= o["expected_yatak_try"] + 1e-9
        assert 0 <= o["bed_days"] <= o["gross_bed_days"]
    for o in report.yenidogan_yatak.opportunities:
        assert 0.0 <= o["recoverable_uplift_try"] <= o["expected_try"] + 1e-9
        assert o["days"] >= 0
    for newborn in report.yenidogan_yatak.opportunities:
        std = _std(report, newborn["claim_id"])
        if std is not None:
            assert std["bed_days"] + newborn["days"] <= std["gross_bed_days"]


# Each case: (who, first day, last day, lines [(code, day, billed, quantity)], claim_type,
#             standard-bed days left, newborn days (None: no newborn row), recoverable TL on the two rows together)
_CASES = {
    # --- one date: the day bed the SUT forbids -------------------------------------------------------------
    "control adult one date": (_ADULT, 0, 0, [], "yatis", 1, None, 44.45),
    "control newborn one date": (_NEWBORN, 0, 0, [], "yatis", 0, 1, 44.45),
    "adult ER bed": (_ADULT, 0, 0, [("530000", 0, "577.45", 1)], "yatis", 0, None, 0.0),
    "newborn ER bed": (_NEWBORN, 0, 0, [("530000", 0, "577.45", 1)], "yatis", 0, 0, 0.0),
    "adult hemodialysis 704230": (_ADULT, 0, 0, [("704230", 0, "4342.48", 1)], "yatis", 0, None, 0.0),
    "adult emergency hemodialysis 704210": (_ADULT, 0, 0, [("704210", 0, "4342.48", 1)], "yatis", 0, None, 0.0),
    "newborn hemodialysis": (_NEWBORN, 0, 0, [("704230", 0, "4342.48", 1)], "yatis", 0, 0, 0.0),
    "adult day case with a hyperbaric-oxygen session": (_ADULT, 0, 0, [("702580", 0, "545.76", 1)], "day_case", 0, None, 0.0),
    "adult ER bed and the day bed billed (the pair is forbidden)": (
        _ADULT, 0, 0, [("530000", 0, "577.45", 1), ("510120", 0, "44.45", 1)], "yatis", 0, None, 0.0),
    "adult 530003 only": (_ADULT, 0, 0, [("530003", 0, "100.00", 1)], "yatis", 1, None, 44.45),
    "adult reversed ER bed": (_ADULT, 0, 0, [("530000", 0, "-577.45", 1)], "yatis", 1, None, 44.45),
    "adult home hemodialysis": (_ADULT, 0, 0, [("704233", 0, "4342.48", 1)], "yatis", 1, None, 44.45),
    "adult inpatient claim with the same hyperbaric session": (
        _ADULT, 0, 0, [("702580", 0, "545.76", 1)], "yatis", 1, None, 44.45),
    # --- a day case crosses midnight: no ward bed, and its day bed is forbidden for EK-2/C procedures -----------
    "adult day case over two dates with a hyperbaric-oxygen session": (
        _ADULT, 0, 1, [("702580", 0, "545.76", 1)], "day_case", 0, None, 0.0),
    "adult day case over two dates, no EK-2/C procedure (untouched)": (_ADULT, 0, 1, [], "day_case", 2, None, 444.70),
    "adult inpatient claim over two dates with the same session (untouched)": (
        _ADULT, 0, 1, [("702580", 0, "545.76", 1)], "yatis", 2, None, 444.70),
    "newborn day case over two dates with a hyperbaric-oxygen session": (
        _NEWBORN, 0, 1, [("702580", 0, "545.76", 1)], "day_case", 0, 0, 0.0),
    # --- three days: the days the bed-including code pays -----------------------------------------------------
    "control adult 3 days": (_ADULT, 0, 2, [], "yatis", 3, None, 667.05),
    "control newborn 3 days": (_NEWBORN, 0, 2, [], "yatis", 0, 3, 1322.94),
    "adult ER bed on day 1": (_ADULT, 0, 2, [("530000", 0, "577.45", 1)], "yatis", 2, None, 444.70),
    "adult ER bed on day 2": (_ADULT, 0, 2, [("530000", 1, "577.45", 1)], "yatis", 2, None, 444.70),
    "adult ER bed for two days": (_ADULT, 0, 2, [("530000", 0, "1154.90", 2)], "yatis", 1, None, 222.35),
    "adult ER bed and standard bed billed on the other days": (
        _ADULT, 0, 2, [("530000", 0, "577.45", 1), ("510010", 1, "444.70", 2)], "yatis", 2, None, 0.0),
    "adult sterile room all three days": (_ADULT, 0, 2, [("510100", 0, "2981.00", 3)], "yatis", 0, None, 0.0),
    "adult isolation room all three days": (_ADULT, 0, 2, [("510110", 0, "1333.00", 3)], "yatis", 0, None, 0.0),
    "adult hemodialysis on a stay of three dates": (_ADULT, 0, 2, [("704230", 1, "4342.48", 1)], "yatis", 3, None, 667.05),
    "newborn ER bed on day 1": (_NEWBORN, 0, 2, [("530000", 0, "577.45", 1)], "yatis", 0, 2, 881.96),
    "newborn ER bed and the incubator billed on the other days": (
        _NEWBORN, 0, 2, [("530000", 0, "577.45", 1), ("510070", 1, "881.96", 2)], "yatis", 0, 2, 0.0),
    "newborn ER bed and the standard bed billed on the other days": (
        _NEWBORN, 0, 2, [("530000", 0, "577.45", 1), ("510010", 1, "444.70", 2)], "yatis", 2, None, 0.0),
}


@pytest.mark.parametrize("name", list(_CASES))
def test_each_bill_gives_the_days_and_the_money_the_sut_leaves(name: str) -> None:
    who, first, last, lines, claim_type, std_days, newborn_days, recoverable = _CASES[name]
    stay = _stay("CLM", who, first, last, claim_type=claim_type)
    ctx = _context(stay, lines=[_line("CLM", c, d, b, quantity=q) for c, d, b, q in lines])
    report = _report(ctx)

    std, newborn = _std(report), _newborn(report)
    assert std is not None
    assert std["bed_days"] == std_days, std["detail"]
    if newborn_days is None:
        assert newborn is None
    else:
        assert newborn is not None and newborn["days"] == newborn_days, newborn["detail"]
    rows = round(sum(a["sgk_uplift_try"] for a in _bed_rows(report)), 2)
    assert rows == pytest.approx(recoverable, abs=0.01)
    assert report.yatak_puani.confirmed_yatak_try + report.yenidogan_yatak.confirmed_yenidogan_yatak_try == pytest.approx(
        recoverable, abs=0.01
    )
    _assert_invariants(report)
    # The bill scope sees the same bed rows as the patient scope.
    bill = _report(ctx, "CLM")
    assert round(sum(a["sgk_uplift_try"] for a in _bed_rows(bill)), 2) == rows
    _assert_invariants(bill)


@pytest.mark.parametrize(
    "name",
    [
        "adult ER bed", "newborn ER bed", "adult hemodialysis 704230", "adult emergency hemodialysis 704210",
        "newborn hemodialysis", "adult day case with a hyperbaric-oxygen session",
    ],
)
def test_a_one_date_bill_with_a_forbidden_day_bed_has_no_bed_row_and_no_headline(name: str) -> None:
    who, first, last, lines, claim_type, *_ = _CASES[name]
    ctx = _context(
        _stay("CLM", who, first, last, claim_type=claim_type),
        lines=[_line("CLM", c, d, b, quantity=q) for c, d, b, q in lines],
    )
    report = _report(ctx)

    assert _bed_rows(report) == []
    assert report.sgk_uplift_try == 0.0
    [std] = report.yatak_puani.opportunities
    assert (std["bed_code"], std["gross_bed_days"], std["bed_days"], std["same_day_stay"]) == ("510120", 1, 0, True)
    assert "No day bed (510120) is expected" in std["detail"]


# --- the ICU transfer day and the package window --------------------------------------------------------------


def _ward_after_icu(*, ward: tuple[str, str], er_day: int | None):
    """ICU claim 10-11 July (510090 on both days, 11 July is the ICU last day) and the ward claim 11-13 July."""
    icu = _stay("ICU", _ICU_UNIT, 0, 1)
    ward_stay = _stay("CLM", ward, 1, 3)
    lines = [_line("ICU", "510090", 0, "0"), _line("ICU", "510090", 1, "0")]
    if er_day is not None:
        lines.append(_line("CLM", "530000", er_day, "577.45"))
    return _context(icu, ward_stay, lines=lines)


@pytest.mark.parametrize("scope", ["patient", "bill"])
def test_an_icu_transfer_day_the_er_bed_also_pays_is_taken_out_once(scope: str) -> None:
    ctx = _ward_after_icu(ward=_ADULT, er_day=1)  # 530000 on the ICU last day = the ward's first day
    report = _report(ctx, "CLM" if scope == "bill" else None)

    std = _std(report)
    assert std is not None
    assert std["bed_days"] == 2  # 12 and 13 July, not 1
    assert "icu_overlap_days" not in std
    assert std["recoverable_uplift_try"] == pytest.approx(2 * 222.35, abs=0.01)
    _assert_invariants(report)


@pytest.mark.parametrize("scope", ["patient", "bill"])
def test_an_er_day_and_a_different_icu_transfer_day_are_both_taken_out(scope: str) -> None:
    ctx = _ward_after_icu(ward=_ADULT, er_day=2)  # 530000 on 12 July; the ICU last day is 11 July
    report = _report(ctx, "CLM" if scope == "bill" else None)

    std = _std(report)
    assert std is not None
    assert (std["bed_days"], std["icu_overlap_days"]) == (1, 1)  # 13 July
    assert std["recoverable_uplift_try"] == pytest.approx(222.35, abs=0.01)
    _assert_invariants(report)


@pytest.mark.parametrize("scope", ["patient", "bill"])
def test_a_newborn_ward_stay_after_the_icu_counts_each_day_once_in_one_row(scope: str) -> None:
    ctx = _ward_after_icu(ward=_NEWBORN, er_day=1)
    report = _report(ctx, "CLM" if scope == "bill" else None)

    newborn, std = _newborn(report), _std(report)
    assert newborn is not None and std is not None
    assert newborn["days"] == 2  # 12 and 13 July; the ICU last day, 11 July, is also the ER day: taken out once
    assert newborn["icu_overlap_dates"] == ["2026-07-11"]
    assert newborn["expected_try"] == pytest.approx(2 * 440.98, abs=0.01)
    assert std["bed_days"] == 0 and std["newborn_overlap_days"] == 2
    _assert_invariants(report)


def test_the_er_bed_after_a_package_window_and_inside_it() -> None:
    package = _line("CLM", "P600040", 1, "5000", category="paket")  # group B: 10 days from 11 July
    inside = _context(_stay("CLM", _ADULT, 0, 11), lines=[package, _line("CLM", "530000", 4, "577.45")])
    after = _context(_stay("CLM", _ADULT, 0, 11), lines=[package, _line("CLM", "530000", 11, "577.45")])

    [std_in] = _report(inside).yatak_puani.opportunities
    [std_after] = _report(after).yatak_puani.opportunities
    assert (std_in["bundled_days"], std_in["bed_days"]) == (11, 1)  # 530000 inside the window pays a bundled day
    assert (std_after["bundled_days"], std_after["bed_days"]) == (11, 0)  # on the one day left it pays that day
    _assert_invariants(_report(inside))
    _assert_invariants(_report(after))


# --- other claims of the patient are untouched --------------------------------------------------------------------


def test_a_claim_with_these_lines_does_not_change_the_patients_other_claim() -> None:
    dialysis = _stay("A", _ADULT, 0, 0)
    plain = _stay("B", _ADULT, 0, 0)
    ctx = _context(dialysis, plain, lines=[_line("A", "704230", 0, "4342.48")])
    report = _report(ctx)

    assert _std(report, "A")["bed_days"] == 0
    assert _std(report, "B")["bed_days"] == 1
    assert [(a["claim_id"], a["sgk_uplift_try"]) for a in _bed_rows(report)] == [("B", pytest.approx(44.45, abs=0.005))]
    assert _bed_rows(_report(ctx, "A")) == []
    assert round(sum(a["sgk_uplift_try"] for a in _bed_rows(_report(ctx, "B"))), 2) == 44.45
    _assert_invariants(report)


def test_the_er_bed_of_another_claim_of_the_patient_takes_no_day() -> None:
    """The ER claim (outpatient) and the stay are two bills: "birlikte" and "kapsar" speak of one bill."""
    er_visit = _stay("ER", _ADULT, 0, 0, claim_type="poliklinik")
    ward = _stay("CLM", _ADULT, 0, 2)
    ctx = _context(er_visit, ward, lines=[_line("ER", "530000", 0, "577.45")])
    report = _report(ctx)

    assert _std(report)["bed_days"] == 3
    assert _std(report)["recoverable_uplift_try"] == pytest.approx(667.05, abs=0.01)


# --- the days an ICU claim's own lines pay (tasks/todo.md, 2026-10-20) ---------------------------------------------
# EK-2/B 510090 "Yemek, yatak, hasta vizit hizmetlerini kapsar"; the EK-2/C ICU packages P552001-3 / P552006-8 are the
# points of "Yoğun bakım tedavileri" (SUT §2.4.4.H.(2)) and EK-2/C points include "Yatak bedeli" (§2.2.2.B-1.(1).a);
# §2.4.4.H.(8): the first and the exit day are 510090, the days between the packages. A claim that carries one of these
# lines used to show its ICU days as 510010 days (444.70 TL beside an ICU row of 0.00 for 510090 on all three dates).

_D90 = "742.59"  # 510090 on 2026-07-10
_PKG = "2000.00"  # an ICU package day, billed below the tariff (the ICU row then shows what is missing)


def _icu_day_rate(*days: int) -> list[tuple[str, int, str, int, str]]:
    return [("510090", day, _D90, 1, "islem") for day in days]


# Each case: (who, first day, last day, lines [(code, day, billed, quantity, category)],
#             standard-bed days left, recoverable TL on the bed rows, the ICU row's recoverable TL (None: not pinned))
_ICU_CASES = {
    "3 dates, 510090 qty 3 on one line": (
        _ICU_UNIT, 0, 2, [("510090", 0, "2227.77", 3, "islem")], 0, 0.0, 0.0),
    "3 dates, 510090 on each date": (_ICU_UNIT, 0, 2, _icu_day_rate(0, 1, 2), 0, 0.0, 0.0),
    "3 dates, 510090 on the first and the last date, nothing between": (
        _ICU_UNIT, 0, 2, _icu_day_rate(0, 2), 0, 0.0, 0.0),
    "3 dates, the SUT shape: 510090, P552002 as a package, 510090": (
        _ICU_UNIT, 0, 2, [*_icu_day_rate(0), ("P552002", 1, _PKG, 1, "paket"), *_icu_day_rate(2)], 0, 0.0, 0.0),
    "3 dates, 510090, an unprefixed 552002 as a procedure, 510090": (
        _ICU_UNIT, 0, 2, [*_icu_day_rate(0), ("552002", 1, _PKG, 1, "islem"), *_icu_day_rate(2)], 0, 0.0, 0.0),
    "3 dates, 510090 once on the first date": (_ICU_UNIT, 0, 2, _icu_day_rate(0), 1, 222.35, 742.59),
    "3 dates, P552002 qty 3 on the first date": (
        _ICU_UNIT, 0, 2, [("P552002", 0, "6000.00", 3, "paket")], 0, 0.0, 0.0),
    "3 dates, 510090 qty 3 and 510010 qty 3 billed beside it": (
        _ICU_UNIT, 0, 2, [("510090", 0, "2227.77", 3, "islem"), ("510010", 0, "667.05", 3, "islem")], 0, 0.0, 0.0),
    "3 dates, 510090 qty 3 and the ER bed on the first date": (
        _ICU_UNIT, 0, 2, [("510090", 0, "2227.77", 3, "islem"), ("530000", 0, "577.45", 1, "islem")], 0, 0.0, 0.0),
    "3 dates, 510090 qty 3 and a sterile room qty 3": (
        _ICU_UNIT, 0, 2, [("510090", 0, "2227.77", 3, "islem"), ("510100", 0, "5024.28", 3, "islem")], 0, 0.0, 0.0),
    "2 dates, 510090 on both": (_ICU_UNIT, 0, 1, _icu_day_rate(0, 1), 0, 0.0, 0.0),
    "1 date, 510090": (_ICU_UNIT, 0, 0, _icu_day_rate(0), 0, 0.0, 0.0),
    "5 dates, 510090, P552002 qty 3, 510090": (
        _ICU_UNIT, 0, 4, [*_icu_day_rate(0), ("P552002", 1, "6000.00", 3, "paket"), *_icu_day_rate(4)], 0, 0.0, 2119.76),
    "5 dates, 510090 on the first and the last date": (_ICU_UNIT, 0, 4, _icu_day_rate(0, 4), 0, 0.0, 0.0),
    "5 dates, 510090 qty 5": (_ICU_UNIT, 0, 4, [("510090", 0, "3712.95", 5, "islem")], 0, 0.0, 0.0),
    # a day-rate line of quantity 2 or more is the first and the exit day in one line (the ICU motor reads it so)
    "10 dates, 510090 qty 2 on the first date": (_ICU_UNIT, 0, 9, [("510090", 0, "1485.18", 2, "islem")], 0, 0.0, 0.0),
    "10 dates, 510090 qty 2 dated on the last date": (_ICU_UNIT, 0, 9, [("510090", 9, "1485.18", 2, "islem")], 0, 0.0, 0.0),
    "12 dates, 510090 qty 5 from d2 (a daily billing: quantity is days, ward days after)": (
        _ADULT, 0, 11, [("510090", 2, "3712.95", 5, "islem")], 6, 1334.10, 0.0),
    "10 dates, 510090 on the first date and on d3 (two lines)": (_ICU_UNIT, 0, 9, _icu_day_rate(0, 3), 5, 1111.75, 0.0),
    "10 dates, an unprefixed 552002 qty 2 from the first date (a package's quantity is days)": (
        _ICU_UNIT, 0, 9, [("552002", 0, "8119.76", 2, "islem")], 7, 1556.45, None),
    # ward days around the ICU stay on the same claim; an ICU package opens no package window (no işlem grubu,
    # §2.2.2.B-1.(3)), so the ward days before the stay are expected whether the package is spelled with a P or not
    # (WP22; before, the P-prefixed package's one-day window from the admission took d0-d1: 0 days, 0.00)
    "7 dates, ward d0-d1, ICU d2-d5 (510090, two packages, 510090), ward d6": (
        _ADULT, 0, 6,
        [*_icu_day_rate(2), ("P552002", 3, _PKG, 1, "paket"), ("P552002", 4, _PKG, 1, "paket"), *_icu_day_rate(5)],
        2, 444.70, 4119.76),
    "7 dates, the same ICU lines and 510010 billed on the ward days": (
        _ADULT, 0, 6,
        [*_icu_day_rate(2), ("P552002", 3, _PKG, 1, "paket"), ("P552002", 4, _PKG, 1, "paket"), *_icu_day_rate(5),
         ("510010", 0, "444.70", 2, "islem"), ("510010", 6, "222.35", 1, "islem")],
        2, 0.0, 4119.76),
    "7 dates, 510090 on d2 and d5 only, ward around": (_ADULT, 0, 6, _icu_day_rate(2, 5), 2, 444.70, 0.0),
    "7 dates, 510090 qty 4 from d2, ward around": (_ADULT, 0, 6, [("510090", 2, "2970.36", 4, "islem")], 2, 444.70, 0.0),
    "7 dates, 510090 qty 7": (_ADULT, 0, 6, [("510090", 0, "5198.13", 7, "islem")], 0, 0.0, 0.0),
    # (WP22; before: 5 days, 1111.75, the window took d0-d6; the same segment with an unprefixed 552001 gave 10)
    "14 dates, a 3-day ICU segment in the middle": (
        _ADULT, 0, 13, [*_icu_day_rate(5), ("P552001", 6, _PKG, 1, "paket"), *_icu_day_rate(7)], 10, 2223.50, 0.0),
    "14 dates, the same segment with an unprefixed 552001": (
        _ADULT, 0, 13, [*_icu_day_rate(5), ("552001", 6, _PKG, 1, "islem"), *_icu_day_rate(7)], 10, 2223.50, None),
    # lines that say nothing about the stay
    "3 dates, 510090 reversed on each date": (
        _ICU_UNIT, 0, 2, [("510090", d, "-742.59", 1, "islem") for d in (0, 1, 2)], 2, 444.70, None),
    "3 dates, 510090 dated the day before the stay": (_ICU_UNIT, 0, 2, _icu_day_rate(-1), 2, 444.70, 742.59),
    # newborn ICU claims: the ICU motor's, not the newborn motor's; the standard-bed row loses the ICU days
    "newborn, 3 dates, 510090 qty 3": (_NEWBORN, 0, 2, [("510090", 0, "2227.77", 3, "islem")], 0, 0.0, 0.0),
    "NICU, 3 dates, P552006 qty 3": (_NICU, 0, 2, [("P552006", 0, "6000.00", 3, "paket")], 0, 0.0, 0.0),
    "newborn, 3 dates, 510090 qty 3 and the incubator billed beside it": (
        _NEWBORN, 0, 2, [("510090", 0, "2227.77", 3, "islem"), ("510070", 0, "1322.94", 3, "islem")], 0, 0.0, 0.0),
    "newborn, 5 dates, 510090, P552007 qty 3, 510090": (
        _NEWBORN, 0, 4, [*_icu_day_rate(0), ("P552007", 1, "6000.00", 3, "paket"), *_icu_day_rate(4)], 0, 0.0, 2119.76),
    # controls: no ICU code on the claim, the rows are what they were
    "control: an ICU-named unit without any ICU code": (_ICU_UNIT, 0, 2, [], 3, 667.05, None),
    "control: a ward claim billing 530000 on the first date": (_ADULT, 0, 2, [("530000", 0, "577.45", 1, "islem")], 2, 444.70, None),
}


def _icu_row_recoverable(report: BillingActionReport) -> float:
    return round(sum(o["recoverable_uplift_try"] for o in report.icu_puani.opportunities), 2)


@pytest.mark.parametrize("name", list(_ICU_CASES))
def test_each_icu_bill_shows_a_bed_day_only_where_no_icu_line_pays_it(name: str) -> None:
    who, first, last, lines, std_days, recoverable, icu_recoverable = _ICU_CASES[name]
    ctx = _context(
        _stay("CLM", who, first, last),
        lines=[_line("CLM", c, d, b, quantity=q, category=cat) for c, d, b, q, cat in lines],
    )
    report = _report(ctx)

    std = _std(report)
    assert std is not None
    assert std["bed_days"] == std_days, std["detail"]
    assert _newborn(report) is None  # an ICU-coded claim is never the newborn motor's; a control has no newborn signal
    rows = round(sum(a["sgk_uplift_try"] for a in _bed_rows(report)), 2)
    assert rows == pytest.approx(recoverable, abs=0.01)
    if icu_recoverable is not None:
        assert _icu_row_recoverable(report) == pytest.approx(icu_recoverable, abs=0.01)  # the ICU motor is not touched
    _assert_invariants(report)
    # The bill scope sees the same rows as the patient scope.
    bill = _report(ctx, "CLM")
    assert round(sum(a["sgk_uplift_try"] for a in _bed_rows(bill)), 2) == rows
    assert _std(bill)["bed_days"] == std_days
    if icu_recoverable is not None:
        assert _icu_row_recoverable(bill) == pytest.approx(icu_recoverable, abs=0.01)
    _assert_invariants(bill)


@pytest.mark.parametrize("scope", ["patient", "bill"])
def test_the_row_of_an_icu_claim_explains_the_days_it_took_out(scope: str) -> None:
    ctx = _context(_stay("CLM", _ICU_UNIT, 0, 2), lines=[_line("CLM", "510090", 0, "2227.77", quantity=3)])
    std = _std(_report(ctx, "CLM" if scope == "bill" else None))

    assert std is not None
    assert (std["gross_bed_days"], std["bed_days"], std["expected_yatak_try"]) == (3, 0, 0.0)
    assert "inside the ICU stay" in std["detail"] and "510090" in std["detail"] and "2.4.4.H" in std["detail"]
    assert "icu_overlap_days" not in std  # the claim's own line paid its last day: nothing was left for the transfer rule


@pytest.mark.parametrize("scope", ["patient", "bill"])
def test_the_ward_claim_after_an_icu_claim_keeps_the_transfer_day_and_the_icu_claim_loses_its_own_days(scope: str) -> None:
    icu = _stay("ICU", _ICU_UNIT, 0, 2)
    ward = _stay("CLM", _ADULT, 2, 4)
    ctx = _context(icu, ward, lines=[_line("ICU", "510090", 0, _D90), _line("ICU", "510090", 2, _D90)])
    report = _report(ctx, "CLM" if scope == "bill" else None)

    ward_row = _std(report)
    assert ward_row is not None
    assert (ward_row["gross_bed_days"], ward_row["bed_days"]) == (3, 2)  # the ICU last day (12 July) is the ICU's
    assert (ward_row["icu_overlap_days"], ward_row["icu_overlap_dates"]) == (1, ["2026-07-12"])
    assert ward_row["recoverable_uplift_try"] == pytest.approx(2 * 222.35, abs=0.01)
    if scope == "patient":
        icu_row = _std(report, "ICU")
        assert icu_row is not None and icu_row["bed_days"] == 0 and "icu_overlap_days" not in icu_row
    _assert_invariants(report)


def test_a_ward_claim_that_ends_on_the_icu_claims_first_day_is_left_as_it_is() -> None:
    """The service-to-ICU transition across two claims stays out of scope (`yatak_icu_overlap` calls it so): the ward
    claim still expects its last day, which the ICU claim's 510090 pays. Pinned as a stated limit, with its number."""
    ward = _stay("CLM", _ADULT, 0, 2)
    icu = _stay("ICU", _ICU_UNIT, 2, 4)
    ctx = _context(
        ward, icu,
        lines=[_line("ICU", "510090", 2, _D90), _line("ICU", "P552002", 3, _PKG, category="paket"), _line("ICU", "510090", 4, _D90)],
    )
    report = _report(ctx)

    ward_row = _std(report)
    assert ward_row is not None and ward_row["bed_days"] == 3
    assert ward_row["recoverable_uplift_try"] == pytest.approx(3 * 222.35, abs=0.01)
    icu_row = _std(report, "ICU")
    assert icu_row is not None and icu_row["bed_days"] == 0
    _assert_invariants(report)
