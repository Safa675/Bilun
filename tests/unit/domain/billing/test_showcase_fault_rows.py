"""The action rows of the three showcase faults that used to show their money only in a KPI.

S3 (anaesthesia points missing) adds to `sgk_uplift_try`; S8 (second package at full rate) adds to
`audit_exposure_try`; S4 (companion bed not billed) is a 0 TL check row, since no 510121 line shows the companion
(#301). Each bill must carry one action row for its fault, in the view that fits the money, and the rows must add
up to the report's components. The bills are the showcase bills of the
demo cohort, read through the registry (`tests/fixtures/synthetic_cohort.py`): a role name and the registry's
fault record, never an id or an amount typed here.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from scripts.synthetic.cohort import KNOWN_REPORT_DIVERGENCES
from src.bilun.domain.billing.billing_actions import collect_billing_actions
from src.bilun.domain.billing.block_registry import BILLING_BLOCK_SPECS
from src.bilun.domain.billing.claim_audit_exposure import (
    audit_exposure_total,
    unbundling_findings_from_claims,
)
from src.bilun.domain.billing.patient_report import compute_patient_billing_report
from src.bilun.domain.billing.types import (
    AnesteziPuaniReview,
    BillingActionReport,
    RefakatciReview,
)
from src.bilun.domain.claims.loader import load_sut_claim_dataset
from src.bilun.domain.claims.patient_context import PatientClaimContext, build_bill_claim_context
from tests.fixtures import synthetic_cohort as cohort

pytestmark = pytest.mark.unit

_NOT_EXEMPT = {"exempt": False, "n_qualifying": 0, "qualifying_diagnoses": []}
_STORIES = tuple(f"S{number}" for number in range(1, 9))
_CENT = Decimal("0.01")


@pytest.fixture(scope="module")
def dataset():
    return load_sut_claim_dataset()


def _context(dataset, story: str) -> PatientClaimContext:
    role = cohort.role(f"showcase_{story}")
    ctx = build_bill_claim_context(role.patient_id, role.claim_id, dataset)
    assert ctx is not None
    assert [claim.claim_id for claim in ctx.claims] == [role.claim_id]
    return ctx


@pytest.fixture(scope="module")
def reports(dataset) -> dict[str, BillingActionReport]:
    """The report of each showcase bill, computed once (not-exempt copay: no copay review row)."""
    out: dict[str, BillingActionReport] = {}
    for story in _STORIES:
        ctx = _context(dataset, story)
        out[story] = compute_patient_billing_report(
            ctx.patient_id, claim_context=ctx, copay_exemption=_NOT_EXEMPT
        )
    return out


def _rows(report: BillingActionReport, surface: str) -> list[dict[str, Any]]:
    return [row for row in report.recommended_actions if row["surface"] == surface]


def _try(value: object) -> Decimal:
    assert value is not None, "the report carries no amount here"
    return Decimal(str(value)).quantize(_CENT)


def _sum_try(values: list[object]) -> Decimal:
    return sum((_try(value) for value in values), Decimal("0.00"))


class TestRevenueRowsOfTheFaultStories:
    def test_s3_missing_anaesthesia_is_one_revenue_row_with_the_registry_amount(
        self, dataset, reports
    ) -> None:
        fault = cohort.fault("S3")
        report = reports["S3"]

        [row] = _rows(report, "anestezi_puani")
        assert row["finding_type"] == "opportunity"
        assert row["claim_id"] == fault["claim_id"]
        assert _try(row["sgk_uplift_try"]) == Decimal(fault["amount_try"])
        # Revenue money only: nothing is filed as a risk, a saving or a billed-at-risk amount.
        assert row["audit_risk_try"] is None
        assert row["compliance_savings_try"] is None
        assert row["billed_try"] is None

        # The row says which surgery asks for the anaesthesia group and which clause it comes from.
        [opportunity] = report.anestezi_puani.opportunities
        assert row["kind"] == opportunity["type"]
        assert row["procedure_code"] == opportunity["procedure_code"]
        # The code is a surgery the bill carries; the anaesthesia group it asks for is not on the bill.
        billed_codes = {line.procedure_code for line in _context(dataset, "S3").procedure_lines}
        assert row["procedure_code"] in billed_codes
        assert opportunity["anestezi_code"] not in billed_codes
        assert row["sut_section_id"] == opportunity["sut_section_id"]
        assert row["detail"] == opportunity["detail"]
        assert opportunity["anestezi_code"] in row["detail"]

        # The headline counts exactly this amount.
        assert _try(report.sgk_uplift_try) == Decimal(fault["amount_try"])
        assert _try(report.anestezi_puani.confirmed_anestezi_try) == Decimal(fault["amount_try"])

    def test_s4_companion_not_billed_is_one_0_tl_check_row_that_names_the_registry_amount(
        self, reports
    ) -> None:
        """#301: SUT §2.6.3.(2) pays the companion on the doctor's order and the refakatçi belgesi, and no 510121
        line shows either, so the row asks for them and names what the nights would bill, outside the money."""
        fault = cohort.fault("S4")
        report = reports["S4"]
        assert KNOWN_REPORT_DIVERGENCES["S4"].record_amount_try == fault["amount_try"]

        [row] = _rows(report, "refakatci")
        assert row["finding_type"] == "opportunity"
        assert row["claim_id"] == fault["claim_id"]
        assert _try(row["sgk_uplift_try"]) == Decimal("0.00")
        assert row["audit_risk_try"] is None
        assert row["compliance_savings_try"] is None
        assert row["billed_try"] is None

        [opportunity] = report.refakatci.opportunities
        assert row["kind"] == opportunity["type"]
        assert row["sut_section_id"] == opportunity["sut_section_id"]
        assert row["detail"] == opportunity["detail"]
        assert row["detail"].startswith("Kontrol et:")
        assert f"= {fault['amount_try']} TRY" in row["detail"]

        assert report.sgk_uplift_try == 0.0
        assert report.refakatci.confirmed_refakat_try == 0.0

    @pytest.mark.parametrize("story", ["S3", "S4"])
    def test_revenue_row_is_listed_for_the_revenue_view(self, reports, story: str) -> None:
        """The Revenue view lists `opportunity` rows; the Compliance view lists `compliance` rows."""
        report = reports[story]
        kinds = {row["finding_type"] for row in report.recommended_actions}
        assert "opportunity" in kinds
        assert "compliance" not in kinds


class TestAuditExposureRowOfS8:
    def test_s8_second_package_is_one_compliance_row_with_the_report_amount(
        self, dataset, reports
    ) -> None:
        fault = cohort.fault("S8")
        report = reports["S8"]

        [row] = _rows(report, "audit_exposure")
        assert row["finding_type"] == "compliance"
        assert row["kind"] == "session_point_violation"
        assert row["claim_id"] == fault["claim_id"]
        # Over-billing risk is not revenue: no SGK uplift, and the headline stays at 0.
        assert row["sgk_uplift_try"] is None
        assert report.sgk_uplift_try == 0.0
        assert report.total_recoverable_try == 0.0

        # The row carries what the report counts (`audit_exposure_try`), no number moved.
        assert _try(row["audit_risk_try"]) == _try(report.audit_exposure_try)
        assert _try(row["billed_try"]) == _try(report.audit_exposure_try)
        divergence = KNOWN_REPORT_DIVERGENCES["S8"]
        assert _try(row["audit_risk_try"]) == Decimal(divergence.report_amount_try)

        # The registry records the same-incision reading (SUT §2.2.2.B.(3)(a), 25%): the row's amount is
        # the separate-incision reading (b, 50%) and the detail states the rest in TRY.
        assert _try(row["audit_risk_try"]) < Decimal(fault["amount_try"])
        ctx = _context(dataset, "S8")
        [finding] = unbundling_findings_from_claims(ctx)
        [violation] = finding.session_violations
        strict_part = _try(violation["review_risk_try"])
        assert _try(row["audit_risk_try"]) + strict_part == Decimal(fault["amount_try"])
        assert str(strict_part) in row["detail"]
        assert Decimal(divergence.record_amount_try) == Decimal(fault["amount_try"])

        # The row names the secondary package and the clause of the reading it uses.
        assert row["procedure_code"] == violation["procedure_code"]
        assert row["procedure_name"] == violation["procedure_name"]
        assert row["sut_section_id"] == violation["sut_section"]
        assert row["detail"] == violation["detail"]

    def test_other_bills_have_no_audit_exposure_row(self, reports) -> None:
        for story, report in reports.items():
            if story != "S8":
                assert _rows(report, "audit_exposure") == [], story
                assert report.audit_exposure_rows == [], story

    def test_rows_and_total_come_from_the_same_findings(self, dataset, reports) -> None:
        """`audit_exposure_try` is unchanged arithmetic over the same findings the rows are made from:
        the rows plus the payment-method bucket (explained by the strategy row) add up to it."""
        for story in _STORIES:
            report = reports[story]
            ctx = _context(dataset, story)
            findings = unbundling_findings_from_claims(ctx)
            assert _try(audit_exposure_total(findings)) == _try(report.audit_exposure_try), story

            payment_method = sum(
                (
                    _try(entry["risk_amount_try"])
                    for finding in findings
                    for entry in finding.payment_method_violations
                ),
                Decimal("0.00"),
            )
            row_total = _sum_try([row["risk_amount_try"] for row in report.audit_exposure_rows])
            assert row_total + payment_method == _try(report.audit_exposure_try), story
            assert _sum_try(
                [row["audit_risk_try"] for row in _rows(report, "audit_exposure")]
            ) == row_total, story


class TestRowsAddUpToTheComponents:
    # surface of the action rows -> the report's component of `sgk_uplift_try` that the rows must add up to
    _COMPONENTS = {
        "billing_strategy": lambda r: r.billing_strategy.uplift_savings_try,
        "session_uplift": lambda r: r.session_uplift.confirmed_uplift_try,
        "drg_uplift": lambda r: r.drg_uplift.confirmed_uplift_try,
        "blood_uplift": lambda r: r.blood_uplift.confirmed_uplift_try,
        "yatak_puani": lambda r: r.yatak_puani.confirmed_yatak_try,
        "anestezi_puani": lambda r: r.anestezi_puani.confirmed_anestezi_try,
        "refakatci": lambda r: r.refakatci.confirmed_refakat_try,
        "material_uplift": lambda r: r.material_uplift.confirmed_uplift_try,
        "procedure_addon_uplift": lambda r: r.procedure_addon_uplift.confirmed_uplift_try,
    }

    @pytest.mark.parametrize("story", _STORIES)
    def test_each_component_equals_the_sum_of_its_rows(self, reports, story: str) -> None:
        report = reports[story]
        for surface, component in self._COMPONENTS.items():
            rows = _rows(report, surface)
            assert _sum_try([row["sgk_uplift_try"] or 0.0 for row in rows]) == _try(
                component(report)
            ), (story, surface)

    @pytest.mark.parametrize("story", _STORIES)
    def test_sgk_uplift_is_the_sum_of_the_rows_money(self, reports, story: str) -> None:
        """On the eight showcase bills every SGK row except the capture gap (own scalar,
        `capture_gap_try`) is a counted component: the rows add up to the headline."""
        report = reports[story]
        counted = [
            row["sgk_uplift_try"]
            for row in report.recommended_actions
            if row["sgk_uplift_try"] is not None and row["surface"] != "procedure_capture_gap"
        ]
        assert _sum_try(counted) == _try(report.sgk_uplift_try)

    @pytest.mark.parametrize("story", ["S1", "S2", "S3"])  # S4's row is a 0 TL check (#301).
    def test_revenue_story_is_explained_by_its_rows_alone(self, reports, story: str) -> None:
        fault = cohort.fault(story)
        assert fault["effect_kind"] == "revenue_uplift"
        report = reports[story]
        assert _sum_try(
            [row["sgk_uplift_try"] for row in report.recommended_actions if row["sgk_uplift_try"]]
        ) == Decimal(fault["amount_try"])
        assert _try(report.sgk_uplift_try) == Decimal(fault["amount_try"])


class TestPuanRowsAreOnlyForMoneyThatCounts:
    """The cohort's zero-amount and suppressed puan opportunities, and self-made ones."""

    def test_zero_and_suppressed_companion_opportunities_on_the_cohort_make_no_row(
        self, reports
    ) -> None:
        for story, report in reports.items():
            if story == "S4":
                continue
            assert _rows(report, "refakatci") == [], story
            assert all(
                float(opp["recoverable_uplift_try"]) == 0.0 for opp in report.refakatci.opportunities
            ), story
        # The premise: the cohort does have companion opportunities of 0 TL (days already billed,
        # package-window bundling), so the empty row lists above are not vacuous.
        assert any(reports[story].refakatci.opportunities for story in ("S1", "S2", "S5", "S6", "S8"))

    def test_only_opportunities_that_add_to_the_sgk_total_make_a_row(self) -> None:
        def opportunity(amount: float, *, included: bool = True, **extra: Any) -> dict[str, Any]:
            return {
                "type": "anestezi_puani_group",
                "claim_id": "CLM-PUAN",
                "procedure_code": "615931",
                "recoverable_uplift_try": amount,
                "included_in_sgk_total": included,
                "sut_section_id": "2.2.2.A",
                "detail": f"detail {amount}",
                **extra,
            }

        report = BillingActionReport(
            patient_id="PT-PUAN",
            anestezi_puani=AnesteziPuaniReview(
                opportunities=[
                    opportunity(0.0),  # already billed in full
                    opportunity(250.0, included=False),  # kept out of the SGK headline
                    opportunity(300.0),
                    opportunity(125.5),
                ]
            ),
            refakatci=RefakatciReview(
                opportunities=[
                    {
                        "type": "refakatci_companion_bed",
                        "claim_id": "CLM-PUAN",
                        "recoverable_uplift_try": 0.0,
                        "included_in_sgk_total": False,
                        "sut_section_id": "2.6.3",
                        "detail": "suppressed",
                        "suppression_notes": ["day_case_suppressed (§2.2.2.(5))"],
                    },
                    {
                        "type": "refakatci_companion_bed",
                        "claim_id": "CLM-PUAN",
                        "recoverable_uplift_try": 74.1,
                        "included_in_sgk_total": True,
                        "sut_section_id": "2.6.3",
                        "detail": "1 night",
                        "suppression_notes": ["Verify the stay certificate."],
                    },
                ]
            ),
        )

        actions = collect_billing_actions(report)
        assert [(row["surface"], row["sgk_uplift_try"]) for row in actions] == [
            ("anestezi_puani", 300.0),
            ("anestezi_puani", 125.5),
            ("refakatci", 74.1),
        ]
        assert [row["finding_type"] for row in actions] == ["opportunity"] * 3
        # Ids follow the position in the block, so a skipped opportunity does not renumber the others.
        assert [row["action_id"] for row in actions] == [
            "anestezi_puani:CLM-PUAN:2",
            "anestezi_puani:CLM-PUAN:3",
            "refakatci:CLM-PUAN:1",
        ]
        # The rows add up to the components the headline is made of.
        assert _sum_try([row["sgk_uplift_try"] for row in actions[:2]]) == _try(
            report.anestezi_puani.confirmed_anestezi_try
        )
        assert _try(actions[2]["sgk_uplift_try"]) == _try(report.refakatci.confirmed_refakat_try)
        assert actions[2]["detail"] == "1 night Verify the stay certificate."
        assert actions[0]["detail"] == "detail 300.0"


    def test_an_opportunity_without_a_recoverable_amount_falls_back_to_its_expected_amount(self) -> None:
        """`confirmed_*_try` reads `expected_try` when `recoverable_uplift_try` is absent; so does the row."""
        report = BillingActionReport(
            patient_id="PT-PUAN",
            anestezi_puani=AnesteziPuaniReview(
                opportunities=[
                    {
                        "type": "anestezi_puani_group",
                        "claim_id": "CLM-PUAN",
                        "expected_try": 40.0,
                        "included_in_sgk_total": True,
                    }
                ]
            ),
            refakatci=RefakatciReview(
                opportunities=[
                    {
                        "type": "refakatci_companion_bed",
                        "claim_id": "CLM-PUAN",
                        "recoverable_uplift_try": None,
                        "expected_try": 25.5,
                    }
                ]
            ),
        )

        actions = collect_billing_actions(report)

        assert [(row["surface"], row["sgk_uplift_try"]) for row in actions] == [
            ("anestezi_puani", 40.0),
            ("refakatci", 25.5),
        ]
        assert _try(actions[0]["sgk_uplift_try"]) == _try(report.anestezi_puani.confirmed_anestezi_try)
        assert _try(actions[1]["sgk_uplift_try"]) == _try(report.refakatci.confirmed_refakat_try)


# Blocks that feed `sgk_uplift_try` through `uplift_field` but make no action row on purpose: a named, decided
# gap, listed together with its reason. The list is empty since the newborn bed motor got rows (its amount nets
# the billed 510070/510081 lines, leaves ICU stays to the ICU motor and shares no day with the standard bed;
# tasks/todo.md, "Newborn bed motor"). A new motor that is added to `BILLING_BLOCK_SPECS` without rows fails
# this guard.
_AGGREGATE_ONLY_BLOCKS: frozenset[str] = frozenset()


def _block_with_one_positive_opportunity(attr: str) -> BillingActionReport:
    report = BillingActionReport(patient_id="PT-GUARD")
    block = getattr(report, attr)
    if attr == "billing_strategy":
        block.recommendations = [
            {
                "claim_id": "CLM-GUARD",
                "type": "mandatory_compliance",
                "recommendation_kind": "mandatory_compliance",
                "procedure_code": "609300",
                "savings_try": 10.0,
                "included_in_sgk_total": True,
            }
        ]
    else:
        block.opportunities = [
            {
                "type": f"{attr}_guard",
                "claim_id": "CLM-GUARD",
                "recoverable_uplift_try": 10.0,
                "expected_try": 10.0,
                "expected_yatak_try": 10.0,
                "total_try": 10.0,
                "included_in_sgk_total": True,
            }
        ]
    return report


def test_every_block_that_feeds_the_sgk_headline_has_action_rows_or_is_on_the_named_list() -> None:
    feeding = [spec.attr for spec in BILLING_BLOCK_SPECS if spec.uplift_field]
    assert {"anestezi_puani", "refakatci", "yatak_puani", "billing_strategy"} <= set(feeding)

    without_rows = {
        attr
        for attr in feeding
        if attr
        not in {
            row["surface"]
            for row in collect_billing_actions(_block_with_one_positive_opportunity(attr))
        }
    }
    assert without_rows == _AGGREGATE_ONLY_BLOCKS, (
        f"blocks that feed sgk_uplift_try with no action row: {sorted(without_rows)}; give a new motor rows "
        "in collect_billing_actions, or name it in _AGGREGATE_ONLY_BLOCKS together with the reason"
    )
