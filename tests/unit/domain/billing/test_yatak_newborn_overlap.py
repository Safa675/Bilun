"""The standard-bed and the newborn bed motors must not both count a newborn's days.

EK-2/B gives 510010, 510070, 510081 and 510090 the same text, "Yemek, yatak, hasta vizit hizmetlerini kapsar":
they are alternatives for one patient-day, which the project already holds for 510090 against 510010
(`prose_rules/yatak_icu_overlap.py`). Before this step a newborn stay was counted twice: 3 days of Kuvöz
(1,322.94 TL) and the same 3 days of standard bed (667.08 TL) both entered `sgk_uplift_try`.

The bills are built in memory; amounts are read from the engine's own opportunities, never typed here.
"""

from __future__ import annotations

import copy
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest

from src.bilun.domain.billing.claim_yatak_newborn_overlap import reconcile_yatak_newborn_overlap
from src.bilun.domain.billing.patient_report import compute_patient_billing_report
from src.bilun.domain.billing.types import (
    EXACTNESS_STATUS_EXACT,
    EXACTNESS_STATUS_MISSING_INPUTS,
    BillingActionReport,
    YatakPuaniReview,
    YenidoganYatakReview,
)
from src.bilun.domain.claims.models import ClaimDiagnosis
from src.bilun.domain.claims.patient_context import PatientClaimContext
from tests.unit.domain.billing.test_blood_uplift_wiring import _claim, _proc

pytestmark = pytest.mark.unit

_NOT_EXEMPT = {"exempt": False, "n_qualifying": 0, "qualifying_diagnoses": []}
_START = date(2026, 7, 10)


def _stay_context(
    *,
    newborn: bool,
    days: int = 3,
    bed_code: str | None = None,
    bed_billed: str = "0",
    standard_bed_billed: str | None = None,
    standard_bed_units: int | None = None,
    standard_bed_start_day: int = 0,
    bed_units: int | None = None,
    department: str | None = None,
    icd10: str | None = None,
) -> PatientClaimContext:
    """One inpatient claim of `days` inclusive days; a newborn one (Z38.0, yenidoğan) or an adult one."""
    end = _START + timedelta(days=days - 1)
    claim = _claim(
        claim_id="CLM-STAY",
        department=department or ("yenidoğan" if newborn else "kardiyoloji"),
        primary_icd10=icd10 or ("Z38.0" if newborn else "I10"),
        admission_date=_START,
        discharge_date=end,
        claim_start_date=_START,
        claim_end_date=end,
    )
    lines = [
        _proc(procedure_line_id="EXAM", claim_id="CLM-STAY", procedure_code="520010", procedure_name="Muayene",
              billed_amount_try=Decimal("10"), procedure_date=_START)
    ]
    if bed_code is not None:
        lines.append(_proc(procedure_line_id="NB-BED", claim_id="CLM-STAY", procedure_code=bed_code,
                           procedure_name="bed", quantity=bed_units or days, billed_amount_try=Decimal(bed_billed),
                           procedure_date=_START))
    if standard_bed_billed is not None:
        lines.append(_proc(procedure_line_id="STD-BED", claim_id="CLM-STAY", procedure_code="510010",
                           procedure_name="Standart yatak", quantity=standard_bed_units or days,
                           billed_amount_try=Decimal(standard_bed_billed),
                           procedure_date=_START + timedelta(days=standard_bed_start_day)))
    diagnosis = ClaimDiagnosis(
        diagnosis_id="DX1", claim_id="CLM-STAY", patient_id="P1", episode_id="E1",
        icd10_code=claim.primary_icd10, is_primary=True, diagnosis_role="primary",
        diagnosis_date=_START, exemption_eligible=False,
    )
    return PatientClaimContext(
        patient_id="P1", claims=(claim,), procedure_lines=tuple(lines), material_lines=(),
        drug_lines=(), diagnoses=(diagnosis,),
    )


def _report(**kwargs: Any) -> BillingActionReport:
    return compute_patient_billing_report(
        "P1", claim_context=_stay_context(**kwargs), copay_exemption=_NOT_EXEMPT
    )


class TestPipeline:
    def test_a_newborn_stay_is_counted_once_not_by_both_bed_motors(self) -> None:
        report = _report(newborn=True)

        [newborn] = report.yenidogan_yatak.opportunities
        [standard] = report.yatak_puani.opportunities
        assert newborn["days"] == 3
        assert report.yenidogan_yatak.confirmed_yenidogan_yatak_try == newborn["expected_try"] > 0
        # The standard bed expects none of the newborn days; the gross stay and the cause stay on the row.
        assert standard["gross_bed_days"] == 3
        assert standard["bed_days"] == 0
        assert standard["expected_yatak_try"] == 0.0
        assert standard["recoverable_uplift_try"] == 0.0
        assert standard["newborn_overlap_days"] == 3
        assert report.yatak_puani.confirmed_yatak_try == 0.0
        assert not [a for a in report.recommended_actions if a["surface"] == "yatak_puani"]

    def test_the_detail_says_why_the_standard_bed_days_are_gone(self) -> None:
        [standard] = _report(newborn=True).yatak_puani.opportunities

        assert "3 day(s)" in standard["detail"]
        assert "newborn bed" in standard["detail"]
        assert "510070 / 510081" in standard["detail"]

    @pytest.mark.parametrize("bed_code", ["510070", "510081"])
    def test_a_newborn_bed_billed_in_full_does_not_make_the_standard_bed_look_unbilled(self, bed_code: str) -> None:
        """The reverse bill: the stay is paid by the newborn bed lines, so no standard-bed day is missing."""
        expected = {"510070": "1322.94", "510081": "933.90"}[bed_code]
        report = _report(newborn=True, bed_code=bed_code, bed_billed=expected)

        assert report.yenidogan_yatak.confirmed_yenidogan_yatak_try == 0.0
        assert report.yatak_puani.confirmed_yatak_try == 0.0
        [standard] = report.yatak_puani.opportunities
        assert standard["bed_days"] == 0 and standard["newborn_overlap_days"] == 3
        assert not [a for a in report.recommended_actions if a["surface"] in ("yatak_puani", "yenidogan_yatak")]

    def test_an_adult_stay_keeps_its_standard_bed_days(self) -> None:
        """The control: no newborn signal, nothing is reconciled and no key is added."""
        report = _report(newborn=False)

        assert report.yenidogan_yatak.opportunities == []
        [standard] = report.yatak_puani.opportunities
        assert standard["bed_days"] == 3
        assert standard["expected_yatak_try"] == pytest.approx(667.08, abs=0.005)
        assert standard["recoverable_uplift_try"] == pytest.approx(667.08, abs=0.005)
        assert "newborn_overlap_days" not in standard
        assert report.yatak_puani.confirmed_yatak_try == pytest.approx(667.08, abs=0.005)

    def test_a_stay_billed_on_the_standard_bed_is_the_standard_bed_motors_alone(self) -> None:
        """The claim has stated its bed (510010): the newborn motor stands down, the standard-bed motor nets
        its own lines. Before, a correctly billed stay still got a full Kuvöz row (1,322.94 on 3 days)."""
        report = _report(newborn=True, standard_bed_billed="667.08")

        assert report.yenidogan_yatak.opportunities == []
        [standard] = report.yatak_puani.opportunities
        assert (standard["bed_days"], standard["actual_billed_try"]) == (3, pytest.approx(667.08, abs=0.005))
        assert standard["recoverable_uplift_try"] == 0.0
        assert "newborn_overlap_days" not in standard
        assert not [a for a in report.recommended_actions if a["surface"] in ("yenidogan_yatak", "yatak_puani")]

    def test_a_partly_billed_standard_bed_leaves_the_unbilled_standard_bed_days(self) -> None:
        report = _report(newborn=True, standard_bed_billed="222.36", standard_bed_units=1)

        assert report.yenidogan_yatak.opportunities == []
        assert report.yatak_puani.confirmed_yatak_try == pytest.approx(2 * 222.36, abs=0.005)

    def test_a_stay_billed_incubator_then_standard_bed_exactly_leaves_nothing_on_both_motors(self) -> None:
        """The reviewer's cliff: 2 Kuvöz days then 8 standard-bed days, billed exactly. The newborn motor owns the
        2 Kuvöz days, the standard-bed motor the 8 days it was billed for; neither recovers anything (the first
        version of the stand-down expected 8 x 440.98 = 3,527.84 Kuvöz beside the billed 510010)."""
        report = _report(
            newborn=True, days=10, bed_code="510070", bed_billed="881.96", bed_units=2,
            standard_bed_billed="1778.88", standard_bed_units=8, standard_bed_start_day=2,
        )

        [newborn] = report.yenidogan_yatak.opportunities
        [standard] = report.yatak_puani.opportunities
        assert (newborn["days"], newborn["standard_bed_days"]) == (2, 8)
        assert newborn["recoverable_uplift_try"] == 0.0
        # The standard bed keeps the 8 days it was billed for and nets them: nothing left.
        assert (standard["gross_bed_days"], standard["bed_days"], standard["newborn_overlap_days"]) == (10, 8, 2)
        assert standard["actual_billed_try"] == pytest.approx(1778.88, abs=0.005)
        assert standard["recoverable_uplift_try"] == 0.0
        assert report.yenidogan_yatak.confirmed_yenidogan_yatak_try == 0.0
        assert report.yatak_puani.confirmed_yatak_try == 0.0
        assert not [a for a in report.recommended_actions if a["surface"] in ("yenidogan_yatak", "yatak_puani")]

    def test_the_days_beside_a_part_billed_standard_bed_are_counted_once(self) -> None:
        """Kuvöz for 1 day and standard bed for 3 of 10 days: 6 days are unbilled and expected once, as Kuvöz."""
        report = _report(
            newborn=True, days=10, bed_code="510070", bed_billed="440.98", bed_units=1,
            standard_bed_billed="667.08", standard_bed_units=3, standard_bed_start_day=1,
        )

        assert report.yenidogan_yatak.confirmed_yenidogan_yatak_try == pytest.approx(6 * 440.98, abs=0.01)
        assert report.yatak_puani.confirmed_yatak_try == 0.0  # the 3 standard days are billed in full
        [standard] = report.yatak_puani.opportunities
        assert standard["bed_days"] == 3
        counted = [a["sgk_uplift_try"] for a in report.recommended_actions if a["sgk_uplift_try"] is not None]
        assert sum(Decimal(str(v)) for v in counted).quantize(Decimal("0.01")) == Decimal(
            str(report.sgk_uplift_try)
        ).quantize(Decimal("0.01"))

    def test_an_icu_named_unit_that_bills_kuvoz_in_full_leaves_nothing_on_both_motors(self) -> None:
        """Review round 3, H4: a unit named YBÜ (no ICU code) whose 6-day stay is billed in full as Kuvöz: the
        newborn motor nets it and owns the days, so the standard bed cannot call them missing (it showed 1,334.16)."""
        report = _report(
            newborn=True, days=6, department="Çocuk YBÜ", icd10="P22.0", bed_code="510070", bed_billed="2645.88",
        )

        assert report.yenidogan_yatak.confirmed_yenidogan_yatak_try == 0.0
        assert report.yatak_puani.confirmed_yatak_try == 0.0
        assert not [a for a in report.recommended_actions if a["surface"] in ("yenidogan_yatak", "yatak_puani")]

    def test_double_covered_line_days_leave_no_standard_bed_shortfall(self) -> None:
        """Review round 3, H2: Kuvöz x7 billed in full plus two 510010 lines billed 0 TL on a 7-day stay."""
        report = _report(
            newborn=True, days=7, bed_code="510070", bed_billed="3086.86", bed_units=7,
            standard_bed_billed="0", standard_bed_units=2, standard_bed_start_day=1,
        )

        [standard] = report.yatak_puani.opportunities
        assert standard["bed_days"] == 0 and standard["recoverable_uplift_try"] == 0.0
        assert report.yatak_puani.confirmed_yatak_try == 0.0

    @pytest.mark.parametrize("department", ["Pediatri", "Çocuk Sağlığı ve Hastalıkları"])
    def test_a_correctly_billed_pediatric_admission_gets_no_kuvoz_row(self, department: str) -> None:
        """Review F1, kept: billed on the standard bed, as a pediatric stay is, it shows no Kuvöz row. (A pediatric
        ward is no newborn signal since the detection was narrowed; the stand-down on a billed standard bed is
        pinned for a real newborn signal by `test_a_stay_billed_on_the_standard_bed_is_the_standard_bed_motors_alone`.)"""
        report = _report(newborn=False, department=department, icd10="J18.9", standard_bed_billed="667.08")

        assert report.yenidogan_yatak.opportunities == []
        assert report.yatak_puani.confirmed_yatak_try == 0.0
        assert not [a for a in report.recommended_actions if a["surface"] in ("yenidogan_yatak", "yatak_puani")]

    @pytest.mark.parametrize("department", ["Pediatri", "PEDİATRİ", "Çocuk Sağlığı ve Hastalıkları", "Çocuk Cerrahisi"])
    def test_a_pediatric_admission_with_no_bed_billed_is_a_standard_bed_stay_not_a_kuvoz_one(
        self, department: str
    ) -> None:
        """Newborn detection: a pediatric ward is no newborn signal (the claim has no age; SUT's newborn is 0-28
        days). A 3-day pneumonia stay with no bed billed showed a 1,322.94 TL Kuvöz row; it is the standard-bed
        motor's stay like any other inpatient claim, and the two bed motors still count each day once."""
        report = _report(newborn=False, department=department, icd10="J18.9")

        assert report.yenidogan_yatak.opportunities == []
        [standard] = report.yatak_puani.opportunities
        assert (standard["gross_bed_days"], standard["bed_days"]) == (3, 3)
        assert "newborn_overlap_days" not in standard
        assert standard["recoverable_uplift_try"] == pytest.approx(667.08, abs=0.005)
        assert report.yatak_puani.confirmed_yatak_try == pytest.approx(667.08, abs=0.005)
        assert not [a for a in report.recommended_actions if a["surface"] == "yenidogan_yatak"]

    @pytest.mark.parametrize("department", ["YENİDOĞAN", "YENIDOGAN", "Yenidogan", "Neonatoloji", "NEONATOLOJİ"])
    def test_a_newborn_named_department_without_a_newborn_code_is_a_kuvoz_stay_in_any_spelling(
        self, department: str
    ) -> None:
        """The Turkish capitals, the ASCII spelling and 'neonatoloji' used to read as no signal and left the stay to
        the standard bed; they read like 'Yenidoğan' now, and the standard-bed motor gives the 3 days up."""
        report = _report(newborn=False, department=department, icd10="J18.9")

        [newborn] = report.yenidogan_yatak.opportunities
        [standard] = report.yatak_puani.opportunities
        assert newborn["days"] == 3 and newborn["expected_try"] == pytest.approx(1322.94, abs=0.005)
        assert (standard["bed_days"], standard["newborn_overlap_days"]) == (0, 3)
        assert report.yatak_puani.confirmed_yatak_try == 0.0
        assert report.yenidogan_yatak.confirmed_yenidogan_yatak_try == pytest.approx(1322.94, abs=0.005)

    def test_a_negative_standard_bed_line_recovers_nothing_on_the_days_the_newborn_bed_took(self) -> None:
        """Review F3: a credit line of -44.47 used to leave 44.47 recoverable on a day with expected 0."""
        report = _report(newborn=True, days=1, bed_code="510070", bed_billed="440.98", standard_bed_billed="-44.47")

        [standard] = report.yatak_puani.opportunities
        assert standard["expected_yatak_try"] == 0.0
        assert standard["recoverable_uplift_try"] == 0.0
        assert report.yatak_puani.confirmed_yatak_try == 0.0
        assert not [a for a in report.recommended_actions if a["surface"] == "yatak_puani"]


def _yatak_opportunity(claim_id: str, *, bed_days: int = 5, billed: float = 0.0, rate: float = 222.36) -> dict[str, Any]:
    expected = round(bed_days * rate, 2)
    return {
        "type": "yatak_puani_standard_bed",
        "claim_id": claim_id,
        "bed_code": "510010",
        "bed_days": bed_days,
        "gross_bed_days": bed_days,
        "daily_rate_try": rate,
        "expected_yatak_try": expected,
        "actual_billed_try": billed,
        "recoverable_uplift_try": round(max(0.0, expected - billed), 2),
        "detail": "Standart yatak (510010): ...",
        "included_in_sgk_total": True,
    }


def _newborn_review(*opportunities: dict[str, Any]) -> YenidoganYatakReview:
    return YenidoganYatakReview(opportunities=list(opportunities), exactness_status=EXACTNESS_STATUS_EXACT)


def _yatak_review(*opportunities: dict[str, Any]) -> YatakPuaniReview:
    return YatakPuaniReview(
        opportunities=list(opportunities), exactness_status=EXACTNESS_STATUS_EXACT,
        rule_source="SUT §2.2.2 test source",
    )


class TestReconcile:
    def test_only_the_claim_with_a_newborn_bed_is_reconciled(self) -> None:
        mine, other = _yatak_opportunity("C1"), _yatak_opportunity("C2")

        result = reconcile_yatak_newborn_overlap(
            _yatak_review(mine, other), _newborn_review({"claim_id": "C1", "days": 3})
        )

        first, second = result.opportunities
        assert first["bed_days"] == 2 and first["newborn_overlap_days"] == 3
        assert first["expected_yatak_try"] == pytest.approx(444.72, abs=0.005)
        assert first["recoverable_uplift_try"] == pytest.approx(444.72, abs=0.005)
        assert second is other  # untouched, same object

    def test_the_recoverable_amount_is_recomputed_net_of_the_billed_standard_bed(self) -> None:
        opp = _yatak_opportunity("C1", bed_days=5, billed=222.36)

        [adjusted] = reconcile_yatak_newborn_overlap(
            _yatak_review(opp), _newborn_review({"claim_id": "C1", "days": 3})
        ).opportunities

        assert adjusted["expected_yatak_try"] == pytest.approx(444.72, abs=0.005)
        assert adjusted["actual_billed_try"] == pytest.approx(222.36, abs=0.005)
        assert adjusted["recoverable_uplift_try"] == pytest.approx(222.36, abs=0.005)

    def test_more_newborn_days_than_bed_days_floors_at_zero_and_reports_the_days_removed(self) -> None:
        [adjusted] = reconcile_yatak_newborn_overlap(
            _yatak_review(_yatak_opportunity("C1", bed_days=3)), _newborn_review({"claim_id": "C1", "days": 10})
        ).opportunities

        assert adjusted["bed_days"] == 0
        assert adjusted["expected_yatak_try"] == 0.0
        assert adjusted["recoverable_uplift_try"] == 0.0
        assert adjusted["newborn_overlap_days"] == 3  # the days actually taken out, not the newborn days

    def test_billed_standard_bed_money_never_makes_the_recoverable_negative(self) -> None:
        [adjusted] = reconcile_yatak_newborn_overlap(
            _yatak_review(_yatak_opportunity("C1", bed_days=3, billed=900.0)),
            _newborn_review({"claim_id": "C1", "days": 3}),
        ).opportunities

        assert adjusted["recoverable_uplift_try"] == 0.0
        assert adjusted["actual_billed_try"] == 900.0  # the billed line stays visible

    def test_a_credit_line_never_makes_the_recoverable_exceed_the_expected_standard_bed(self) -> None:
        [adjusted] = reconcile_yatak_newborn_overlap(
            _yatak_review(_yatak_opportunity("C1", bed_days=4, billed=-44.47)),
            _newborn_review({"claim_id": "C1", "days": 3}),
        ).opportunities

        assert adjusted["expected_yatak_try"] == pytest.approx(222.36, abs=0.005)
        assert adjusted["recoverable_uplift_try"] == pytest.approx(222.36, abs=0.005)  # was 266.83

    @pytest.mark.parametrize(
        "yatak,newborn",
        [
            (_yatak_review(), _newborn_review({"claim_id": "C1", "days": 3})),
            (_yatak_review(_yatak_opportunity("C1")), _newborn_review()),
            (_yatak_review(_yatak_opportunity("C1")), _newborn_review({"claim_id": "C-OTHER", "days": 3})),
            (_yatak_review(_yatak_opportunity("C1")), _newborn_review({"claim_id": "C1", "days": 0})),
            (_yatak_review(_yatak_opportunity("C1", bed_days=0)), _newborn_review({"claim_id": "C1", "days": 3})),
        ],
        ids=["no standard bed", "no newborn bed", "other claim", "newborn days 0", "standard bed already 0"],
    )
    def test_nothing_to_reconcile_returns_the_same_review(self, yatak: YatakPuaniReview, newborn: YenidoganYatakReview) -> None:
        assert reconcile_yatak_newborn_overlap(yatak, newborn) is yatak

    def test_a_review_without_inputs_passes_through(self) -> None:
        missing = YatakPuaniReview(exactness_status=EXACTNESS_STATUS_MISSING_INPUTS)

        assert reconcile_yatak_newborn_overlap(missing, _newborn_review({"claim_id": "C1", "days": 3})) is missing

    def test_metadata_is_kept_and_the_input_is_not_mutated(self) -> None:
        opp = _yatak_opportunity("C1")
        before = copy.deepcopy(opp)
        review = _yatak_review(opp)

        result = reconcile_yatak_newborn_overlap(review, _newborn_review({"claim_id": "C1", "days": 3}))

        assert result is not review
        assert opp == before
        assert review.opportunities == [before]
        assert result.exactness_status == EXACTNESS_STATUS_EXACT
        assert result.rule_source == "SUT §2.2.2 test source"
        assert result.unavailable_reason == review.unavailable_reason
        assert result.required_inputs_missing == review.required_inputs_missing
        assert result.opportunities[0]["detail"].startswith(before["detail"])
        assert result.opportunities[0]["detail"] != before["detail"]


def _transfer_context(
    *, ward_end: date = date(2026, 7, 12), ward_newborn: bool = True
) -> PatientClaimContext:
    """The reviewer's bill: a NICU claim 8-10 July (510090 on 8 and 10 July) and the ward claim of the same
    baby 10-12 July with no bed line. The ICU last day, 10 July, is paid by 510090 on the first claim.
    ``ward_end`` shortens the ward claim (10 July: a stay of one date); ``ward_newborn=False`` makes it an adult claim."""
    icu = _claim(
        claim_id="CLM-ICU", department="Yenidoğan Yoğun Bakım", primary_icd10="P22.0",
        admission_date=date(2026, 7, 8), discharge_date=date(2026, 7, 10),
        claim_start_date=date(2026, 7, 8), claim_end_date=date(2026, 7, 10),
    )
    ward = _claim(
        claim_id="CLM-WARD", department="yenidoğan" if ward_newborn else "kardiyoloji",
        primary_icd10="P22.0" if ward_newborn else "I10",
        admission_date=date(2026, 7, 10), discharge_date=ward_end,
        claim_start_date=date(2026, 7, 10), claim_end_date=ward_end,
    )
    lines = (
        _proc(procedure_line_id="I1", claim_id="CLM-ICU", procedure_code="510090", procedure_name="Yoğun bakım",
              billed_amount_try=Decimal("0"), procedure_date=date(2026, 7, 8)),
        _proc(procedure_line_id="I2", claim_id="CLM-ICU", procedure_code="510090", procedure_name="Yoğun bakım",
              billed_amount_try=Decimal("0"), procedure_date=date(2026, 7, 10)),
        _proc(procedure_line_id="W1", claim_id="CLM-WARD", procedure_code="520010", procedure_name="Muayene",
              billed_amount_try=Decimal("10"), procedure_date=date(2026, 7, 10)),
    )
    diagnoses = tuple(
        ClaimDiagnosis(
            diagnosis_id=f"DX-{claim_id}", claim_id=claim_id, patient_id="P1", episode_id="E1", icd10_code=icd10,
            is_primary=True, diagnosis_role="primary", diagnosis_date=date(2026, 7, 8), exemption_eligible=False,
        )
        for claim_id, icd10 in (("CLM-ICU", "P22.0"), ("CLM-WARD", "P22.0" if ward_newborn else "I10"))
    )
    return PatientClaimContext(
        patient_id="P1", claims=(icu, ward), procedure_lines=lines, material_lines=(), drug_lines=(),
        diagnoses=diagnoses,
    )


class TestIcuTransferDay:
    @pytest.mark.parametrize("scope", ["patient", "bill"])
    def test_the_icu_last_day_of_another_claim_is_neither_a_newborn_nor_a_standard_bed_day(self, scope: str) -> None:
        ctx = _transfer_context()
        if scope == "bill":
            ctx = ctx.slice_for_claim("CLM-WARD")
        report = compute_patient_billing_report("P1", claim_context=ctx, copay_exemption=_NOT_EXEMPT)

        [newborn] = [o for o in report.yenidogan_yatak.opportunities if o["claim_id"] == "CLM-WARD"]
        assert newborn["days"] == 2  # 11 and 12 July; 10 July is the ICU last day
        assert newborn["expected_try"] == pytest.approx(2 * 440.98, abs=0.005)
        assert newborn["icu_overlap_dates"] == ["2026-07-10"]
        # The ICU claim itself is the ICU motor's.
        assert not [o for o in report.yenidogan_yatak.opportunities if o["claim_id"] == "CLM-ICU"]

        [standard] = [o for o in report.yatak_puani.opportunities if o["claim_id"] == "CLM-WARD"]
        assert standard["icu_overlap_dates"] == ["2026-07-10"]  # the standard-bed motor drops the same day
        assert standard["bed_days"] == 0 and standard["recoverable_uplift_try"] == 0.0
        # Both bed motors dropped the same day, so no day is left over: the standard bed keeps nothing.
        assert standard["newborn_overlap_days"] == 2
        counted = [a["sgk_uplift_try"] for a in report.recommended_actions if a["sgk_uplift_try"] is not None]
        assert sum(Decimal(str(v)) for v in counted).quantize(Decimal("0.01")) == Decimal(
            str(report.sgk_uplift_try)
        ).quantize(Decimal("0.01"))


# --- SUT §2.2.2.(3): a stay under 24 hours is billed at the day bed 510120 (44.45 TRY) ----------------------
# A stay of one date (admission date == discharge date) is certainly under 24 hours. Both bed motors price its one
# day at the day bed, not as a full 510010 (222.36) or Kuvöz (440.98) day, and no day is counted twice.


def _one_date_context(
    lines: tuple[tuple[str, str], ...] = (),
    *,
    newborn: bool = True,
    department: str | None = None,
    icd10: str | None = None,
) -> PatientClaimContext:
    """One inpatient claim of one date (10 July) with an exam line and ``lines`` = (code, billed amount)."""
    claim = _claim(
        claim_id="CLM-STAY",
        department=department or ("yenidoğan" if newborn else "kardiyoloji"),
        primary_icd10=icd10 or ("Z38.0" if newborn else "I10"),
        admission_date=_START, discharge_date=_START, claim_start_date=_START, claim_end_date=_START,
    )
    procedure_lines = [
        _proc(procedure_line_id="EXAM", claim_id="CLM-STAY", procedure_code="520010", procedure_name="Muayene",
              billed_amount_try=Decimal("10"), procedure_date=_START)
    ]
    for index, (code, billed) in enumerate(lines):
        procedure_lines.append(
            _proc(procedure_line_id=f"L{index}", claim_id="CLM-STAY", procedure_code=code, procedure_name="bed",
                  procedure_category="paket" if code.startswith("P6") else "islem",
                  billed_amount_try=Decimal(billed), procedure_date=_START)
        )
    diagnosis = ClaimDiagnosis(
        diagnosis_id="DX1", claim_id="CLM-STAY", patient_id="P1", episode_id="E1", icd10_code=claim.primary_icd10,
        is_primary=True, diagnosis_role="primary", diagnosis_date=_START, exemption_eligible=False,
    )
    return PatientClaimContext(
        patient_id="P1", claims=(claim,), procedure_lines=tuple(procedure_lines), material_lines=(),
        drug_lines=(), diagnoses=(diagnosis,),
    )


def _one_date_report(lines: tuple[tuple[str, str], ...] = (), **kwargs: Any) -> BillingActionReport:
    return compute_patient_billing_report(
        "P1", claim_context=_one_date_context(lines, **kwargs), copay_exemption=_NOT_EXEMPT
    )


def _bed_rows(report: BillingActionReport) -> list[dict[str, Any]]:
    return [a for a in report.recommended_actions if a["surface"] in ("yenidogan_yatak", "yatak_puani")]


class TestStayUnder24Hours:
    def test_a_newborn_stay_of_one_date_is_one_day_bed_day_counted_once(self) -> None:
        report = _one_date_report()

        [newborn] = report.yenidogan_yatak.opportunities
        [standard] = report.yatak_puani.opportunities
        assert (newborn["days"], newborn["bed_code"]) == (1, "510120")
        assert newborn["expected_try"] == pytest.approx(44.45, abs=0.005)  # was 440.98
        assert newborn["recoverable_uplift_try"] == pytest.approx(44.45, abs=0.005)
        # The standard bed expects none of the day the newborn row owns; the gross stay and the cause stay on the row.
        assert (standard["gross_bed_days"], standard["bed_days"], standard["newborn_overlap_days"]) == (1, 0, 1)
        assert standard["expected_yatak_try"] == 0.0 and standard["recoverable_uplift_try"] == 0.0
        assert report.yenidogan_yatak.confirmed_yenidogan_yatak_try == pytest.approx(44.45, abs=0.005)
        assert report.yatak_puani.confirmed_yatak_try == 0.0
        assert [(a["surface"], a["sgk_uplift_try"]) for a in _bed_rows(report)] == [
            ("yenidogan_yatak", pytest.approx(44.45, abs=0.005))
        ]
        assert report.sgk_uplift_try == pytest.approx(44.45, abs=0.005)  # headline = the one row

    def test_the_standard_bed_detail_says_the_newborn_row_owns_the_day_at_the_day_bed(self) -> None:
        [standard] = _one_date_report().yatak_puani.opportunities

        assert "on the newborn bed row" in standard["detail"]
        assert "510070 / 510081" not in standard["detail"]  # the day is no Kuvöz or Kot day

    def test_a_stay_billed_as_the_day_bed_leaves_nothing(self) -> None:
        """Review F5: a correctly billed 510120 still showed 440.98 Kuvöz; it is now the stated bed."""
        report = _one_date_report((("510120", "44.45"),))

        assert report.yenidogan_yatak.opportunities == []  # stands down: the claim has stated its bed
        [standard] = report.yatak_puani.opportunities
        assert (standard["bed_code"], standard["bed_days"]) == ("510120", 1)
        assert standard["actual_billed_try"] == pytest.approx(44.45, abs=0.005)
        assert standard["recoverable_uplift_try"] == 0.0
        assert report.sgk_uplift_try == 0.0
        assert _bed_rows(report) == []

    def test_a_day_bed_billed_in_part_leaves_the_remainder_on_the_standard_bed_row(self) -> None:
        report = _one_date_report((("510120", "20.00"),))

        assert report.yenidogan_yatak.opportunities == []
        assert report.yatak_puani.confirmed_yatak_try == pytest.approx(24.45, abs=0.005)
        assert [(a["surface"], a["sgk_uplift_try"]) for a in _bed_rows(report)] == [
            ("yatak_puani", pytest.approx(24.45, abs=0.005))
        ]
        assert report.sgk_uplift_try == pytest.approx(24.45, abs=0.005)

    def test_a_stay_billed_as_a_full_standard_day_leaves_nothing(self) -> None:
        report = _one_date_report((("510010", "222.36"),))

        assert report.yenidogan_yatak.opportunities == []
        [standard] = report.yatak_puani.opportunities
        assert standard["expected_yatak_try"] == pytest.approx(44.45, abs=0.005)
        assert standard["recoverable_uplift_try"] == 0.0
        assert report.sgk_uplift_try == 0.0

    @pytest.mark.parametrize(
        ("code", "billed", "recoverable"),
        [("510070", "440.98", 0.0), ("510081", "311.30", 0.0), ("510070", "20.00", 24.45)],
    )
    def test_a_newborn_bed_billed_for_a_stay_of_one_date_is_netted_against_the_day_bed(
        self, code: str, billed: str, recoverable: float
    ) -> None:
        report = _one_date_report(((code, billed),))

        [newborn] = report.yenidogan_yatak.opportunities
        assert (newborn["bed_code"], newborn["days"]) == ("510120", 1)
        assert newborn["expected_try"] == pytest.approx(44.45, abs=0.005)
        assert newborn["actual_billed_try"] == pytest.approx(float(billed), abs=0.005)
        assert newborn["recoverable_uplift_try"] == pytest.approx(recoverable, abs=0.005)
        [standard] = report.yatak_puani.opportunities
        assert standard["bed_days"] == 0 and standard["recoverable_uplift_try"] == 0.0
        assert report.sgk_uplift_try == pytest.approx(recoverable, abs=0.005)

    def test_a_package_on_the_day_bundles_it_on_both_motors(self) -> None:
        report = _one_date_report((("P600040", "5000"),))

        [newborn] = report.yenidogan_yatak.opportunities
        [standard] = report.yatak_puani.opportunities
        assert (newborn["days"], newborn["bundled_days"], newborn["expected_try"]) == (0, 1, 0.0)
        assert (standard["bed_days"], standard["bundled_days"], standard["expected_yatak_try"]) == (0, 1, 0.0)
        assert report.yenidogan_yatak.confirmed_yenidogan_yatak_try == 0.0
        assert report.yatak_puani.confirmed_yatak_try == 0.0

    def test_an_icu_claim_of_one_date_is_the_icu_motors_alone(self) -> None:
        report = _one_date_report((("510090", "0"),), icd10="P22.0", department="Yenidoğan Yoğun Bakım")

        assert report.yenidogan_yatak.opportunities == []
        [standard] = report.yatak_puani.opportunities
        assert standard["bed_days"] == 0  # the claim's own last day is a 510090 day
        assert report.yatak_puani.confirmed_yatak_try == 0.0
        assert not [a for a in _bed_rows(report)]

    def test_a_unit_named_as_an_icu_with_nothing_billed_keeps_its_day_on_the_standard_bed_at_the_day_bed(self) -> None:
        """The stated limit of the ICU department gate (the standard-bed motor reads no department): the newborn
        motor stands down and the standard bed still counts the day, now at the day bed (was 222.36)."""
        report = _one_date_report(department="Yenidoğan Yoğun Bakım", icd10="P22.0")

        assert report.yenidogan_yatak.opportunities == []
        [standard] = report.yatak_puani.opportunities
        assert (standard["bed_code"], standard["bed_days"]) == ("510120", 1)
        assert report.yatak_puani.confirmed_yatak_try == pytest.approx(44.45, abs=0.005)

    @pytest.mark.parametrize(
        ("lines", "recoverable"),
        [((), 44.45), ((("510120", "44.45"),), 0.0), ((("510120", "20.00"),), 24.45), ((("510010", "222.36"),), 0.0)],
        ids=["nothing", "day-bed-in-full", "day-bed-in-part", "standard-in-full"],
    )
    def test_an_adult_stay_of_one_date_is_the_standard_bed_motors_at_the_day_bed(
        self, lines: tuple[tuple[str, str], ...], recoverable: float
    ) -> None:
        report = _one_date_report(lines, newborn=False)

        assert report.yenidogan_yatak.opportunities == []
        [standard] = report.yatak_puani.opportunities
        assert (standard["bed_code"], standard["bed_days"], standard["same_day_stay"]) == ("510120", 1, True)
        assert "newborn_overlap_days" not in standard
        assert report.yatak_puani.confirmed_yatak_try == pytest.approx(recoverable, abs=0.005)
        assert report.sgk_uplift_try == pytest.approx(recoverable, abs=0.005)

    @pytest.mark.parametrize("newborn", [True, False])
    def test_a_stay_of_two_dates_is_untouched(self, newborn: bool) -> None:
        """Control: 2 days, nothing billed (Kuvöz 2 x 440.98 for a newborn, 2 x 222.36 standard for an adult)."""
        report = _report(newborn=newborn, days=2)

        if newborn:
            [row] = report.yenidogan_yatak.opportunities
            assert (row["bed_code"], row["days"], row["same_day_stay"]) == ("510070", 2, False)
            assert row["expected_try"] == pytest.approx(881.96, abs=0.005)
        else:
            [row] = report.yatak_puani.opportunities
            assert (row["bed_code"], row["bed_days"], row["same_day_stay"]) == ("510010", 2, False)
            assert row["expected_yatak_try"] == pytest.approx(444.72, abs=0.005)

    @pytest.mark.parametrize("scope", ["patient", "bill"])
    @pytest.mark.parametrize("newborn", [True, False])
    def test_the_only_day_is_paid_by_510090_on_the_icu_claim_whose_last_day_it_is(self, scope: str, newborn: bool) -> None:
        ctx = _transfer_context(ward_end=date(2026, 7, 10), ward_newborn=newborn)
        if scope == "bill":
            ctx = ctx.slice_for_claim("CLM-WARD")
        report = compute_patient_billing_report("P1", claim_context=ctx, copay_exemption=_NOT_EXEMPT)

        [standard] = [o for o in report.yatak_puani.opportunities if o["claim_id"] == "CLM-WARD"]
        assert standard["bed_days"] == 0
        assert standard["expected_yatak_try"] == 0.0 and standard["recoverable_uplift_try"] == 0.0
        assert standard["icu_overlap_dates"] == ["2026-07-10"]
        newborn_rows = [o for o in report.yenidogan_yatak.opportunities if o["claim_id"] == "CLM-WARD"]
        if newborn:
            [row] = newborn_rows
            assert (row["days"], row["bed_code"], row["expected_try"]) == (0, "510120", 0.0)
            assert row["icu_overlap_dates"] == ["2026-07-10"]
        else:
            assert newborn_rows == []


class TestDayBedActionRow:
    """The action row of a stay priced at the day bed is its own kind, `yatak_puani_day_bed`, on both motors.

    The frontend titles a row that has no procedure code by its kind, and the kinds `yatak_puani_standard_bed` and
    `yenidogan_yatak` read "Standard bed-day charge" and "Newborn bed charge (510070 / 510081)": a title that names
    Kuvöz and Kot on a 44.45 TRY row whose detail starts "Gündüz yatak (510120)". Only the row's kind changes; the
    opportunity keeps its type, its keys and its money."""

    @pytest.mark.parametrize(
        ("newborn", "lines", "surface", "block_type", "recoverable"),
        [
            (False, (), "yatak_puani", "yatak_puani_standard_bed", 44.45),
            (False, (("510120", "20.00"),), "yatak_puani", "yatak_puani_standard_bed", 24.45),
            (True, (), "yenidogan_yatak", "yenidogan_yatak", 44.45),
            (True, (("510070", "20.00"),), "yenidogan_yatak", "yenidogan_yatak", 24.45),
        ],
        ids=["standard-nothing-billed", "standard-day-bed-in-part", "newborn-nothing-billed", "newborn-kuvoz-in-part"],
    )
    def test_a_row_priced_at_the_day_bed_has_the_day_bed_kind(
        self, newborn: bool, lines: tuple[tuple[str, str], ...], surface: str, block_type: str, recoverable: float
    ) -> None:
        report = _one_date_report(lines, newborn=newborn)

        [row] = _bed_rows(report)
        [opportunity] = (report.yenidogan_yatak if newborn else report.yatak_puani).opportunities
        assert (row["surface"], row["kind"]) == (surface, "yatak_puani_day_bed")
        assert row["detail"].startswith("Gündüz yatak (510120)")
        # Only the row's kind: the opportunity keeps its type and bed code, the row its amount and class.
        assert (opportunity["type"], opportunity["bed_code"]) == (block_type, "510120")
        assert row["sgk_uplift_try"] == pytest.approx(recoverable, abs=0.005)
        assert row["sgk_uplift_try"] == pytest.approx(opportunity["recoverable_uplift_try"], abs=0.005)
        assert row["finding_type"] == "opportunity"
        # No code and no name: the title is the kind label alone and no invoice line is highlighted.
        assert row["procedure_code"] is None and row["procedure_name"] is None

    @pytest.mark.parametrize(
        ("newborn", "surface", "kind"),
        [(False, "yatak_puani", "yatak_puani_standard_bed"), (True, "yenidogan_yatak", "yenidogan_yatak")],
    )
    def test_a_row_of_two_dates_keeps_its_kind(self, newborn: bool, surface: str, kind: str) -> None:
        [row] = _bed_rows(_report(newborn=newborn, days=2))

        assert (row["surface"], row["kind"]) == (surface, kind)
        assert not row["detail"].startswith("Gündüz yatak")

    @pytest.mark.parametrize("newborn", [True, False], ids=["newborn", "standard"])
    def test_the_api_payload_and_its_public_projection_serve_the_day_bed_kind(self, newborn: bool) -> None:
        """What the frontend receives: the row as the endpoint serializes it, and as the public projection keeps it."""
        import json

        from src.bilun.api.public_responses import project_public_response
        from src.bilun.api.routes.billing import _serialize_billing_report

        payload = json.loads(json.dumps(_serialize_billing_report(_one_date_report(newborn=newborn)), default=str))
        public = project_public_response(payload, "/api/billing-report/{patient_id}")

        for served in (payload, public):
            [row] = [a for a in served["recommended_actions"] if a["surface"] in ("yenidogan_yatak", "yatak_puani")]
            assert row["kind"] == "yatak_puani_day_bed"
            assert row["sgk_uplift_try"] == pytest.approx(44.45, abs=0.005)
            assert row["detail"].startswith("Gündüz yatak (510120)")


class TestReconcileDayBed:
    def test_the_sentence_names_the_day_bed_when_the_newborn_row_is_a_day_bed_stay(self) -> None:
        opp = _yatak_opportunity("C1", bed_days=1, rate=44.45)

        [adjusted] = reconcile_yatak_newborn_overlap(
            _yatak_review(opp), _newborn_review({"claim_id": "C1", "days": 1, "bed_code": "510120"})
        ).opportunities

        assert adjusted["bed_days"] == 0 and adjusted["expected_yatak_try"] == 0.0
        assert adjusted["newborn_overlap_days"] == 1
        assert "day bed (510120) on the newborn bed row" in adjusted["detail"]
        assert "510070 / 510081" not in adjusted["detail"]

    @pytest.mark.parametrize("newborn_row", [{"claim_id": "C1", "days": 3}, {"claim_id": "C1", "days": 3, "bed_code": "510070"}])
    def test_any_other_newborn_row_keeps_the_kuvoz_and_cot_sentence(self, newborn_row: dict[str, Any]) -> None:
        [adjusted] = reconcile_yatak_newborn_overlap(
            _yatak_review(_yatak_opportunity("C1")), _newborn_review(newborn_row)
        ).opportunities

        assert "510070 / 510081" in adjusted["detail"]
        assert "day bed (510120)" not in adjusted["detail"]


class TestReversedNewbornBedLine:
    def test_an_incubator_billed_reversed_and_rebilled_as_the_day_bed_leaves_nothing_on_both_motors(self) -> None:
        report = _one_date_report((("510070", "-440.98"), ("510120", "44.45")))

        [newborn] = report.yenidogan_yatak.opportunities
        assert (newborn["days"], newborn["standard_bed_days"]) == (0, 1)
        assert newborn["recoverable_uplift_try"] == 0.0
        [standard] = report.yatak_puani.opportunities
        assert standard["bed_days"] == 1 and "newborn_overlap_days" not in standard  # the standard-bed motor owns the day
        assert standard["actual_billed_try"] == pytest.approx(44.45, abs=0.005)
        assert standard["recoverable_uplift_try"] == 0.0
        assert report.sgk_uplift_try == 0.0
        assert _bed_rows(report) == []
