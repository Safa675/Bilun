"""Unit tests for EMR vs claim procedure capture gap detector."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ClaimHeader, PerformedProcedureLine, ProcedureClaimLine
from src.bilun.domain.prose_rules.procedure_capture_gap import detect_procedure_capture_gaps


def _claim(**overrides) -> ClaimHeader:
    base = {
        "claim_id": "F-DEMO-001",
        "patient_id": "P1",
        "episode_id": "E1",
        "claim_type": "gunubirlik",
        "facility_tier": "egitim_arastirma",
        "provider_type": "Universite",
        "department": "Gastro",
        "admission_date": date(2024, 6, 1),
        "discharge_date": date(2024, 6, 1),
        "claim_start_date": date(2024, 6, 1),
        "claim_end_date": date(2024, 6, 1),
        "primary_icd10": "K50.9",
        "package_candidate": False,
        "expected_total_billed_try": Decimal("1000.00"),
        "expected_total_payable_try": Decimal("900.00"),
        "expected_denial_reason": "",
        "scenario_tag": "sgk_procedure_capture_kolonoskopi",
    }
    base.update(overrides)
    return ClaimHeader(**base)


def _proc_line(**overrides) -> ProcedureClaimLine:
    base = {
        "procedure_line_id": "ISL-1",
        "claim_id": "F-DEMO-001",
        "patient_id": "P1",
        "episode_id": "E1",
        "procedure_date": date(2024, 6, 1),
        "procedure_code": "701450",
        "procedure_name": "Kolonoskopi",
        "procedure_category": "islem",
        "quantity": 1,
        "unit_price_try": Decimal("1200.00"),
        "billed_amount_try": Decimal("1200.00"),
        "expected_payable_try": Decimal("1080.00"),
        "is_package_included": False,
        "package_code": "",
        "surcharge_applicable": False,
        "copay_rate_applicable": True,
        "denial_reason_expected": "",
        "rule_trace_expected": "",
    }
    base.update(overrides)
    return ProcedureClaimLine(**base)


def _performed(**overrides) -> PerformedProcedureLine:
    base = {
        "performed_line_id": "EMR-1",
        "claim_id": "F-DEMO-001",
        "patient_id": "P1",
        "episode_id": "E1",
        "service_date": date(2024, 6, 1),
        "procedure_code": "701460",
        "procedure_name": "Polipektomi",
        "source": "emr",
    }
    base.update(overrides)
    return PerformedProcedureLine(**base)


class TestProcedureCaptureGap:
    def test_flags_performed_not_submitted(self) -> None:
        claim = _claim()
        procs = [_proc_line()]
        performed = [_performed()]

        rows = detect_procedure_capture_gaps(claim, performed, procs)
        assert len(rows) == 1
        assert rows[0]["procedure_code"] == "701460"
        assert rows[0]["included_in_sgk_total"] is False
        assert rows[0]["recoverable_gap_try"] > 0
        assert rows[0]["price_methodology"] in ("ek2b_list_price", "ek2c_package_price")

    def test_suppresses_when_claim_submitted(self) -> None:
        claim = _claim()
        procs = [
            _proc_line(),
            _proc_line(
                procedure_line_id="ISL-2",
                procedure_code="701460",
                procedure_name="Polipektomi",
                billed_amount_try=Decimal("400.00"),
            ),
        ]
        performed = [_performed()]

        rows = detect_procedure_capture_gaps(claim, performed, procs)
        assert rows == []

    def test_suppresses_zero_billed_line_still_counts_as_missing_for_capture(self) -> None:
        claim = _claim()
        procs = [
            _proc_line(),
            _proc_line(
                procedure_line_id="ISL-2",
                procedure_code="701460",
                billed_amount_try=Decimal("0.00"),
            ),
        ]
        performed = [_performed()]

        rows = detect_procedure_capture_gaps(claim, performed, procs)
        assert len(rows) == 1
