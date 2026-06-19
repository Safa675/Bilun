"""Synthetic demo vignette hypothetical totals for optional override."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.billing.demo_vignette_lookup import (
    hypothetical_itemized_total_try,
    hypothetical_package_total_try,
)
from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine

pytestmark = pytest.mark.unit


def _claim(**overrides) -> ClaimHeader:
    base = dict(
        claim_id="CLM-DEMO",
        patient_id="SENTETIK-HASTA-0003",
        episode_id="E1",
        claim_type="yatis",
        facility_tier="egitim_arastirma",
        provider_type="Universite",
        department="Ortopedi ve Travmatoloji",
        admission_date=date(2023, 2, 19),
        discharge_date=date(2023, 2, 21),
        claim_start_date=date(2023, 2, 19),
        claim_end_date=date(2023, 2, 21),
        primary_icd10="M23.2",
        package_candidate=True,
        expected_total_billed_try=Decimal("4000"),
        expected_total_payable_try=Decimal("4000"),
        expected_denial_reason="",
        scenario_tag="sgk_optional_override_package_higher",
    )
    base.update(overrides)
    return ClaimHeader(**base)


def _proc(**overrides) -> ProcedureClaimLine:
    base = dict(
        procedure_line_id="PL1",
        claim_id="CLM-DEMO",
        patient_id="SENTETIK-HASTA-0003",
        episode_id="E1",
        procedure_date=date(2023, 2, 19),
        procedure_code="600150",
        procedure_name="Item A",
        procedure_category="islem",
        quantity=1,
        unit_price_try=Decimal("2200"),
        billed_amount_try=Decimal("2200"),
        expected_payable_try=Decimal("2200"),
        is_package_included=False,
        package_code="609300",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    base.update(overrides)
    return ProcedureClaimLine(**base)


class TestDemoVignetteLookup:
    def test_package_hypothesis_for_itemized_only_submission(self) -> None:
        claim = _claim()
        lines = [
            _proc(),
            _proc(
                procedure_line_id="PL2",
                procedure_code="600160",
                procedure_name="Item B",
                unit_price_try=Decimal("1800"),
                billed_amount_try=Decimal("1800"),
                expected_payable_try=Decimal("1800"),
            ),
        ]
        assert hypothetical_package_total_try(claim, lines, resolved_package_total=6975.48) == 9000.0

    def test_itemized_hypothesis_for_package_only_submission(self) -> None:
        claim = _claim(
            patient_id="SENTETIK-HASTA-0002",
            scenario_tag="sgk_optional_override_itemized_higher",
        )
        lines = [
            _proc(
                procedure_code="609270",
                procedure_name="Package",
                procedure_category="paket",
                unit_price_try=Decimal("3500"),
                billed_amount_try=Decimal("3500"),
                expected_payable_try=Decimal("3500"),
                package_code="609270",
            ),
        ]
        assert hypothetical_itemized_total_try(claim, lines, resolved_itemized_total=0.0) == 9000.0
