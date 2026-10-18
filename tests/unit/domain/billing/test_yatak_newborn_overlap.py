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
) -> PatientClaimContext:
    """One inpatient claim of `days` inclusive days; a newborn one (Z38.0, yenidoğan) or an adult one."""
    end = _START + timedelta(days=days - 1)
    claim = _claim(
        claim_id="CLM-STAY",
        department="yenidoğan" if newborn else "kardiyoloji",
        primary_icd10="Z38.0" if newborn else "I10",
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
                           procedure_name="bed", quantity=days, billed_amount_try=Decimal(bed_billed),
                           procedure_date=_START))
    if standard_bed_billed is not None:
        lines.append(_proc(procedure_line_id="STD-BED", claim_id="CLM-STAY", procedure_code="510010",
                           procedure_name="Standart yatak", quantity=days,
                           billed_amount_try=Decimal(standard_bed_billed), procedure_date=_START))
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

    def test_a_standard_bed_line_billed_on_a_newborn_stay_is_not_a_newborn_bed_line(self) -> None:
        """510010 billed beside nothing else: the newborn motor still expects the newborn bed (its own code
        family); the standard bed motor expects no day. Flagging the 510010 line as double billing is a
        separate audit-exposure detector (not built; tasks/todo.md)."""
        report = _report(newborn=True, standard_bed_billed="667.08")

        [newborn] = report.yenidogan_yatak.opportunities
        assert newborn["actual_billed_try"] == 0.0
        assert newborn["recoverable_uplift_try"] == pytest.approx(1322.94, abs=0.005)
        assert report.yatak_puani.confirmed_yatak_try == 0.0


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
