"""Unit tests for DRG / EK-2/C package adequacy detector."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.prose_rules.drg_package_adequacy import (
    detect_drg_package_adequacy_opportunities,
)


def _claim(**overrides) -> ClaimHeader:
    base = {
        "claim_id": "F-DEMO-001",
        "patient_id": "P1",
        "episode_id": "E1",
        "claim_type": "yatis",
        "facility_tier": "egitim_arastirma",
        "provider_type": "Universite",
        "department": "Genel",
        "admission_date": date(2024, 6, 1),
        "discharge_date": date(2024, 6, 5),
        "claim_start_date": date(2024, 6, 1),
        "claim_end_date": date(2024, 6, 5),
        "primary_icd10": "K50.9",
        "package_candidate": True,
        "expected_total_billed_try": Decimal("10000.00"),
        "expected_total_payable_try": Decimal("9000.00"),
        "expected_denial_reason": "",
        "scenario_tag": "sgk_package_adequacy_undercoded",
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
        "procedure_code": "600150",
        "procedure_name": "Proc A",
        "procedure_category": "islem",
        "quantity": 1,
        "unit_price_try": Decimal("5000.00"),
        "billed_amount_try": Decimal("5000.00"),
        "expected_payable_try": Decimal("4500.00"),
        "is_package_included": False,
        "package_code": "",
        "surcharge_applicable": False,
        "copay_rate_applicable": False,
        "denial_reason_expected": "",
        "rule_trace_expected": "",
    }
    base.update(overrides)
    return ProcedureClaimLine(**base)


class TestDrgPackageAdequacy:
    def test_flags_under_coded_package(self) -> None:
        claim = _claim()
        procs = [
            _proc_line(),
            _proc_line(
                procedure_line_id="ISL-2",
                procedure_code="600160",
                procedure_name="Proc B",
            ),
            _proc_line(
                procedure_line_id="ISL-3",
                procedure_code="609270",
                procedure_name="Package",
                procedure_category="paket",
                billed_amount_try=Decimal("3500.00"),
                expected_payable_try=Decimal("3500.00"),
            ),
        ]

        rows = detect_drg_package_adequacy_opportunities(claim, procs)
        assert len(rows) == 1
        assert rows[0]["current_package_code"] == "609270"
        assert rows[0]["candidate_package_code"] == "609300"
        assert rows[0]["recommendation_kind"] == "documentation_review"
        assert rows[0]["included_in_sgk_total"] is False
        assert rows[0]["primary_icd10"] == "K50.9"
        assert set(rows[0]["clinical_procedure_codes"]) == {"600150", "600160"}

    def test_skips_non_package_candidate_claims(self) -> None:
        claim = _claim(package_candidate=False)
        procs = [
            _proc_line(),
            _proc_line(
                procedure_line_id="ISL-3",
                procedure_code="609270",
                procedure_category="paket",
                billed_amount_try=Decimal("3500.00"),
            ),
        ]
        assert detect_drg_package_adequacy_opportunities(claim, procs) == []

    def test_skips_unknown_billed_package(self) -> None:
        claim = _claim()
        procs = [
            _proc_line(),
            _proc_line(
                procedure_line_id="ISL-2",
                procedure_code="600160",
                procedure_name="Proc B",
            ),
            _proc_line(
                procedure_line_id="ISL-3",
                procedure_code="999999",
                procedure_name="Unknown package",
                procedure_category="paket",
                billed_amount_try=Decimal("3500.00"),
            ),
        ]
        assert detect_drg_package_adequacy_opportunities(claim, procs) == []

    def test_skips_when_footprint_not_met(self) -> None:
        claim = _claim()
        procs = [
            _proc_line(),
            _proc_line(
                procedure_line_id="ISL-3",
                procedure_code="609270",
                procedure_category="paket",
                billed_amount_try=Decimal("3500.00"),
            ),
        ]
        assert detect_drg_package_adequacy_opportunities(claim, procs) == []
