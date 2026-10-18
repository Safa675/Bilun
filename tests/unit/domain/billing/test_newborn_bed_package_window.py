"""The newborn bed motor honours the EK-2/C package window as the standard-bed motor does.

SUT 2.2.2.B-1(1),(3)-(4): a package includes the bed from admission through its window; the days after it are
billed separately. The standard-bed motor reads this since #259; the newborn bed motor counted every day of a
newborn package stay (a 10-day stay with a group-B package: 4,409.80 TL against 0). The mandated case
(`mandated_package_lines`: billed hizmet başı though the package is mandated, the S1 appendectomy P610131,
group C, 8 days) is built on the fixtures of `test_mandated_package_window.py`.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from src.bilun.domain.billing.patient_report import compute_patient_billing_report
from src.bilun.domain.claims.models import ClaimDiagnosis
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.yatak_puani import claim_package_window
from tests.unit.domain.billing.test_blood_uplift_wiring import _claim, _proc
from tests.unit.domain.billing.test_showcase_session_and_package_gaps import GENCER, _Bill, _d

pytestmark = pytest.mark.unit

_NOT_EXEMPT = {"exempt": False, "n_qualifying": 0, "qualifying_diagnoses": []}
_KUVOZ_DAY = 440.98  # 510070 in force in 2026.


def _billed_package_report(*, package_code: str, package_day: date):
    start, end = date(2026, 7, 10), date(2026, 7, 19)
    claim = _claim(
        claim_id="CLM-NB", department="yenidoğan", primary_icd10="Z38.0", admission_date=start,
        discharge_date=end, claim_start_date=start, claim_end_date=end,
    )
    package = _proc(
        procedure_line_id="PK", claim_id="CLM-NB", procedure_code=package_code, procedure_name="paket",
        procedure_category="paket", billed_amount_try=Decimal("5000"), procedure_date=package_day,
    )
    diagnosis = ClaimDiagnosis(
        diagnosis_id="DX1", claim_id="CLM-NB", patient_id="P1", episode_id="E1", icd10_code="Z38.0",
        is_primary=True, diagnosis_role="primary", diagnosis_date=start, exemption_eligible=False,
    )
    ctx = PatientClaimContext(
        patient_id="P1", claims=(claim,), procedure_lines=(package,), material_lines=(), drug_lines=(),
        diagnoses=(diagnosis,),
    )
    return compute_patient_billing_report("P1", claim_context=ctx, copay_exemption=_NOT_EXEMPT)


class TestBilledPackage:
    def test_both_bed_motors_expect_no_day_inside_a_package_that_covers_the_stay(self) -> None:
        report = _billed_package_report(package_code="P600040", package_day=date(2026, 7, 11))

        [newborn] = report.yenidogan_yatak.opportunities
        [standard] = report.yatak_puani.opportunities
        assert (newborn["days"], newborn["bundled_days"]) == (0, 10)
        assert (standard["bed_days"], standard["bundled_days"]) == (0, 10)
        assert report.yenidogan_yatak.confirmed_yenidogan_yatak_try == 0.0
        assert report.yatak_puani.confirmed_yatak_try == 0.0
        assert not [a for a in report.recommended_actions if a["surface"] in ("yenidogan_yatak", "yatak_puani")]

    def test_the_two_bed_motors_agree_on_the_days_after_a_short_window(self) -> None:
        report = _billed_package_report(package_code="P600330", package_day=date(2026, 7, 10))

        [newborn] = report.yenidogan_yatak.opportunities
        [standard] = report.yatak_puani.opportunities
        assert newborn["days"] == 7 and newborn["bundled_days"] == 3
        assert standard["bundled_days"] == 3 and standard["gross_bed_days"] == 10
        # The days after the window are newborn bed days, so the standard bed keeps none of them.
        assert standard["bed_days"] == 0 and standard["newborn_overlap_days"] == 7
        assert report.yenidogan_yatak.confirmed_yenidogan_yatak_try == pytest.approx(7 * _KUVOZ_DAY, abs=0.01)
        assert report.yatak_puani.confirmed_yatak_try == 0.0
        [row] = [a for a in report.recommended_actions if a["surface"] == "yenidogan_yatak"]
        assert Decimal(str(row["sgk_uplift_try"])) == Decimal(str(report.yenidogan_yatak.confirmed_yenidogan_yatak_try))


def _newborn_mandated_bill(*, bed_lines: list[tuple[date, int]]) -> PatientClaimContext:
    """The faulty S1 kept 12 days (14-25 July) as a newborn stay: P610131 mandated, window through 21 July,
    4 days after it. `bed_lines` are (day, quantity) of billed 510070."""
    start = _d("2026-07-14")
    bill = _Bill("C-SH01", "yatis", start, _d("2026-07-25"), package_candidate=True)
    bill.proc("610131", start, specialty=GENCER)
    for day, quantity in bed_lines:
        bill.proc("510070", day, qty=quantity, specialty=GENCER)
    ctx = bill.ctx()
    return replace(ctx, claims=(replace(ctx.claims[0], department="yenidoğan"),))


class TestMandatedPackage:
    def test_the_window_is_the_mandated_one(self) -> None:
        ctx = _newborn_mandated_bill(bed_lines=[])
        window = claim_package_window(ctx.claims[0], list(ctx.procedure_lines))
        assert (window.start, window.end, window.mandated) == (_d("2026-07-14"), _d("2026-07-21"), True)

    def test_days_after_the_window_are_expected_and_in_window_lines_belong_to_the_package(self) -> None:
        in_window = [(_d("2026-07-14") + timedelta(days=i), 1) for i in range(8)]
        report = compute_patient_billing_report(
            "SH", claim_context=_newborn_mandated_bill(bed_lines=in_window), copay_exemption=_NOT_EXEMPT
        )

        [newborn] = report.yenidogan_yatak.opportunities
        assert (newborn["days"], newborn["bundled_days"]) == (4, 8)
        # 14-21 July lines pay the package, not the 4 days after it.
        assert newborn["actual_billed_try"] == 0.0
        assert newborn["recoverable_uplift_try"] == pytest.approx(4 * _KUVOZ_DAY, abs=0.01)

    def test_a_bed_line_after_the_window_counts(self) -> None:
        after = [(_d("2026-07-22") + timedelta(days=i), 1) for i in range(4)]
        report = compute_patient_billing_report(
            "SH", claim_context=_newborn_mandated_bill(bed_lines=after), copay_exemption=_NOT_EXEMPT
        )

        [newborn] = report.yenidogan_yatak.opportunities
        assert newborn["actual_billed_try"] == pytest.approx(4 * _KUVOZ_DAY, abs=0.01)
        assert newborn["recoverable_uplift_try"] == 0.0

    def test_one_multi_day_line_reaching_past_the_window_counts_so_the_stay_is_not_expected_twice(self) -> None:
        report = compute_patient_billing_report(
            "SH", claim_context=_newborn_mandated_bill(bed_lines=[(_d("2026-07-14"), 12)]),
            copay_exemption=_NOT_EXEMPT,
        )

        [newborn] = report.yenidogan_yatak.opportunities
        assert newborn["actual_billed_try"] == pytest.approx(12 * _KUVOZ_DAY, abs=0.01)
        assert newborn["recoverable_uplift_try"] == 0.0
