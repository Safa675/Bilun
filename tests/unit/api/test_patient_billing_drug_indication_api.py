"""API serialization tests for §4.2 drug indication on patient billing reports.

The former SUT-DEMO cohort patients (0014/0017/0019) were purged, so these tests
exercise the API serialization path against an in-memory claim context rather than
the synthetic cohort. Domain-level engine coverage lives in
``test_claim_drug_indication.py``.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.bilun.api.routes.billing import _serialize_billing_report
from src.bilun.api.routes.validation import validate_claim_legacy_endpoint
from src.bilun.api.schemas import (
    BillingReportResponse,
    DrugIndicationReviewResponse,
    ValidateClaimResponse,
)
from src.bilun.cache.build_streaming import json_ready
from src.bilun.domain.billing.orchestrator import compute_patient_billing_report
from src.bilun.domain.billing.drug_indication_findings import (
    evaluate_drug_indication_findings,
)
from src.bilun.domain.claims.models import ClaimDiagnosis, ClaimHeader, DrugClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.drug_indication import list_drug_indication_rules
from src.bilun.shared.models import ClaimValidationRequest, DrugContext, MaterialItem

pytestmark = pytest.mark.unit


def _ctx(*, report_present: bool | None = False) -> PatientClaimContext:
    claim = ClaimHeader(
        claim_id="C1",
        patient_id="P1",
        episode_id="E1",
        claim_type="yatis",
        facility_tier="2",
        provider_type="kamu",
        department="onkoloji",
        admission_date=date(2026, 1, 1),
        discharge_date=date(2026, 1, 5),
        claim_start_date=date(2026, 1, 1),
        claim_end_date=date(2026, 1, 5),
        primary_icd10="C34.9",
        package_candidate=False,
        expected_total_billed_try=Decimal("10000"),
        expected_total_payable_try=Decimal("7200"),
        expected_denial_reason="",
        scenario_tag="sgk_drug_indication_bevacizumab_missing_report",
    )
    drug_line = DrugClaimLine(
        drug_claim_line_id="D1",
        prescription_id="RX1",
        claim_id="C1",
        patient_id="P1",
        episode_id="E1",
        drug_claim_date=date(2026, 1, 2),
        drug_name="AVASTIN 400 MG (BEVACIZUMAB)",
        drug_code="A00000",
        barkod="8690000000001",
        equivalence_group="bevasizumab",
        quantity=1,
        unit_price_try=Decimal("10000"),
        billed_amount_try=Decimal("10000"),
        expected_payable_try=Decimal("7200"),
        discount_tier_expected=Decimal("0.28"),
        denial_reason_expected="",
        rule_trace_expected="",
        drug_specialty_board_report_present=report_present,
    )
    return PatientClaimContext(
        patient_id="P1",
        claims=(claim,),
        procedure_lines=(),
        material_lines=(),
        drug_lines=(drug_line,),
        diagnoses=(
            ClaimDiagnosis(
                diagnosis_id="DG1",
                claim_id="C1",
                patient_id="P1",
                episode_id="E1",
                icd10_code="C34.9",
                is_primary=True,
                diagnosis_role="birincil",
                diagnosis_date=date(2026, 1, 1),
                exemption_eligible=False,
            ),
        ),
    )


class TestPatientBillingDrugIndicationApi:
    def test_validate_claim_endpoint_preserves_structured_legacy_details(self) -> None:
        payload = validate_claim_legacy_endpoint(
            ClaimValidationRequest(
                claim_id="PUBLIC-ENDPOINT-MISMATCH",
                materials=[MaterialItem(name="Trastuzumab", unit_price=500)],
                drug_context=DrugContext(
                    primary_icd10="J45.9",
                    prescriber_specialty="tıbbi onkoloji",
                    board_report_present=True,
                    report_duration_months=3,
                ),
            )
        )
        model = ValidateClaimResponse.model_validate(payload)
        violation = next(
            row for row in model.violations if row.get("rule") == "drug_indication"
        )

        assert violation["material_name"] == "Trastuzumab"
        assert violation["message"]
        assert violation["savings_try"] == 0.0
        assert violation["risk_amount"] == 0.0
        assert violation["details"]["violation_kind"] == "indication_mismatch"
        assert violation["details"]["finding_id"].startswith("drug_indication:")

    def test_billing_json_surfaces_drug_indication_violations(self) -> None:
        report = compute_patient_billing_report("P1", claim_context=_ctx(report_present=False))
        payload = _serialize_billing_report(report)
        model = BillingReportResponse.model_validate(payload)

        assert model.drug_indication_violation_count == 1
        assert model.drug_indication.violation_count == 1
        assert model.drug_indication.violations[0]["violation_kind"] == "missing_board_report"
        assert len(model.drug_indication.findings) == 1
        finding = model.drug_indication.findings[0]
        assert finding.finding_id == "drug_indication:P1:C1:D1:missing_board_report"
        assert finding.observed_icd10_codes == ["C34.9"]
        assert finding.explanation_tr
        assert finding.recommended_action_tr
        assert finding.eligible_routes
        assert "_legacy_base" not in payload["drug_indication"]["findings"][0]
        assert all(
            route.rule_id and len(route.regulatory_summary_tr or "") <= 600
            for route in finding.eligible_routes
        )
        assert model.drug_indication.coverage_scope.get("pilot_rule_count", 0) >= 131
        assert model.drug_indication.coverage_scope.get("v1_stop_conditions")

        drug_actions = [
            row
            for row in payload["recommended_actions"]
            if row.get("surface") == "drug_indication"
        ]
        assert drug_actions[0]["action_id"] == finding.finding_id
        assert drug_actions[0]["finding_id"] == finding.finding_id
        assert drug_actions[0]["sgk_uplift_try"] is None
        assert drug_actions[0]["audit_risk_try"] is None
        assert drug_actions[0]["compliance_savings_try"] is None

    def test_billing_json_clean_when_report_present(self) -> None:
        report = compute_patient_billing_report("P1", claim_context=_ctx(report_present=True))
        payload = _serialize_billing_report(report)
        model = BillingReportResponse.model_validate(payload)

        assert model.drug_indication_violation_count == 0
        assert model.drug_indication.violation_count == 0

    def test_legacy_payload_defaults_structured_fields_without_fabricating_exactness(self) -> None:
        model = BillingReportResponse.model_validate(
            {
                "patient_id": "P-LEGACY",
                "drug_indication": {
                    "exactness_status": "missing_exact_inputs",
                    "required_inputs_missing": ["claim_diagnoses"],
                    "violations": [
                        {
                            "claim_id": "C-LEGACY",
                            "drug_name": "AVASTIN",
                            "violation_kind": "needs_report_verification",
                            "severity": "review",
                        }
                    ],
                },
            }
        )

        assert model.drug_indication.findings == []
        assert model.drug_indication.evaluations == []
        assert model.drug_indication.exactness_status == "missing_exact_inputs"
        assert model.drug_indication.required_inputs_missing == ["claim_diagnoses"]

    def test_json_ready_cache_round_trip_preserves_nested_counts_and_contract(self) -> None:
        report = compute_patient_billing_report("P1", claim_context=_ctx(report_present=False))
        live = BillingReportResponse.model_validate(_serialize_billing_report(report))
        cached_payload = _serialize_billing_report(json_ready(report))
        cached = BillingReportResponse.model_validate(cached_payload)

        assert cached.drug_indication_violation_count == live.drug_indication_violation_count == 1
        assert cached.drug_indication.violation_count == live.drug_indication.violation_count == 1
        assert cached.drug_indication.error_count == live.drug_indication.error_count == 1
        assert [row.finding_id for row in cached.drug_indication.findings] == [
            row.finding_id for row in live.drug_indication.findings
        ]
        assert [row.drug_claim_line_id for row in cached.drug_indication.evaluations] == [
            row.drug_claim_line_id for row in live.drug_indication.evaluations
        ]
        cached_action = next(
            row for row in cached.recommended_actions if row.get("surface") == "drug_indication"
        )
        assert cached_action["sgk_uplift_try"] is None
        assert cached_action["audit_risk_try"] is None
        assert cached_action["compliance_savings_try"] is None

    def test_unencoded_drug_cache_round_trip_preserves_noncoverage_without_missing_inputs(
        self,
    ) -> None:
        ctx = _ctx(report_present=True)
        ctx = replace(
            ctx,
            drug_lines=(
                replace(ctx.drug_lines[0], drug_name="UNENCODED MEDICINE"),
            ),
        )
        report = compute_patient_billing_report("P1", claim_context=ctx)
        payload = _serialize_billing_report(json_ready(report))
        model = BillingReportResponse.model_validate(payload)

        assert model.drug_indication_violation_count == 0
        assert model.drug_indication.violation_count == 0
        assert model.drug_indication.findings == []
        assert len(model.drug_indication.evaluations) == 1
        evaluation = model.drug_indication.evaluations[0]
        assert evaluation.applicability_status == "not_in_encoded_corpus"
        assert evaluation.evaluation_status == "unavailable"
        assert evaluation.missing_inputs == []
        assert model.drug_indication.required_inputs_missing == []
        assert model.drug_indication.unavailable_reason

    def test_api_contract_preserves_route_and_observed_diagnosis_truncation(self) -> None:
        antidote_rule = next(
            rule
            for rule in list_drug_indication_rules()
            if rule.get("rule_id")
            == "4.2.3.poisoning_antidote_full_coverage_no_report"
        )
        ctx = _ctx(report_present=True)
        ctx = replace(
            ctx,
            drug_lines=(replace(ctx.drug_lines[0], drug_name="PANZEHIR"),),
            diagnoses=tuple(
                ClaimDiagnosis(
                    diagnosis_id=f"DG-{index}",
                    claim_id="C1",
                    patient_id="P1",
                    episode_id="E1",
                    icd10_code=f"Z{index:02d}.1",
                    is_primary=False,
                    diagnosis_role="ek",
                    diagnosis_date=date(2026, 1, 1),
                    exemption_eligible=False,
                )
                for index in range(70)
            ),
        )
        batch = evaluate_drug_indication_findings(
            ctx.patient_id,
            ctx,
            rules=[antidote_rule],
        )
        model = DrugIndicationReviewResponse.model_validate(
            {
                "exactness_status": "exact",
                "findings": [finding.to_dict() for finding in batch.findings],
                "evaluations": [evaluation.to_dict() for evaluation in batch.evaluations],
                "violations": list(batch.legacy_violations),
            }
        )

        finding = model.findings[0]
        evaluation = model.evaluations[0]
        route = finding.eligible_routes[0]
        assert finding.observed_icd10_count == 71
        assert finding.observed_icd10_truncated is True
        assert evaluation.observed_icd10_count == 71
        assert evaluation.observed_icd10_truncated is True
        assert route.icd10_code_count == 23
        assert route.icd10_codes_truncated is True
        assert route.icd10_range_count == 0
        assert route.icd10_ranges_truncated is False

    def test_genuine_legacy_exact_payload_is_downgraded_and_counted(self) -> None:
        model = BillingReportResponse.model_validate(
            {
                "patient_id": "P-LEGACY",
                "drug_indication": {
                    "exactness_status": "exact",
                    "violations": [
                        {
                            "claim_id": "C-LEGACY",
                            "drug_name": "AVASTIN",
                            "violation_kind": "missing_board_report",
                            "severity": "error",
                        }
                    ],
                },
            }
        )

        assert model.drug_indication.violation_count == 1
        assert model.drug_indication.error_count == 1
        assert model.drug_indication.exactness_status in {
            "missing_exact_inputs",
            "partial_exact",
        }
        assert model.drug_indication.findings == []
        assert model.drug_indication.evaluations == []
        assert model.drug_indication.unavailable_reason
        assert model.drug_indication.required_inputs_missing

    def test_genuine_legacy_empty_payload_is_not_claimed_exact(self) -> None:
        model = BillingReportResponse.model_validate(
            {
                "patient_id": "P-EMPTY",
                "drug_indication": {"exactness_status": "exact"},
            }
        )

        assert model.drug_indication.violation_count == 0
        assert model.drug_indication.error_count == 0
        assert model.drug_indication.exactness_status != "exact"
        assert model.drug_indication.findings == []
        assert model.drug_indication.evaluations == []

    def test_mixed_structured_and_legacy_payload_uses_structured_counts(self) -> None:
        report = compute_patient_billing_report("P1", claim_context=_ctx(report_present=False))
        payload = _serialize_billing_report(report)
        payload["drug_indication"]["violations"] = [
            {"violation_kind": "missing_board_report", "severity": "error"},
            {"violation_kind": "indication_mismatch", "severity": "error"},
        ]

        model = BillingReportResponse.model_validate(payload)

        assert len(model.drug_indication.findings) == 1
        assert model.drug_indication.violation_count == 1
        assert model.drug_indication.error_count == 1

    def test_malformed_structured_finding_fails_closed(self) -> None:
        with pytest.raises(ValidationError):
            BillingReportResponse.model_validate(
                {
                    "patient_id": "P-MALFORMED",
                    "drug_indication": {"findings": [{"finding_id": "only-id"}]},
                }
            )
