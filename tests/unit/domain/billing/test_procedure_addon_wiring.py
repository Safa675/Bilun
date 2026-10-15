"""Phase 2.3 — procedure add-on uplift wiring."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.billing.orchestrator import compute_patient_billing_report
from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext

pytestmark = pytest.mark.unit


def _claim(**overrides) -> ClaimHeader:
    base = dict(
        claim_id="CLM-ADDON",
        patient_id="P1",
        episode_id="E1",
        claim_type="gunubirlik",
        facility_tier="egitim_arastirma",
        provider_type="Universite",
        department="gastroenterology",
        admission_date=date(2026, 1, 10),
        discharge_date=date(2026, 1, 10),
        claim_start_date=date(2026, 1, 10),
        claim_end_date=date(2026, 1, 10),
        primary_icd10="K63.5",
        package_candidate=False,
        expected_total_billed_try=Decimal("900"),
        expected_total_payable_try=Decimal("900"),
        expected_denial_reason="",
        scenario_tag="sgk_procedure_addon_kolonoskopi",
    )
    base.update(overrides)
    return ClaimHeader(**base)


def _proc(**overrides) -> ProcedureClaimLine:
    base = dict(
        procedure_line_id="PL1",
        claim_id="CLM-ADDON",
        patient_id="P1",
        episode_id="E1",
        procedure_date=date(2026, 1, 10),
        procedure_code="701450",
        procedure_name="Kolonoskopi",
        procedure_category="islem",
        quantity=1,
        unit_price_try=Decimal("879.72"),
        billed_amount_try=Decimal("879.72"),
        expected_payable_try=Decimal("879.72"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=True,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    base.update(overrides)
    return ProcedureClaimLine(**base)


class TestProcedureAddonWiring:
    def test_addon_counts_in_sgk_headline(self) -> None:
        claim = _claim()
        ctx = PatientClaimContext(
            patient_id="P1",
            claims=(claim,),
            procedure_lines=(_proc(),),
            material_lines=(),
            drug_lines=(),
            diagnoses=(),
        )
        report = compute_patient_billing_report(
            "P1",
            claim_context=ctx,
            copay_exemption={"exempt": False},
        )
        expected = round(879.72 * 0.3, 2)
        assert report.procedure_addon_uplift.confirmed_uplift_try == pytest.approx(
            expected, rel=0.02
        )
        assert report.sgk_uplift_try >= report.procedure_addon_uplift.confirmed_uplift_try

    def test_underbilled_addon_uses_session_not_missing_addon(self) -> None:
        claim = _claim()
        procs = (
            _proc(),
            _proc(
                procedure_line_id="PL2",
                procedure_code="701460",
                procedure_name="Polipektomi",
                billed_amount_try=Decimal("50"),
                expected_payable_try=Decimal("50"),
            ),
        )
        ctx = PatientClaimContext(
            patient_id="P1",
            claims=(claim,),
            procedure_lines=procs,
            material_lines=(),
            drug_lines=(),
            diagnoses=(),
        )
        report = compute_patient_billing_report(
            "P1",
            claim_context=ctx,
            copay_exemption={"exempt": False},
        )
        assert report.procedure_addon_uplift.opportunities == []
        assert report.session_uplift.confirmed_uplift_try > 0

    def test_addon_factor_reads_the_branches_of_session_operations_only(self) -> None:
        from src.bilun.domain.prose_rules.procedure_addon_uplift import (
            detect_missing_procedure_addon_opportunities,
        )

        # #261: the anaesthesia line (another branch) is not a session operation,
        # so the missing polypectomy stays at 30 %, not 30 + 25 cross-specialty.
        procs = [
            _proc(procedure_specialty_code="1900"),
            _proc(procedure_line_id="PL2", procedure_code="550160", procedure_name="Anestezi",
                  procedure_specialty_code="3100"),
        ]
        rows = detect_missing_procedure_addon_opportunities(_claim(), procs)
        assert [(r["expected_addon_procedure_code"], r["addon_factor"]) for r in rows] == [
            ("701460", 0.3),
        ]
