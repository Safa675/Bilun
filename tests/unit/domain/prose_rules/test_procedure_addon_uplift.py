"""Unit tests for missing procedure add-on detector."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.prose_rules.procedure_addon_uplift import (
    detect_missing_procedure_addon_opportunities,
)

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


class TestProcedureAddonUplift:
    def test_colonoscopy_missing_polypectomy(self) -> None:
        claim = _claim()
        rows = detect_missing_procedure_addon_opportunities(claim, [_proc()])
        assert len(rows) == 1
        row = rows[0]
        assert row["type"] == "missing_add_on_procedure"
        assert row["trigger_procedure_code"] == "701450"
        assert row["expected_addon_procedure_code"] == "701460"
        assert row["addon_factor"] == pytest.approx(0.3)
        assert row["recoverable_uplift_try"] == pytest.approx(879.72 * 0.3, rel=0.02)
        assert row["price_methodology"] == "primary_billed_x_session_factor"
        assert row["included_in_sgk_total"] is True

    def test_zero_billed_addon_line_suppresses_missing(self) -> None:
        claim = _claim()
        procs = [
            _proc(),
            _proc(
                procedure_line_id="PL2",
                procedure_code="701460",
                procedure_name="Polipektomi",
                billed_amount_try=Decimal("0"),
                expected_payable_try=Decimal("0"),
            ),
        ]
        assert detect_missing_procedure_addon_opportunities(claim, procs) == []

    def test_addon_present_suppresses_uplift(self) -> None:
        claim = _claim()
        procs = [
            _proc(),
            _proc(
                procedure_line_id="PL2",
                procedure_code="701460",
                procedure_name="Polipektomi",
                billed_amount_try=Decimal("200"),
                expected_payable_try=Decimal("200"),
            ),
        ]
        assert detect_missing_procedure_addon_opportunities(claim, procs) == []

    def test_session_uplift_dedupes(self) -> None:
        claim = _claim()
        session_rows = [
            {
                "claim_id": "CLM-ADDON",
                "session_date": "2026-01-10",
                "procedure_code": "701460",
            }
        ]
        assert (
            detect_missing_procedure_addon_opportunities(
                claim,
                [_proc()],
                session_uplift_opportunities=session_rows,
            )
            == []
        )
