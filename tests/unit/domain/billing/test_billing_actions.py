"""Unit tests for structured billing recommended actions."""

from __future__ import annotations

import pytest

from src.bilun.domain.billing.billing_actions import collect_billing_actions, count_billing_actions
from src.bilun.domain.billing.patient_report import compute_patient_billing_report
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
    def test_f015_includes_three_violations_and_copay_review(self, dataset) -> None:
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
            chapters={"E"},
        )

        assert report.action_count == len(report.recommended_actions)
        assert report.action_count == 4

        surfaces = {row["surface"] for row in report.recommended_actions}
        assert surfaces == {"billing_strategy", "copay"}

        violations = [
            row
            for row in report.recommended_actions
            if row["kind"] == "compliance_violation"
        ]
        assert len(violations) == 3
        assert {row["procedure_code"] for row in violations} == {
            "608870",
            "603791",
            "609111",
        }

        copay_rows = [row for row in report.recommended_actions if row["surface"] == "copay"]
        assert len(copay_rows) == 1
        assert copay_rows[0]["kind"] == "exemption_review"

    def test_f011_includes_override_and_material_uplift(self, dataset) -> None:
        claim_id = "F-SENTETIK-HASTA-0003-011"
        ctx = build_bill_claim_context("SENTETIK-HASTA-0003", claim_id, dataset)
        assert ctx is not None

        report = compute_patient_billing_report(
            "SENTETIK-HASTA-0003",
            claim_context=ctx,
            copay_exemption={"exempt": False, "n_qualifying": 0, "qualifying_diagnoses": []},
            chapters={"I"},
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
            chapters={"I"},
        )
        assert count_billing_actions(report) == len(collect_billing_actions(report))
