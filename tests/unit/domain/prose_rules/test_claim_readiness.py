"""Unit tests for proactive claim submission checklist."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.billing.claim_submission_checklist import (
    recommend_claim_submission_checklist_from_claims,
)
from src.bilun.domain.billing.types import EXACTNESS_STATUS_EXACT, EXACTNESS_STATUS_NOT_APPLICABLE
from src.bilun.domain.claims.models import (
    ClaimHeader,
    DrugClaimLine,
    MaterialClaimLine,
    MedulaRejectionEvent,
)
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.claim_readiness import detect_claim_readiness_items

pytestmark = pytest.mark.unit


def _claim(*, scenario_tag: str = "demo") -> ClaimHeader:
    return ClaimHeader(
        claim_id="F-DEMO-001",
        patient_id="P1",
        episode_id="E1",
        claim_type="yatis",
        facility_tier="2_basamak_kamu",
        provider_type="Kamu",
        department="Ortopedi",
        admission_date=date(2024, 10, 1),
        discharge_date=date(2024, 10, 3),
        claim_start_date=date(2024, 10, 1),
        claim_end_date=date(2024, 10, 3),
        primary_icd10="M17.9",
        package_candidate=False,
        expected_total_billed_try=Decimal("4200"),
        expected_total_payable_try=Decimal("4200"),
        expected_denial_reason="",
        scenario_tag=scenario_tag,
    )


def _material(*, uts_registered: bool = True) -> MaterialClaimLine:
    return MaterialClaimLine(
        material_line_id="MLZ-001",
        claim_id="F-DEMO-001",
        procedure_line_id="ISL-001",
        patient_id="P1",
        material_date=date(2024, 10, 1),
        material_code="OP2000",
        material_name="Implant",
        material_type="implant",
        specialty_category="ortopedi",
        quantity=1,
        unit_price_try=Decimal("4200"),
        billed_amount_try=Decimal("4200"),
        expected_payable_try=Decimal("4200"),
        is_bundled=False,
        requires_pre_auth=False,
        denial_reason_expected="",
        rule_trace_expected="",
        uts_registered=uts_registered,
        titubb_uts_barcode_documentation_missing=not uts_registered,
    )


def _drug(*, report_present: bool | None = False) -> DrugClaimLine:
    return DrugClaimLine(
        drug_claim_line_id="ILC-001",
        prescription_id="REC-001",
        claim_id="F-DEMO-001",
        patient_id="P1",
        episode_id="E1",
        drug_claim_date=date(2024, 10, 1),
        drug_name="Bevacizumab",
        drug_code="BEVA",
        barkod="8690000000001",
        equivalence_group="L01XC07",
        quantity=1,
        unit_price_try=Decimal("10000"),
        billed_amount_try=Decimal("10000"),
        expected_payable_try=Decimal("7200"),
        discount_tier_expected=Decimal("0.72"),
        denial_reason_expected="",
        rule_trace_expected="",
        drug_specialty_board_report_present=report_present,
        drug_inpatient_supply=True,
    )


class TestClaimReadinessDetection:
    def test_material_uts_missing_triggers_0704_risk(self) -> None:
        claim = _claim()
        ctx = PatientClaimContext(
            patient_id="P1",
            claims=(claim,),
            procedure_lines=(),
            material_lines=(_material(uts_registered=False),),
            drug_lines=(),
            diagnoses=(),
        )
        items = detect_claim_readiness_items(claim, ctx)
        assert len(items) == 1
        assert items[0]["sonuc_kodu_risk"] == "0704"
        assert items[0]["trigger_key"] == "material_uts_barcode_missing"

    def test_skips_when_rejection_already_recorded(self) -> None:
        claim = _claim()
        ctx = PatientClaimContext(
            patient_id="P1",
            claims=(claim,),
            procedure_lines=(),
            material_lines=(_material(uts_registered=False),),
            drug_lines=(),
            diagnoses=(),
            medula_rejection_events=(
                MedulaRejectionEvent(
                    rejection_event_id="MED-1",
                    claim_id="F-DEMO-001",
                    patient_id="P1",
                    episode_id="E1",
                    medula_stage="fatura_kayit",
                    sonuc_kodu="0704",
                    hata_mesaji="ÜTS eksik",
                ),
            ),
        )
        assert detect_claim_readiness_items(claim, ctx) == []

    def test_drug_missing_board_report_triggers_0612_risk(self) -> None:
        claim = _claim(scenario_tag="drug_demo")
        ctx = PatientClaimContext(
            patient_id="P1",
            claims=(claim,),
            procedure_lines=(),
            material_lines=(),
            drug_lines=(_drug(report_present=False),),
            diagnoses=(),
        )
        items = detect_claim_readiness_items(claim, ctx)
        assert len(items) == 1
        assert items[0]["sonuc_kodu_risk"] == "0612"


class TestClaimSubmissionChecklistWiring:
    def test_empty_context_not_applicable(self) -> None:
        block = recommend_claim_submission_checklist_from_claims(
            PatientClaimContext(
                patient_id="P1",
                claims=(),
                procedure_lines=(),
                material_lines=(),
                drug_lines=(),
                diagnoses=(),
            )
        )
        assert block.exactness_status == EXACTNESS_STATUS_NOT_APPLICABLE
        assert block.item_count == 0

    def test_wiring_returns_exact_items(self) -> None:
        claim = _claim(scenario_tag="sgk_claim_readiness_uts_barcode_missing")
        ctx = PatientClaimContext(
            patient_id="P1",
            claims=(claim,),
            procedure_lines=(),
            material_lines=(_material(uts_registered=False),),
            drug_lines=(),
            diagnoses=(),
        )
        block = recommend_claim_submission_checklist_from_claims(ctx)
        assert block.exactness_status == EXACTNESS_STATUS_EXACT
        assert block.item_count == 1
        assert block.items[0]["playbook_key"] == "0704_uts_barcode_missing"

    def test_merges_fatura_documentation_requirements(self) -> None:
        """A1: fatura_inceleme_checklist items land on the same checklist surface."""
        from src.bilun.domain.claims.models import ProcedureClaimLine

        claim = ClaimHeader(
            claim_id="F-DOC-001",
            patient_id="P1",
            episode_id="E1",
            claim_type="ayaktan",
            facility_tier="2_basamak_kamu",
            provider_type="Kamu",
            department="Dermatoloji",
            admission_date=None,
            discharge_date=None,
            claim_start_date=date(2024, 10, 1),
            claim_end_date=date(2024, 10, 1),
            primary_icd10="C44.9",
            package_candidate=False,
            expected_total_billed_try=Decimal("500"),
            expected_total_payable_try=Decimal("500"),
            expected_denial_reason="",
            scenario_tag="doc_checklist",
        )
        proc = ProcedureClaimLine(
            procedure_line_id="ISL-DOC-1",
            claim_id="F-DOC-001",
            patient_id="P1",
            episode_id="E1",
            procedure_date=date(2024, 10, 1),
            procedure_code="700280",
            procedure_name="Kriyoterapi malign lezyonlar",
            procedure_category="islem",
            quantity=1,
            unit_price_try=Decimal("500"),
            billed_amount_try=Decimal("500"),
            expected_payable_try=Decimal("500"),
            is_package_included=False,
            package_code="",
            surcharge_applicable=False,
            copay_rate_applicable=False,
            denial_reason_expected="",
            rule_trace_expected="",
        )
        ctx = PatientClaimContext(
            patient_id="P1",
            claims=(claim,),
            procedure_lines=(proc,),
            material_lines=(),
            drug_lines=(),
            diagnoses=(),
        )
        block = recommend_claim_submission_checklist_from_claims(ctx)
        assert block.exactness_status == EXACTNESS_STATUS_EXACT
        doc_items = [
            item
            for item in block.items
            if item.get("checklist_kind") == "documentation_requirement"
        ]
        assert doc_items, "expected fatura documentation checklist items"
        assert any("patoloji_raporu" in (item.get("required_documents") or []) for item in doc_items)
        assert all(item.get("severity") == "warning" for item in doc_items)
        # Advisory surface only — these must not look like analyze_claim violations.
        assert all(item.get("recommendation_kind") == "documentation_checklist" for item in doc_items)
