"""Unit tests for structured billing recommended actions."""

from __future__ import annotations

import pytest

from src.bilun.domain.billing.billing_actions import collect_billing_actions, count_billing_actions
from src.bilun.domain.billing.patient_report import compute_patient_billing_report
from src.bilun.domain.billing.types import BillingActionReport, MaterialPreCheck
from src.bilun.domain.claims.loader import load_sut_claim_dataset
from src.bilun.domain.claims.patient_context import (
    build_bill_claim_context,
    build_patient_claim_context,
)

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
        assert surfaces == {"copay", "claim_checklist"}

        violations = [
            row
            for row in report.recommended_actions
            if row["kind"] == "compliance_violation"
        ]
        assert len(violations) == 0

        copay_rows = [row for row in report.recommended_actions if row["surface"] == "copay"]
        assert len(copay_rows) == 1
        assert copay_rows[0]["kind"] == "exemption_review"

        doc_rows = [
            row
            for row in report.recommended_actions
            if row["surface"] == "claim_checklist"
            and row["kind"] == "documentation_requirement"
        ]
        assert len(doc_rows) == 1
        assert "muayene" in (doc_rows[0].get("detail") or "").lower()
        assert report.action_count == 1 + len(doc_rows)

        checklist_docs = [
            item
            for item in report.claim_submission_checklist.items
            if item.get("checklist_kind") == "documentation_requirement"
        ]
        assert len(checklist_docs) == 1
        assert checklist_docs[0].get("sut_anchor") == "Fatura İnceleme ORTAK-5"

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
        assert override[0]["sgk_uplift_try"] == pytest.approx(6300.0)

        strategy_override = report.billing_strategy.optional_override_opportunities[0]
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
