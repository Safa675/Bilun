"""Unit tests for structured billing recommended actions."""

from __future__ import annotations

import pytest

from src.bilun.domain.billing.billing_actions import collect_billing_actions, count_billing_actions
from src.bilun.domain.billing.patient_report import compute_patient_billing_report
from src.bilun.domain.billing.types import (
    BillingActionReport,
    BillingStrategyRecommendation,
    CopayOptimization,
    MaterialPreCheck,
)
from src.bilun.domain.claims.loader import load_sut_claim_dataset
from src.bilun.domain.claims.patient_context import (
    build_bill_claim_context,
    build_patient_claim_context,
)
from src.bilun.domain.sut.clause_reference import RULE_TYPE_COPAY_WAIVER

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def dataset():
    return load_sut_claim_dataset()


class TestBillingActionsBreakdown:
    def test_f015_includes_copay_review_and_documentation_checklist(self, dataset) -> None:
        claim_id = "F-SENTETIK-HASTA-0003-015"
        ctx = build_bill_claim_context("SENTETIK-HASTA-0003", claim_id, dataset)
        assert ctx is not None

        copay = {
            "exempt": True,
            "n_qualifying": 1,
            "qualifying_diagnoses": [
                {"code": "E03.9", "disease": "Endokrin", "range": "E00-E90"},
            ],
        }
        report = compute_patient_billing_report(
            "SENTETIK-HASTA-0003",
            claim_context=ctx,
            copay_exemption=copay,
        )

        assert report.action_count == len(report.recommended_actions)

        surfaces = {row["surface"] for row in report.recommended_actions}
        assert surfaces == {"copay", "claim_checklist", "billing_strategy"}

        violations = [
            row
            for row in report.recommended_actions
            if row["kind"] == "compliance_violation"
        ]
        # Post 2026-07-01 amendment + rule-wiring drift, procedure 613080 on this
        # claim is package-mandated (§2.2.1.B-1.a), so one compliance violation now
        # accompanies the copay review + documentation checklist.
        assert len(violations) == 1
        assert "613080" in (violations[0].get("detail") or "")

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

        doc_rows = [
            row
            for row in report.recommended_actions
            if row["surface"] == "claim_checklist"
            and row["kind"] == "documentation_requirement"
        ]
        assert len(doc_rows) == 3
        assert any("muayene" in (row.get("detail") or "").lower() for row in doc_rows)
        # Review item 3: the mandated-package comparison (#269) no longer needs the
        # synthetic package_candidate flag, so the claim gets its package gap row.
        gap_rows = [
            row for row in report.recommended_actions if row["kind"] == "mandatory_compliance"
        ]
        assert len(gap_rows) == 1
        assert report.action_count == (
            len(copay_rows) + len(violations) + len(doc_rows) + len(gap_rows)
        )

        checklist_docs = [
            item
            for item in report.claim_submission_checklist.items
            if item.get("checklist_kind") == "documentation_requirement"
        ]
        assert len(checklist_docs) == 3
        anchors = {item.get("sut_anchor") for item in checklist_docs}
        assert "Fatura İnceleme ORTAK-5" in anchors

    def test_f011_doc_checklist_is_relevance_gated(self, dataset) -> None:
        """Yatış + EK-2/C cerrahi claim should not spam ungated ORTAK/TPN rules."""
        claim_id = "F-SENTETIK-HASTA-0003-011"
        ctx = build_bill_claim_context("SENTETIK-HASTA-0003", claim_id, dataset)
        assert ctx is not None
        report = compute_patient_billing_report(
            "SENTETIK-HASTA-0003",
            claim_context=ctx,
            copay_exemption={"exempt": False, "n_qualifying": 0, "qualifying_diagnoses": []},
        )
        docs = [
            item
            for item in report.claim_submission_checklist.items
            if item.get("checklist_kind") == "documentation_requirement"
        ]
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

    def test_f011_includes_override_and_material_uplift(self, dataset) -> None:
        claim_id = "F-SENTETIK-HASTA-0003-011"
        ctx = build_bill_claim_context("SENTETIK-HASTA-0003", claim_id, dataset)
        assert ctx is not None

        report = compute_patient_billing_report(
            "SENTETIK-HASTA-0003",
            claim_context=ctx,
            copay_exemption={"exempt": False, "n_qualifying": 0, "qualifying_diagnoses": []},
        )

        assert report.exactness_status == "exact"
        assert report.action_count == len(report.recommended_actions)

        override = [
            row
            for row in report.recommended_actions
            if row.get("kind") == "optional_override"
        ]
        assert len(override) == 1
        assert override[0]["sgk_uplift_try"] == pytest.approx(4515.48)

        strategy_override = report.billing_strategy.optional_override_opportunities[0]
        # 600160 is primary by catalog points: 1800 + the hizmet başı §2.2.2.A(5)
        # 30 % of 600150's own 2200 (was the package 25 %: 2350.0, uplift 4625.48).
        assert strategy_override["itemized_total_try"] == pytest.approx(2460.0)
        assert strategy_override["package_total_try"] == pytest.approx(6975.48)
        assert strategy_override.get("recommended_package_code") == "609300"

        materials = [
            row for row in report.recommended_actions if row["surface"] == "material_uplift"
        ]
        assert len(materials) == 2
        assert all(row["material_code"] == "OR2640" for row in materials)

    def test_count_matches_collect(self, dataset) -> None:
        ctx = build_patient_claim_context("SENTETIK-HASTA-0003", dataset)
        report = compute_patient_billing_report(
            "SENTETIK-HASTA-0003",
            claim_context=ctx,
            copay_exemption={"exempt": False, "n_qualifying": 0, "qualifying_diagnoses": []},
        )
        assert count_billing_actions(report) == len(collect_billing_actions(report))


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
