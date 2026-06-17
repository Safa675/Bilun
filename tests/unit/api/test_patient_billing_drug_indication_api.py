"""API serialization tests for §4.2 drug indication on patient billing reports."""

from __future__ import annotations

import pytest

from src.bilun.api.routes.billing import _serialize_billing_report
from src.bilun.api.schemas import BillingReportResponse
from src.bilun.domain.billing.orchestrator import compute_patient_billing_report
from src.bilun.domain.claims import build_patient_claim_context, load_sut_claim_dataset

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def dataset():
    return load_sut_claim_dataset()


class TestPatientBillingDrugIndicationApi:
    def test_0014_billing_json_surfaces_drug_indication_violations(self, dataset) -> None:
        patient_id = "SENTETIK-HASTA-0014"
        ctx = build_patient_claim_context(patient_id, dataset)
        assert ctx is not None

        report = compute_patient_billing_report(patient_id, claim_context=ctx)
        payload = _serialize_billing_report(report)
        model = BillingReportResponse.model_validate(payload)

        assert model.drug_indication_violation_count == 1
        assert model.drug_indication.violation_count == 1
        assert model.drug_indication.violations[0]["violation_kind"] == "missing_board_report"
        assert model.drug_indication.coverage_scope.get("pilot_rule_count", 0) >= 131
        assert model.drug_indication.coverage_scope.get("v1_stop_conditions")

    def test_0019_billing_json_surfaces_tier_b_duration_mismatch(self, dataset) -> None:
        patient_id = "SENTETIK-HASTA-0019"
        ctx = build_patient_claim_context(patient_id, dataset)
        assert ctx is not None

        report = compute_patient_billing_report(patient_id, claim_context=ctx)
        payload = _serialize_billing_report(report)
        model = BillingReportResponse.model_validate(payload)

        assert model.drug_indication_violation_count == 1
        assert model.drug_indication.violations[0]["violation_kind"] == "report_duration_mismatch"

    def test_0017_billing_json_has_zero_drug_indication_violations(self, dataset) -> None:
        patient_id = "SENTETIK-HASTA-0017"
        ctx = build_patient_claim_context(patient_id, dataset)
        assert ctx is not None

        report = compute_patient_billing_report(patient_id, claim_context=ctx)
        payload = _serialize_billing_report(report)
        model = BillingReportResponse.model_validate(payload)

        assert model.drug_indication_violation_count == 0
        assert model.drug_indication.violation_count == 0
