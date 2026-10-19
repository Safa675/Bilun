"""Both bed motors on the same bills: no bed day where the SUT says the bed is already paid or may not be billed.

Follow-up of the day-bed change (tasks/todo.md, 2026-10-19). A one-date `yatis` claim that bills 530000 (EK-2/B: "Yatak,
yemek, hasta vizit hizmetlerini kapsar. 510120, 530003 ile birlikte faturalandırılmaz.") or hemodialysis 704210 / 704230
(SUT §2.4.4.D-1.(11): "gündüz yatak ücreti fiyata dâhil") showed a 44.45 TL day bed; a stay of several dates showed the
510010 / Kuvöz days an ER bed (530000) or a special room (510100, 510110) had paid already. The bills are built in memory
and run through `compute_patient_billing_report`; prices are those of the 2026-07-07 list (510010 222.36, 510070
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
    "adult day case over two dates, no EK-2/C procedure (untouched)": (_ADULT, 0, 1, [], "day_case", 2, None, 444.72),
    "adult inpatient claim over two dates with the same session (untouched)": (
        _ADULT, 0, 1, [("702580", 0, "545.76", 1)], "yatis", 2, None, 444.72),
    "newborn day case over two dates with a hyperbaric-oxygen session": (
        _NEWBORN, 0, 1, [("702580", 0, "545.76", 1)], "day_case", 0, 0, 0.0),
    # --- three days: the days the bed-including code pays -----------------------------------------------------
    "control adult 3 days": (_ADULT, 0, 2, [], "yatis", 3, None, 667.08),
    "control newborn 3 days": (_NEWBORN, 0, 2, [], "yatis", 0, 3, 1322.94),
    "adult ER bed on day 1": (_ADULT, 0, 2, [("530000", 0, "577.45", 1)], "yatis", 2, None, 444.72),
    "adult ER bed on day 2": (_ADULT, 0, 2, [("530000", 1, "577.45", 1)], "yatis", 2, None, 444.72),
    "adult ER bed for two days": (_ADULT, 0, 2, [("530000", 0, "1154.90", 2)], "yatis", 1, None, 222.36),
    "adult ER bed and standard bed billed on the other days": (
        _ADULT, 0, 2, [("530000", 0, "577.45", 1), ("510010", 1, "444.72", 2)], "yatis", 2, None, 0.0),
    "adult sterile room all three days": (_ADULT, 0, 2, [("510100", 0, "2981.00", 3)], "yatis", 0, None, 0.0),
    "adult isolation room all three days": (_ADULT, 0, 2, [("510110", 0, "1333.00", 3)], "yatis", 0, None, 0.0),
    "adult hemodialysis on a stay of three dates": (_ADULT, 0, 2, [("704230", 1, "4342.48", 1)], "yatis", 3, None, 667.08),
    "newborn ER bed on day 1": (_NEWBORN, 0, 2, [("530000", 0, "577.45", 1)], "yatis", 0, 2, 881.96),
    "newborn ER bed and the incubator billed on the other days": (
        _NEWBORN, 0, 2, [("530000", 0, "577.45", 1), ("510070", 1, "881.96", 2)], "yatis", 0, 2, 0.0),
    "newborn ER bed and the standard bed billed on the other days": (
        _NEWBORN, 0, 2, [("530000", 0, "577.45", 1), ("510010", 1, "444.72", 2)], "yatis", 2, None, 0.0),
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
    assert std["recoverable_uplift_try"] == pytest.approx(2 * 222.36, abs=0.01)
    _assert_invariants(report)


@pytest.mark.parametrize("scope", ["patient", "bill"])
def test_an_er_day_and_a_different_icu_transfer_day_are_both_taken_out(scope: str) -> None:
    ctx = _ward_after_icu(ward=_ADULT, er_day=2)  # 530000 on 12 July; the ICU last day is 11 July
    report = _report(ctx, "CLM" if scope == "bill" else None)

    std = _std(report)
    assert std is not None
    assert (std["bed_days"], std["icu_overlap_days"]) == (1, 1)  # 13 July
    assert std["recoverable_uplift_try"] == pytest.approx(222.36, abs=0.01)
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
    assert _std(report)["recoverable_uplift_try"] == pytest.approx(667.08, abs=0.01)
