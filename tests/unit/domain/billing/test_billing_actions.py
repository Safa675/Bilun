"""Unit tests for structured billing recommended actions.

The bill-level tests read the showcase bills of the demo cohort through the registry
(`tests/fixtures/synthetic_cohort.py`): a role name and the registry's fault record, never an id or an
amount typed here.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Any

import pytest

from src.bilun.domain.billing.billing_actions import collect_billing_actions, count_billing_actions
from src.bilun.domain.billing.patient_report import compute_patient_billing_report
from src.bilun.domain.billing.types import (
    BillingActionReport,
    BillingStrategyRecommendation,
    CopayOptimization,
    MaterialPreCheck,
    MaterialUplift,
)
from src.bilun.domain.claims.loader import load_sut_claim_dataset
from src.bilun.domain.claims.patient_context import (
    PatientClaimContext,
    build_bill_claim_context,
    build_patient_claim_context,
)
from src.bilun.domain.sut.clause_reference import RULE_TYPE_COPAY_WAIVER
from tests.fixtures import synthetic_cohort as cohort

pytestmark = pytest.mark.unit

_NOT_EXEMPT = {"exempt": False, "n_qualifying": 0, "qualifying_diagnoses": []}
_EXEMPT = {
    "exempt": True,
    "n_qualifying": 1,
    "qualifying_diagnoses": [{"code": "E03.9", "disease": "Endokrin", "range": "E00-E90"}],
}


@pytest.fixture(scope="module")
def dataset():
    return load_sut_claim_dataset()


def _showcase_context(dataset, role_name: str) -> PatientClaimContext:
    """The claim context of the one showcase bill that `role_name` names in the registry."""
    role = cohort.role(role_name)
    ctx = build_bill_claim_context(role.patient_id, role.claim_id, dataset)
    assert ctx is not None
    assert [claim.claim_id for claim in ctx.claims] == [role.claim_id]
    return ctx


def _report(ctx: PatientClaimContext, copay_exemption: dict[str, Any]) -> BillingActionReport:
    return compute_patient_billing_report(
        ctx.patient_id, claim_context=ctx, copay_exemption=copay_exemption
    )


def _documentation_actions(report: BillingActionReport) -> list[dict[str, Any]]:
    return [
        row
        for row in report.recommended_actions
        if row["surface"] == "claim_checklist" and row["kind"] == "documentation_requirement"
    ]


def _documentation_items(report: BillingActionReport) -> list[dict[str, Any]]:
    return [
        item
        for item in report.claim_submission_checklist.items
        if item.get("checklist_kind") == "documentation_requirement"
    ]


def _try(value: object) -> Decimal:
    """A report amount as a two-decimal `Decimal`, comparable with the registry's decimal strings."""
    assert value is not None, "the report carries no amount here"
    return Decimal(str(value)).quantize(Decimal("0.01"))


class TestBillingActionsBreakdown:
    def test_companion_bill_gets_its_fault_row_the_copay_review_and_the_documentation_checklist(
        self, dataset
    ) -> None:
        """S4 (companion not billed) has no strategy, material or drug row: its fault row (the companion
        bed it did not bill), the exemption input and the documentation checklist are what reaches
        `recommended_actions`. No 510121 line shows a companion, so the fault row is a 0 TL "Kontrol et"
        row that names the nights' amount and adds nothing to the SGK total (#301)."""
        fault = cohort.fault("S4")
        ctx = _showcase_context(dataset, "showcase_S4")
        report = _report(ctx, _EXEMPT)

        assert report.action_count == len(report.recommended_actions)

        surfaces = {row["surface"] for row in report.recommended_actions}
        assert surfaces == {"copay", "refakatci", "claim_checklist"}
        [companion_row] = [row for row in report.recommended_actions if row["surface"] == "refakatci"]
        assert _try(companion_row["sgk_uplift_try"]) == Decimal("0.00")
        assert companion_row["detail"].startswith("Kontrol et:")
        assert f"= {fault['amount_try']} TRY" in companion_row["detail"]
        assert report.refakatci.confirmed_refakat_try == 0.0

        # The procedures of this bill carry no mandated package: no compliance violation and no
        # package gap row (the S1 bill below is the one that has them).
        violations = [
            row for row in report.recommended_actions if row["kind"] == "compliance_violation"
        ]
        assert violations == []
        gap_rows = [
            row for row in report.recommended_actions if row["kind"] == "mandatory_compliance"
        ]
        assert gap_rows == []

        copay_rows = [row for row in report.recommended_actions if row["surface"] == "copay"]
        assert len(copay_rows) == 1
        copay_row = copay_rows[0]
        assert copay_row["kind"] == "exemption_review"
        assert copay_row["finding_type"] == "opportunity"
        clause_ref = copay_row["clause_ref"]
        assert clause_ref is not None
        assert clause_ref["rule_type"] == RULE_TYPE_COPAY_WAIVER
        # Canonical dot-form coordinate — never the legacy "1.8.5(7)" string.
        coordinate = clause_ref["clause_coordinate"]
        assert coordinate != "1.8.5(7)"
        assert "(" not in coordinate or ".(" in coordinate
        assert copay_row["sut_section_id"] == coordinate

        doc_rows = _documentation_actions(report)
        checklist_docs = _documentation_items(report)
        assert doc_rows
        assert len(doc_rows) == len(checklist_docs)
        assert report.action_count == len(copay_rows) + 1 + len(doc_rows)
        refs = {item.get("fatura_inceleme_ref") for item in checklist_docs}
        # An inpatient stay: the detailed discharge summary (ORTAK-27), not the visit rule (ORTAK-5).
        assert "ORTAK-27" in refs
        assert "ORTAK-5" not in refs
        anchors = {item.get("sut_anchor") for item in checklist_docs}
        assert "Fatura İnceleme ORTAK-27" in anchors

    def test_outpatient_variant_of_the_same_bill_gets_the_visit_documentation(
        self, dataset
    ) -> None:
        """No bill of the cohort is an outpatient visit: the S4 bill is re-billed as `poliklinik` in
        memory, which is all ORTAK-5 (`is_outpatient_polyclinic`) looks at."""
        ctx = _showcase_context(dataset, "showcase_S4")
        outpatient = replace(ctx, claims=(replace(ctx.claims[0], claim_type="poliklinik"),))
        report = _report(outpatient, _EXEMPT)

        assert report.action_count == len(report.recommended_actions)
        assert {row["surface"] for row in report.recommended_actions} == {
            "copay",
            "claim_checklist",
        }
        checklist_docs = _documentation_items(report)
        refs = {item.get("fatura_inceleme_ref") for item in checklist_docs}
        assert "ORTAK-5" in refs
        assert "ORTAK-27" not in refs
        assert "Fatura İnceleme ORTAK-5" in {item.get("sut_anchor") for item in checklist_docs}
        assert len(_documentation_actions(report)) == len(checklist_docs)

    def test_documentation_checklist_is_relevance_gated(self, dataset) -> None:
        """An inpatient EK-2/C orthopaedic bill (S5, the hemiarthroplasty package) should not spam
        ungated ORTAK/TPN rules."""
        ctx = _showcase_context(dataset, "showcase_S5")
        claim = ctx.claims[0]
        # The premise of the assertions below, so that a rebuilt cohort fails here and not silently.
        assert claim.claim_type == "yatis"
        assert "ortopedi" in claim.department.lower()
        assert any(line.procedure_category == "paket" for line in ctx.procedure_lines)

        report = _report(ctx, _NOT_EXEMPT)
        docs = _documentation_items(report)
        refs = {item.get("fatura_inceleme_ref") for item in docs}
        assert "ORTAK-24" not in refs
        assert "ORTAK-5" not in refs
        assert "ORTAK-17" in refs  # EK-2/C present
        assert "ORTAK-27" in refs  # yatis
        assert "ORTOPEDİ-6" in refs
        for item in docs:
            anchor = item.get("sut_anchor") or ""
            assert anchor.startswith("Fatura İnceleme ")
            assert "F000" not in anchor and "C000" not in anchor

    def test_package_gap_of_s1_reaches_the_actions_with_the_registry_amount(self, dataset) -> None:
        """S1 bills a package itemised: one violation row (no money) and one package-gap row that
        carries the amount the registry's injection record proved."""
        fault = cohort.fault("S1")
        ctx = _showcase_context(dataset, "showcase_S1")
        report = _report(ctx, _NOT_EXEMPT)

        assert report.action_count == len(report.recommended_actions)
        strategy_rows = [
            row for row in report.recommended_actions if row["surface"] == "billing_strategy"
        ]
        assert sorted(row["kind"] for row in strategy_rows) == [
            "compliance_violation",
            "mandatory_compliance",
        ]
        by_kind = {row["kind"]: row for row in strategy_rows}
        assert by_kind["compliance_violation"]["sgk_uplift_try"] is None
        gap_row = by_kind["mandatory_compliance"]
        assert gap_row["finding_type"] == "compliance"
        assert gap_row["claim_id"] == fault["claim_id"]
        assert _try(gap_row["sgk_uplift_try"]) == Decimal(fault["amount_try"])

        gap = next(
            rec
            for rec in report.billing_strategy.recommendations
            if rec.get("recommendation_kind") == "mandatory_compliance"
        )
        assert gap["current_billing"] == "itemized"
        assert gap["recommendation"] == "package"
        assert gap_row["procedure_code"] == gap["recommended_package_code"]
        # The package is what the clean bill carries, the itemised lines are what the faulty bill carries.
        assert _try(gap["package_total_try"]) == Decimal(fault["billed_clean_try"])
        assert _try(gap["itemized_total_try"]) == Decimal(fault["billed_faulty_try"])
        assert _try(gap["savings_try"]) == Decimal(fault["amount_try"])
        assert gap["included_in_sgk_total"] is True
        assert _try(report.sgk_uplift_try) == Decimal(fault["amount_try"])

    def test_count_matches_collect(self, dataset) -> None:
        patient_id = cohort.role("default_landing").patient_id
        ctx = build_patient_claim_context(patient_id, dataset)
        assert ctx is not None
        report = _report(ctx, _NOT_EXEMPT)
        assert count_billing_actions(report) == len(collect_billing_actions(report))
        assert count_billing_actions(report) > 0


class TestUpliftActionRows:
    """Strategy and uplift rows that no showcase bill produces, from self-made reports."""

    def test_optional_override_row_is_an_opportunity_that_carries_the_savings(self) -> None:
        def report(*, included: bool) -> BillingActionReport:
            return BillingActionReport(
                patient_id="PT-OVERRIDE",
                billing_strategy=BillingStrategyRecommendation(
                    recommendations=[
                        {
                            "claim_id": "CLM-OVR-1",
                            "recommendation": "package",
                            "recommendation_kind": "optional_override",
                            "payment_method_kind": "DRG_OVERRIDABLE",
                            "recommended_package_code": "609300",
                            "savings_try": 4075.48,
                            "package_total_try": 6975.48,
                            "itemized_total_try": 2900.0,
                            "current_billing": "itemized",
                            "included_in_sgk_total": included,
                        }
                    ]
                ),
            )

        [row] = collect_billing_actions(report(included=True))
        assert row["surface"] == "billing_strategy"
        assert row["kind"] == "optional_override"
        assert row["finding_type"] == "opportunity"
        assert row["claim_id"] == "CLM-OVR-1"
        assert row["procedure_code"] == "609300"
        assert row["sgk_uplift_try"] == pytest.approx(4075.48)

        # An override that the headline does not count carries no SGK uplift.
        [uncounted] = collect_billing_actions(report(included=False))
        assert uncounted["kind"] == "optional_override"
        assert uncounted["sgk_uplift_try"] is None

    def test_each_material_uplift_opportunity_is_one_opportunity_row(self) -> None:
        report = BillingActionReport(
            patient_id="PT-MAT-UPLIFT",
            material_uplift=MaterialUplift(
                opportunities=[
                    {
                        "claim_id": "CLM-MU-1",
                        "material_code": "OR2640",
                        "material_name": "Implant A",
                        "recoverable_uplift_try": 1250.5,
                    },
                    {
                        "claim_id": "CLM-MU-1",
                        "material_code": "OR2640",
                        "material_name": "Implant A",
                        "recoverable_uplift_try": 800.0,
                    },
                ]
            ),
        )

        actions = collect_billing_actions(report)
        assert [row["surface"] for row in actions] == ["material_uplift", "material_uplift"]
        assert all(row["material_code"] == "OR2640" for row in actions)
        assert all(row["claim_id"] == "CLM-MU-1" for row in actions)
        assert all(row["finding_type"] == "opportunity" for row in actions)
        assert [row["sgk_uplift_try"] for row in actions] == [1250.5, 800.0]
        assert len({row["action_id"] for row in actions}) == 2


class TestMaterialRecommendedActions:
    def test_material_pre_auth_maps_note_price_and_sut_section(self) -> None:
        report = BillingActionReport(
            patient_id="PT-MAT",
            materials=MaterialPreCheck(
                pre_auth_required=[
                    {
                        "claim_id": "F-1",
                        "sut_code": "OP1198",
                        "material_name": "Ortez",
                        "price_try": 1250.0,
                        "note": "EK-3C-1 — pre-auth required",
                        "sut_section_id": "3.1.2",
                    }
                ]
            ),
        )

        actions = collect_billing_actions(report)
        assert len(actions) == 1
        row = actions[0]
        assert row["surface"] == "materials"
        assert row["kind"] == "material_pre_auth"
        assert row["material_code"] == "OP1198"
        assert row["material_name"] == "Ortez"
        assert row["billed_try"] == pytest.approx(1250.0)
        assert row["detail"] == "EK-3C-1 — pre-auth required"
        assert row["sut_section_id"] == "3.1.2"
        assert row["sgk_uplift_try"] is None

    def test_material_kind_fallback_sut_section_when_row_missing(self) -> None:
        report = BillingActionReport(
            patient_id="PT-MAT",
            materials=MaterialPreCheck(
                bundled_separate_billing=[
                    {
                        "sut_code": "EK3B99",
                        "material_name": "Screw",
                        "price_try": 99.0,
                        "note": "Bundled billed separately",
                    }
                ]
            ),
        )

        row = collect_billing_actions(report)[0]
        assert row["kind"] == "material_bundling"
        assert row["sut_section_id"] == "EK-3B-1"
        assert row["billed_try"] == pytest.approx(99.0)


class TestCopayExemptionActionRows:
    """Reason-specific copay exemption rows (EK-1/A, EK-4/D, acil, fallback)."""

    @staticmethod
    def _copay_actions(report: BillingActionReport) -> list[dict]:
        return [row for row in collect_billing_actions(report) if row["surface"] == "copay"]

    def test_ek4d_row_emitted_without_is_exempt(self) -> None:
        report = BillingActionReport(
            patient_id="PT-COPAY",
            copay=CopayOptimization(
                is_exempt=False,
                rx_copay_savings_by_ground={"ek4d_drug": 12.0},
            ),
        )

        rows = self._copay_actions(report)
        assert len(rows) == 1
        row = rows[0]
        assert row["action_id"] == "copay:ek4d_exemption_review"
        assert row["kind"] == "exemption_review"
        assert row["finding_type"] == "opportunity"
        assert row["sut_section_id"] == "1.8.2.(3)"
        assert row["clause_ref"]["clause_coordinate"] == "1.8.2.(3)"
        assert row["clause_ref"]["annex"] == "EK-4/D"
        assert row["clause_ref"]["rule_type"] == RULE_TYPE_COPAY_WAIVER
        assert row["compliance_savings_try"] is None

    def test_acil_servis_category_row(self) -> None:
        report = BillingActionReport(
            patient_id="PT-COPAY",
            copay=CopayOptimization(
                is_exempt=True,
                exemption_disease="Akut miyokard enfarktüsü",
                exemption_sources=[
                    {
                        "category": "acil_servis",
                        "rule_source": "SUT §1.8.5 acil servis muafiyeti",
                        "counts_toward_exempt": True,
                        "waives_sections": ("1.8.1",),
                        "evidence": {},
                    }
                ],
                patient_copay_waived_total_try=150.0,
            ),
        )

        rows = self._copay_actions(report)
        assert len(rows) == 1
        row = rows[0]
        assert row["action_id"] == "copay:acil_servis_exemption_review"
        assert row["sut_section_id"] == "1.8.5"
        assert row["clause_ref"]["clause_coordinate"] == "1.8.5"
        assert row["detail"] == "Akut miyokard enfarktüsü"
        assert row["compliance_savings_try"] == pytest.approx(150.0)

    def test_money_lands_only_on_primary_row(self) -> None:
        report = BillingActionReport(
            patient_id="PT-COPAY",
            copay=CopayOptimization(
                is_exempt=True,
                exemption_disease="KOAH",
                exemption_sources=[
                    {
                        "category": "acil_servis",
                        "rule_source": "SUT §1.8.5 acil servis muafiyeti",
                        "counts_toward_exempt": True,
                        "waives_sections": ("1.8.1",),
                        "evidence": {},
                    },
                    {
                        "category": "ek1a_chronic",
                        "rule_source": "SUT §1.8.5(7) + EK-1/A",
                        "counts_toward_exempt": True,
                        "waives_sections": ("1.8.1",),
                        "evidence": {},
                    },
                ],
                primary_exemption_category="ek1a_chronic",
                patient_copay_waived_total_try=240.0,
            ),
        )

        rows = self._copay_actions(report)
        assert [row["action_id"] for row in rows] == [
            "copay:acil_servis_exemption_review",
            "copay:ek1a_exemption_review",
        ]
        assert rows[0]["compliance_savings_try"] is None
        assert rows[1]["compliance_savings_try"] == pytest.approx(240.0)
        assert rows[1]["clause_ref"]["clause_coordinate"] == "1.8.5.(7)"
        assert rows[1]["clause_ref"]["annex"] == "EK-1/A"

    def test_fallback_row_when_is_exempt_without_sources(self) -> None:
        report = BillingActionReport(
            patient_id="PT-COPAY",
            copay=CopayOptimization(
                is_exempt=True,
                patient_copay_waived_total_try=80.0,
            ),
        )

        rows = self._copay_actions(report)
        assert len(rows) == 1
        row = rows[0]
        assert row["action_id"] == "copay:exemption_review"
        assert row["sut_section_id"] == "1.8.5"
        assert row["clause_ref"]["clause_coordinate"] == "1.8.5"
        assert row["finding_type"] == "opportunity"
        assert row["compliance_savings_try"] == pytest.approx(80.0)


class TestBillingStrategyCompliantClaimFiltering:
    def test_already_compliant_package_claim_is_excluded_from_recommended_actions(self) -> None:
        """Claims already billed correctly as package per SUT §2.2.2(1) with 0 savings
        should not be emitted into recommended_actions as false 'compliance risks'.
        """
        report = BillingActionReport(
            patient_id="PT-STRATEGY",
            billing_strategy=BillingStrategyRecommendation(
                recommendations=[
                    {
                        "claim_id": "CLM-OK-1",
                        "recommendation": "package",
                        "recommendation_kind": "mandatory_compliance",
                        "payment_method_kind": "DRG_MANDATORY",
                        "savings_try": 0.0,
                        "package_total_try": 47197.95,
                        "itemized_total_try": 35000.0,
                        "current_billing": "package",
                        "detail": "Claim CLM-OK-1 is billed correctly as package per SUT §2.2.2(1).",
                        "message_code": "claim_package_ok",
                        "message_params": {"claim_id": "CLM-OK-1", "amount_try": 47197.95},
                    },
                    {
                        "claim_id": "CLM-VIOLATION-1",
                        "recommendation": "package",
                        "recommendation_kind": "mandatory_compliance",
                        "payment_method_kind": "DRG_MANDATORY",
                        "savings_try": 12000.0,
                        "package_total_try": 47197.95,
                        "itemized_total_try": 35000.0,
                        "current_billing": "itemized",
                        "detail": "SUT §2.2 mandates package billing for claim CLM-VIOLATION-1.",
                        "message_code": "claim_mandate_package",
                        "message_params": {"claim_id": "CLM-VIOLATION-1"},
                    },
                ]
            ),
        )

        actions = collect_billing_actions(report)
        assert len(actions) == 1
        assert actions[0]["claim_id"] == "CLM-VIOLATION-1"
        assert actions[0]["kind"] == "mandatory_compliance"
        assert actions[0]["finding_type"] == "compliance"
        assert actions[0]["sgk_uplift_try"] == 12000.0

    def test_already_compliant_itemized_claim_is_excluded_from_recommended_actions(self) -> None:
        """Claims already billed correctly as itemized with 0 savings should also be excluded."""
        report = BillingActionReport(
            patient_id="PT-STRATEGY-2",
            billing_strategy=BillingStrategyRecommendation(
                recommendations=[
                    {
                        "claim_id": "CLM-ITEM-OK",
                        "recommendation": "itemized",
                        "recommendation_kind": "mandatory_compliance",
                        "payment_method_kind": "ITEMIZED",
                        "savings_try": 0.0,
                        "current_billing": "itemized",
                        "detail": "Claim CLM-ITEM-OK is billed correctly as itemized per SUT §2.2.",
                        "message_code": "claim_itemized_ok",
                    },
                ]
            ),
        )

        actions = collect_billing_actions(report)
        assert len(actions) == 0
