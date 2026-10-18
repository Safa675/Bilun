"""The rows behind `audit_exposure_try` and the `audit_exposure` action rows made from them.

The exposure total and its rows come from the same unbundling findings, so the KPI the Compliance view shows
cannot drift from the list below it. Self-made findings cover the buckets that no showcase bill produces; the
showcase bill of S8 is in `test_showcase_fault_rows.py`. The arithmetic of the total itself is pinned by the
~40 exposure assertions of `test_showcase_session_and_package_gaps.py`.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from src.bilun.domain.billing.billing_actions import collect_billing_actions
from src.bilun.domain.billing.claim_audit_exposure import (
    AuditExposureReview,
    audit_exposure_rows,
    audit_exposure_total,
    compute_audit_exposure_from_claims,
    recommend_audit_exposure_from_claims,
    unbundling_findings_from_claims,
)
from src.bilun.domain.billing.patient_report import compute_patient_billing_report
from src.bilun.domain.billing.report_totals import finalize_report_totals
from src.bilun.domain.billing.types import BillingActionReport
from src.bilun.domain.claims.loader import load_sut_claim_dataset
from src.bilun.domain.claims.patient_context import build_bill_claim_context
from src.bilun.domain.prose_rules.drg_unbundling import ClaimUnbundlingFinding
from tests.fixtures import synthetic_cohort as cohort

pytestmark = pytest.mark.unit


def _finding(**buckets: list[dict]) -> ClaimUnbundlingFinding:
    return ClaimUnbundlingFinding(claim_id="CLM-EXP-1", chapter="K", **buckets)


_SESSION = {
    "procedure_line_id": "ISL-1",
    "procedure_code": "P603840",
    "procedure_name": "Second package",
    "risk_amount_try": 3584.8,
    "sut_section": "2.2.2.B.b",
    "rule_id": "2.2.2.B.b",
    "detail": "Secondary procedure billed at full rate.",
}
_BLOOD = {
    "procedure_line_id": "ISL-2",
    "procedure_code": "KAN-1",
    "procedure_name": "Blood component",
    "risk_amount_try": 120.25,
    "sut_section": "2.2.2.B-1.e",
    "rule_id": "blood_component_partial_bill",
    "detail": "Blood component may only be billed at a fraction of points.",
}
_BUNDLED = {
    "procedure_line_id": "ISL-3",
    "procedure_code": "P600001",
    "procedure_name": "Package-included line",
    "risk_amount_try": 40.0,
    "detail": "HEURISTIC — package-included flag on claim line; not verified against SUT §2.2 prose.",
}
_PAYMENT_METHOD = {
    "procedure_line_id": "ISL-4",
    "procedure_code": "610131",
    "procedure_name": "Itemized line of a mandated package",
    "risk_amount_try": 900.0,
    "sut_section": "2.2.2(1)",
    "rule_id": "payment_method_mandated_package",
    "detail": "Package mandated, billed hizmet başı.",
}


class TestAuditExposureRows:
    def test_each_bucket_with_risk_makes_one_row_in_bucket_order(self) -> None:
        finding = _finding(
            bundled_violations=[_BUNDLED],
            blood_component_violations=[_BLOOD],
            session_violations=[_SESSION],
        )

        rows = audit_exposure_rows([finding])

        assert [(row["kind"], row["risk_amount_try"]) for row in rows] == [
            ("session_point_violation", 3584.8),
            ("blood_component_partial_bill", 120.25),
            ("bundled_line_flag", 40.0),
        ]
        session_row = rows[0]
        assert session_row["claim_id"] == "CLM-EXP-1"
        assert session_row["procedure_line_id"] == "ISL-1"
        assert session_row["procedure_code"] == "P603840"
        assert session_row["procedure_name"] == "Second package"
        assert session_row["sut_section"] == "2.2.2.B.b"
        assert session_row["rule_id"] == "2.2.2.B.b"
        assert session_row["detail"] == "Secondary procedure billed at full rate."
        # A heuristic entry keeps its own words, and has no clause to cite.
        assert rows[2]["sut_section"] is None
        assert rows[2]["detail"].startswith("HEURISTIC")

    def test_entries_without_risk_make_no_row(self) -> None:
        finding = _finding(
            session_violations=[{**_SESSION, "risk_amount_try": 0.0}, {**_SESSION, "risk_amount_try": None}],
            blood_component_violations=[],
        )

        assert audit_exposure_rows([finding]) == []

    def test_payment_method_risk_counts_in_the_total_but_makes_no_row(self) -> None:
        """The same `mandated_package_gap` gives the bill its `billing_strategy` `compliance_violation`
        row; a second row would list one finding twice."""
        finding = _finding(
            payment_method_violations=[_PAYMENT_METHOD], session_violations=[_SESSION]
        )

        assert audit_exposure_total([finding]) == pytest.approx(3584.8 + 900.0)
        assert [row["kind"] for row in audit_exposure_rows([finding])] == ["session_point_violation"]

    def test_total_adds_every_bucket_of_every_claim(self) -> None:
        first = _finding(
            session_violations=[_SESSION],
            blood_component_violations=[_BLOOD],
            payment_method_violations=[_PAYMENT_METHOD],
            bundled_violations=[_BUNDLED],
        )
        second = replace(first, claim_id="CLM-EXP-2")

        assert audit_exposure_total([first, second]) == pytest.approx(2 * (3584.8 + 120.25 + 900.0 + 40.0))
        assert audit_exposure_total([]) == 0.0
        assert audit_exposure_rows([]) == []
        # Each claim keeps its own rows.
        assert [row["claim_id"] for row in audit_exposure_rows([first, second])] == [
            "CLM-EXP-1",
            "CLM-EXP-1",
            "CLM-EXP-1",
            "CLM-EXP-2",
            "CLM-EXP-2",
            "CLM-EXP-2",
        ]


class TestAuditExposureActions:
    def _report(self, *rows: dict) -> BillingActionReport:
        return BillingActionReport(patient_id="PT-EXP", audit_exposure_rows=list(rows))

    def test_a_report_without_rows_has_no_audit_exposure_action(self) -> None:
        assert collect_billing_actions(self._report()) == []

    def test_each_row_is_one_compliance_action_carrying_the_risk(self) -> None:
        rows = audit_exposure_rows(
            [
                _finding(
                    session_violations=[_SESSION],
                    blood_component_violations=[_BLOOD],
                    bundled_violations=[_BUNDLED],
                )
            ]
        )

        actions = collect_billing_actions(self._report(*rows))

        assert [action["surface"] for action in actions] == ["audit_exposure"] * 3
        assert [action["kind"] for action in actions] == [
            "session_point_violation",
            "blood_component_partial_bill",
            "bundled_line_flag",
        ]
        assert {action["finding_type"] for action in actions} == {"compliance"}
        assert [action["audit_risk_try"] for action in actions] == [3584.8, 120.25, 40.0]
        # What is at risk is the billed money over the allowed amount: it is also the billed-at-risk amount.
        assert [action["billed_try"] for action in actions] == [3584.8, 120.25, 40.0]
        # Over-billing risk is never SGK revenue.
        assert {action["sgk_uplift_try"] for action in actions} == {None}
        assert {action["compliance_savings_try"] for action in actions} == {None}
        assert len({action["action_id"] for action in actions}) == 3
        assert [action["sut_section_id"] for action in actions] == ["2.2.2.B.b", "2.2.2.B-1.e", None]
        assert actions[0]["procedure_code"] == "P603840"
        assert actions[0]["procedure_name"] == "Second package"
        assert actions[0]["claim_id"] == "CLM-EXP-1"
        assert actions[0]["detail"] == "Secondary procedure billed at full rate."

    def test_two_entries_of_one_bucket_are_told_apart_by_their_line(self) -> None:
        """Two over-billed secondaries of one session are two rows of one kind; the line id in the action
        id is what keeps them apart (the list renders by it)."""
        second = {
            **_SESSION,
            "procedure_line_id": "ISL-9",
            "procedure_code": "P603841",
            "risk_amount_try": 410.0,
        }
        rows = audit_exposure_rows([_finding(session_violations=[_SESSION, second])])

        actions = collect_billing_actions(self._report(*rows))

        assert [action["kind"] for action in actions] == ["session_point_violation"] * 2
        assert [action["audit_risk_try"] for action in actions] == [3584.8, 410.0]
        assert len({action["action_id"] for action in actions}) == 2
        assert "ISL-1" in actions[0]["action_id"]
        assert "ISL-9" in actions[1]["action_id"]

    def test_one_line_in_two_buckets_keeps_two_distinct_actions(self) -> None:
        rows = audit_exposure_rows(
            [
                _finding(
                    session_violations=[_SESSION],
                    bundled_violations=[{**_BUNDLED, "procedure_line_id": "ISL-1"}],
                )
            ]
        )

        actions = collect_billing_actions(self._report(*rows))

        assert len({action["action_id"] for action in actions}) == 2


class TestReportAssembly:
    @staticmethod
    def _s8_context():
        dataset = load_sut_claim_dataset()
        role = cohort.role("showcase_S8")
        ctx = build_bill_claim_context(role.patient_id, role.claim_id, dataset)
        assert ctx is not None
        return ctx

    def test_the_review_is_the_total_and_the_rows_of_one_pass(self) -> None:
        ctx = self._s8_context()

        review = recommend_audit_exposure_from_claims(ctx)

        findings = unbundling_findings_from_claims(ctx)
        assert review.total_try == audit_exposure_total(findings)
        assert review.total_try == compute_audit_exposure_from_claims(ctx)
        assert review.rows == audit_exposure_rows(findings)
        assert len(review.rows) == 1

    def test_the_report_carries_the_rows_and_the_unchanged_total(self) -> None:
        ctx = self._s8_context()

        report = compute_patient_billing_report(ctx.patient_id, claim_context=ctx)

        assert report.audit_exposure_rows == recommend_audit_exposure_from_claims(ctx).rows
        assert report.audit_exposure_try == compute_audit_exposure_from_claims(ctx)
        assert [row["surface"] for row in report.recommended_actions].count("audit_exposure") == 1

    def test_finalize_uses_the_review_it_is_given(self) -> None:
        """The report assembly does one unbundling pass: a total handed in is the total, not a second pass."""
        ctx = self._s8_context()
        report = BillingActionReport(patient_id=ctx.patient_id)

        finalize_report_totals(report, claim_context=ctx, audit_exposure=AuditExposureReview(total_try=123.45))

        assert report.audit_exposure_try == 123.45

    def test_finalize_takes_the_total_from_the_review_or_computes_it(self) -> None:
        ctx = self._s8_context()
        review = recommend_audit_exposure_from_claims(ctx)

        with_review = BillingActionReport(patient_id=ctx.patient_id)
        finalize_report_totals(with_review, claim_context=ctx, audit_exposure=review)
        computed = BillingActionReport(patient_id=ctx.patient_id)
        finalize_report_totals(computed, claim_context=ctx)

        assert with_review.audit_exposure_try == computed.audit_exposure_try == review.total_try
        # The finalizer only sets totals: the rows are the report assembly's.
        assert with_review.audit_exposure_rows == computed.audit_exposure_rows == []

    def test_without_procedure_lines_there_is_no_exposure_and_no_row(self) -> None:
        ctx = self._s8_context()
        no_lines = replace(ctx, procedure_lines=())

        report = compute_patient_billing_report(no_lines.patient_id, claim_context=no_lines)
        assert report.audit_exposure_try == 0.0
        assert report.audit_exposure_rows == []
        assert not [row for row in report.recommended_actions if row["surface"] == "audit_exposure"]

        bare = BillingActionReport(patient_id="PT-EXP")
        finalize_report_totals(bare, claim_context=None)
        assert bare.audit_exposure_try == 0.0
        assert recommend_audit_exposure_from_claims(no_lines).rows == []
        assert recommend_audit_exposure_from_claims(no_lines).total_try == 0.0


class TestPaymentMethodBucket:
    """The payment-method bucket counts in `audit_exposure_try` but makes no audit row, because the bill's
    `billing_strategy` `compliance_violation` row is the finding (SUT 2.2.2.(1): the package is mandated).
    That row carries no amount: the money of this bucket is in the KPI only. The premise is pinned on the
    committed S1 bill (a package billed itemized) with one 20,000 TL drug line added in memory, so that the
    itemized lines overstate the package."""

    @staticmethod
    def _overbilled_s1_context():
        dataset = load_sut_claim_dataset()
        role = cohort.role("showcase_S1")
        ctx = build_bill_claim_context(role.patient_id, role.claim_id, dataset)
        assert ctx is not None
        template = ctx.drug_lines[0]
        expensive = replace(
            template,
            drug_claim_line_id=f"{template.drug_claim_line_id}-EXTRA",
            billed_amount_try=Decimal("20000.00"),
            expected_payable_try=Decimal("20000.00"),
        )
        return replace(ctx, drug_lines=(*ctx.drug_lines, expensive))

    def test_the_bucket_money_is_in_the_kpi_and_named_by_the_strategy_row_only(self) -> None:
        ctx = self._overbilled_s1_context()

        report = compute_patient_billing_report(ctx.patient_id, claim_context=ctx)

        findings = unbundling_findings_from_claims(ctx)
        entries = [
            (finding.claim_id, entry)
            for finding in findings
            for entry in finding.payment_method_violations
            if entry["risk_amount_try"] > 0
        ]
        assert entries, "the premise: the payment-method bucket carries money on this bill"
        assert report.audit_exposure_try == pytest.approx(
            sum(entry["risk_amount_try"] for _, entry in entries)
        )
        # No audit row for it ...
        assert report.audit_exposure_rows == []
        assert not [row for row in report.recommended_actions if row["surface"] == "audit_exposure"]
        # ... because the strategy row names the finding: one per entry (same claim, same code), no money.
        violations = [
            row
            for row in report.recommended_actions
            if row["surface"] == "billing_strategy" and row["kind"] == "compliance_violation"
        ]
        for claim_id, entry in entries:
            assert any(
                row["claim_id"] == claim_id and row["procedure_code"] == entry["procedure_code"]
                for row in violations
            ), entry
        assert {row["audit_risk_try"] for row in violations} == {None}
        assert {row["sgk_uplift_try"] for row in violations} == {None}
