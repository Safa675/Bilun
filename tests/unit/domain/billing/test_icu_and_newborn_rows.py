"""Action rows for the ICU motor, and why the newborn bed motor still has none.

`icu_puani` feeds `sgk_uplift_try` through `confirmed_icu_try` (the expected 510090 + P55200x charge minus
the ICU lines already billed). Its rows must add up to that component: a row exists only for money the
headline counts. `yenidogan_yatak` feeds the headline too but its amount is not netted against the billed
newborn bed lines, so surfacing it would tell a billing officer to recover what was already billed: it stays
on the named aggregate-only list until the engine is fixed. No showcase story exercises either motor, so
the bills are built in memory (amounts are read from the engine's own opportunity, never typed here).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from itertools import product
from typing import Any

import pytest

from src.bilun.domain.billing.billing_actions import collect_billing_actions
from src.bilun.domain.billing.patient_report import compute_patient_billing_report
from src.bilun.domain.billing.types import (
    AnesteziPuaniReview,
    BillingActionReport,
    IcuPuaniReview,
    RefakatciReview,
)
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.icu_puani import detect_icu_tier_overbilling
from tests.unit.domain.billing.test_blood_uplift_wiring import _claim, _proc

pytestmark = pytest.mark.unit

_NOT_EXEMPT = {"exempt": False, "n_qualifying": 0, "qualifying_diagnoses": []}
_CENT = Decimal("0.01")


def _try(value: object) -> Decimal:
    assert value is not None
    return Decimal(str(value)).quantize(_CENT)


def _sum_try(values: list[object]) -> Decimal:
    return sum((_try(value) for value in values), Decimal("0.00"))


def _rows(report: BillingActionReport, surface: str) -> list[dict[str, Any]]:
    return [row for row in report.recommended_actions if row["surface"] == surface]


def _icu_claim(claim_id: str = "CLM-ICU") -> Any:
    return _claim(
        claim_id=claim_id,
        department="yoğun bakım",
        primary_icd10="J96.0",
        admission_date=date(2026, 7, 10),
        discharge_date=date(2026, 7, 14),
        claim_start_date=date(2026, 7, 10),
        claim_end_date=date(2026, 7, 14),
    )


def _icu_lines(
    claim_id: str = "CLM-ICU", *, day_rate_billed: str = "100", package_billed: str = "500"
) -> list[Any]:
    """First and last ICU day (510090) around three days of the 3rd-level package (P552003)."""
    return [
        _proc(procedure_line_id=f"{claim_id}-D1", claim_id=claim_id, procedure_code="510090",
              procedure_name="Yoğun bakım", billed_amount_try=Decimal(day_rate_billed),
              procedure_date=date(2026, 7, 10)),
        _proc(procedure_line_id=f"{claim_id}-P3", claim_id=claim_id, procedure_code="P552003",
              procedure_name="Yoğun bakım 3. basamak", quantity=3, billed_amount_try=Decimal(package_billed),
              procedure_date=date(2026, 7, 11)),
        _proc(procedure_line_id=f"{claim_id}-D2", claim_id=claim_id, procedure_code="510090",
              procedure_name="Yoğun bakım", billed_amount_try=Decimal(day_rate_billed),
              procedure_date=date(2026, 7, 14)),
    ]


def _icu_report(*, day_rate_billed: str = "100", package_billed: str = "500") -> BillingActionReport:
    ctx = PatientClaimContext(
        patient_id="P1", claims=(_icu_claim(),), material_lines=(), drug_lines=(), diagnoses=(),
        procedure_lines=tuple(_icu_lines(day_rate_billed=day_rate_billed, package_billed=package_billed)),
    )
    return compute_patient_billing_report("P1", claim_context=ctx, copay_exemption=_NOT_EXEMPT)


class TestIcuRows:
    def test_a_partly_billed_stay_gets_one_revenue_row_with_the_unbilled_remainder(self) -> None:
        report = _icu_report()

        [opportunity] = report.icu_puani.opportunities
        [row] = _rows(report, "icu_puani")
        billed = _sum_try([100, 500, 100])
        assert _try(opportunity["actual_billed_try"]) == billed
        remainder = _try(opportunity["total_try"]) - billed
        assert remainder > 0

        assert row["finding_type"] == "opportunity"
        assert row["kind"] == opportunity["type"] == "icu_puani_yogun_bakim"
        assert row["claim_id"] == opportunity["claim_id"]
        assert row["sut_section_id"] == opportunity["sut_section_id"] == "2.4.4.H"
        assert _try(row["sgk_uplift_try"]) == _try(opportunity["recoverable_uplift_try"]) == remainder
        # Revenue money only: nothing is filed as a risk, a saving or a billed-at-risk amount, and the row
        # spans 510090 and P55200x lines, so it points at no single procedure.
        assert row["audit_risk_try"] is None
        assert row["compliance_savings_try"] is None
        assert row["billed_try"] is None
        assert row["procedure_code"] is None

        # The detail states the full expected charge; the row says what the billed lines leave of it.
        assert row["detail"].startswith(opportunity["detail"])
        assert f"{billed} TRY" in row["detail"]
        assert "unbilled remainder" in row["detail"]

        # The headline counts exactly the rows' money, and the ICU component is this row.
        assert _try(report.icu_puani.confirmed_icu_try) == remainder
        counted = [
            action["sgk_uplift_try"]
            for action in report.recommended_actions
            if action["sgk_uplift_try"] is not None
        ]
        assert _sum_try(counted) == _try(report.sgk_uplift_try)

    def test_a_stay_with_nothing_billed_keeps_the_engine_detail(self) -> None:
        report = _icu_report(day_rate_billed="0", package_billed="0")
        [opportunity] = report.icu_puani.opportunities
        [row] = _rows(report, "icu_puani")
        assert opportunity["actual_billed_try"] == 0
        assert _try(row["sgk_uplift_try"]) == _try(opportunity["total_try"])
        assert row["detail"] == opportunity["detail"]

    def test_an_opportunity_without_a_detail_gets_none_invented(self) -> None:
        opportunity = {
            "type": "icu_puani_yogun_bakim",
            "claim_id": "CLM-X",
            "recoverable_uplift_try": 50.0,
            "actual_billed_try": 10.0,
        }
        report = BillingActionReport(patient_id="P1", icu_puani=IcuPuaniReview(opportunities=[opportunity]))
        [row] = collect_billing_actions(report)
        assert row["detail"] is None
        assert _try(row["sgk_uplift_try"]) == _try(report.icu_puani.confirmed_icu_try)

    def test_a_stay_billed_in_full_makes_no_row(self) -> None:
        """The motor nets the billed ICU lines (#13); a stay that is billed in full has nothing to recover."""
        expected = _icu_report().icu_puani.opportunities[0]["total_try"]
        report = _icu_report(package_billed=str(Decimal(str(expected)) + 1))

        [opportunity] = report.icu_puani.opportunities
        assert opportunity["recoverable_uplift_try"] == 0.0
        assert report.icu_puani.confirmed_icu_try == 0.0
        assert _rows(report, "icu_puani") == []

    def test_two_icu_claims_get_two_rows_that_add_up_to_the_component(self) -> None:
        claims = (_icu_claim("CLM-ICU-A"), _icu_claim("CLM-ICU-B"))
        lines = _icu_lines("CLM-ICU-A") + _icu_lines("CLM-ICU-B", package_billed="900")
        ctx = PatientClaimContext(
            patient_id="P1", claims=claims, procedure_lines=tuple(lines), material_lines=(),
            drug_lines=(), diagnoses=(),
        )
        report = compute_patient_billing_report("P1", claim_context=ctx, copay_exemption=_NOT_EXEMPT)

        rows = _rows(report, "icu_puani")
        assert [row["claim_id"] for row in rows] == ["CLM-ICU-A", "CLM-ICU-B"]
        assert len({row["action_id"] for row in rows}) == 2
        assert _sum_try([row["sgk_uplift_try"] for row in rows]) == _try(report.icu_puani.confirmed_icu_try)
        assert _try(rows[0]["sgk_uplift_try"]) > _try(rows[1]["sgk_uplift_try"])  # B billed 400 TL more

    def test_the_tier_overbilling_review_is_not_an_uplift_row(self) -> None:
        """`detect_icu_tier_overbilling` (P552003 without a support line) is an audit review row with
        `included_in_sgk_total` False and no money; it must never become an uplift row."""
        claim, lines = _icu_claim(), _icu_lines()
        [tier] = detect_icu_tier_overbilling([claim], lines)
        assert tier["type"] == "icu_tier_overbilling"
        assert tier["included_in_sgk_total"] is False
        assert tier["at_risk_try"] == 0.0

        # In the pipeline the review goes to the claim-audit violations, not into the ICU block.
        report = _icu_report()
        assert {row["type"] for row in report.icu_puani.opportunities} == {"icu_puani_yogun_bakim"}

        # And if a review row ever lands in the block, it makes no row and does not move the sum.
        [opportunity] = report.icu_puani.opportunities
        mixed = BillingActionReport(
            patient_id="P1", icu_puani=IcuPuaniReview(opportunities=[tier, opportunity, tier])
        )
        [row] = [r for r in collect_billing_actions(mixed) if r["surface"] == "icu_puani"]
        assert row["action_id"] == "icu_puani:CLM-ICU:1"  # the position in the block, not renumbered
        assert _try(row["sgk_uplift_try"]) == _try(mixed.icu_puani.confirmed_icu_try)
        review_only = BillingActionReport(patient_id="P1", icu_puani=IcuPuaniReview(opportunities=[tier]))
        assert collect_billing_actions(review_only) == []


_MISSING = object()
# surface -> (block, the field its component reads without `recoverable_uplift_try`, the other puan field, the component)
_COUNTED_BLOCKS = {
    "icu_puani": (IcuPuaniReview, "total_try", "expected_try", "confirmed_icu_try"),
    "anestezi_puani": (AnesteziPuaniReview, "expected_try", "total_try", "confirmed_anestezi_try"),
    "refakatci": (RefakatciReview, "expected_try", "total_try", "confirmed_refakat_try"),
}


def _opportunity(recoverable: object, fallback: object, included: object, fallback_field: str, other_field: str):
    row: dict[str, Any] = {"type": "x", "claim_id": "CLM-X", other_field: 77.7}  # the field it must NOT read
    for key, value in (("recoverable_uplift_try", recoverable), (fallback_field, fallback),
                       ("included_in_sgk_total", included)):
        if value is not _MISSING:
            row[key] = value
    return row


@pytest.mark.parametrize("surface", sorted(_COUNTED_BLOCKS))
def test_rows_add_up_to_the_blocks_component_for_every_field_combination(surface: str) -> None:
    block_type, fallback_field, other_field, component = _COUNTED_BLOCKS[surface]
    # `included_in_sgk_total` is read by truthiness in the components (`row.get(..., True)`): None and 0 leave
    # the headline, 1 stays in; the rows must follow.
    combinations = list(
        product(
            [_MISSING, None, 0.0, 125.5],
            [_MISSING, 0.0, 300.0],
            [_MISSING, True, False, None, 0, 1],
        )
    )
    every_row = []
    for recoverable, fallback, included in combinations:
        row = _opportunity(recoverable, fallback, included, fallback_field, other_field)
        every_row.append(row)
        report = BillingActionReport(patient_id="P1", **{surface: block_type(opportunities=[row])})
        rows = [r for r in collect_billing_actions(report) if r["surface"] == surface]
        assert _sum_try([r["sgk_uplift_try"] for r in rows]) == _try(getattr(getattr(report, surface), component)), (
            recoverable, fallback, included,
        )
        assert len(rows) <= 1
    # All of them in one block: no cross-talk between opportunities.
    report = BillingActionReport(patient_id="P1", **{surface: block_type(opportunities=every_row)})
    rows = [r for r in collect_billing_actions(report) if r["surface"] == surface]
    assert rows, "the combinations include counted money"
    assert _sum_try([r["sgk_uplift_try"] for r in rows]) == _try(getattr(getattr(report, surface), component))


def _newborn_report(*, bed_billed: str | None) -> BillingActionReport:
    claim = _claim(
        claim_id="CLM-NB", department="yenidoğan", primary_icd10="Z38.0",
        admission_date=date(2026, 7, 10), discharge_date=date(2026, 7, 12),
        claim_start_date=date(2026, 7, 10), claim_end_date=date(2026, 7, 12),
    )
    lines = [_proc(procedure_line_id="NB-EXAM", claim_id="CLM-NB", procedure_code="520010",
                   procedure_name="Muayene", billed_amount_try=Decimal("10"),
                   procedure_date=date(2026, 7, 10))]
    if bed_billed is not None:
        lines.append(_proc(procedure_line_id="NB-BED", claim_id="CLM-NB", procedure_code="510070",
                           procedure_name="Kuvöz", quantity=3, billed_amount_try=Decimal(bed_billed),
                           procedure_date=date(2026, 7, 10)))
    ctx = PatientClaimContext(
        patient_id="P1", claims=(claim,), procedure_lines=tuple(lines), material_lines=(),
        drug_lines=(), diagnoses=(),
    )
    return compute_patient_billing_report("P1", claim_context=ctx, copay_exemption=_NOT_EXEMPT)


class TestNewbornBedStaysAggregateOnly:
    def test_an_unbilled_newborn_stay_is_counted_in_the_headline_but_has_no_row(self) -> None:
        """The control of the defect below: the motor works on an unbilled stay, and surfaces no row."""
        report = _newborn_report(bed_billed=None)
        [opportunity] = report.yenidogan_yatak.opportunities
        assert opportunity["days"] == 3
        assert _try(report.yenidogan_yatak.confirmed_yenidogan_yatak_try) == _try(opportunity["expected_try"]) > 0
        assert _rows(report, "yenidogan_yatak") == []

    @pytest.mark.xfail(
        strict=True,
        raises=AssertionError,
        reason=(
            "The newborn bed motor sets recoverable_uplift_try = expected_try and never nets the billed "
            "510070/510081 lines (the ICU and standard-bed motors do, #13). Fix the amount, then remove this "
            "marker, give the block rows in collect_billing_actions and take it off _AGGREGATE_ONLY_BLOCKS."
        ),
    )
    def test_a_newborn_bed_billed_in_full_leaves_nothing_recoverable(self) -> None:
        expected = _newborn_report(bed_billed=None).yenidogan_yatak.opportunities[0]["expected_try"]
        report = _newborn_report(bed_billed=str(Decimal(str(expected))))
        assert report.yenidogan_yatak.confirmed_yenidogan_yatak_try == 0.0
