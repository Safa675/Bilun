"""Unit tests for prospective gazette repricing detector."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.prose_rules.gazette_repricing import (
    detect_gazette_repricing_opportunities,
)


def _claim(**overrides) -> ClaimHeader:
    base = {
        "claim_id": "F-DEMO-001",
        "patient_id": "P1",
        "episode_id": "E1",
        "claim_type": "poliklinik",
        "facility_tier": "2_basamak_kamu",
        "provider_type": "Kamu",
        "department": "Genel",
        "admission_date": None,
        "discharge_date": None,
        "claim_start_date": date(2024, 6, 1),
        "claim_end_date": date(2024, 6, 1),
        "primary_icd10": "L98.9",
        "package_candidate": False,
        "expected_total_billed_try": Decimal("449.73"),
        "expected_total_payable_try": Decimal("449.73"),
        "expected_denial_reason": "",
        "scenario_tag": "sgk_gazette_repricing_600150",
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
        "procedure_name": "Proc",
        "procedure_category": "islem",
        "quantity": 1,
        "unit_price_try": Decimal("449.73"),
        "billed_amount_try": Decimal("449.73"),
        "expected_payable_try": Decimal("449.73"),
        "is_package_included": False,
        "package_code": "",
        "surcharge_applicable": False,
        "copay_rate_applicable": False,
        "denial_reason_expected": "",
        "rule_trace_expected": "",
    }
    base.update(overrides)
    return ProcedureClaimLine(**base)


class TestGazetteRepricing:
    def test_flags_stale_price_after_tebliğ(self) -> None:
        rows = detect_gazette_repricing_opportunities(
            _claim(),
            [_proc_line()],
        )
        assert len(rows) == 1
        assert rows[0]["procedure_code"] == "600150"
        assert rows[0]["price_at_service_try"] == 449.73
        assert rows[0]["amended_list_price_try"] == 539.68
        assert rows[0]["recoverable_repricing_try"] == 89.95
        assert rows[0]["included_in_sgk_total"] is False
        assert rows[0]["recommendation_kind"] == "prospective_repricing"

    def test_skips_when_payable_already_at_new_price(self) -> None:
        rows = detect_gazette_repricing_opportunities(
            _claim(),
            [
                _proc_line(
                    expected_payable_try=Decimal("539.68"),
                    billed_amount_try=Decimal("539.68"),
                    unit_price_try=Decimal("539.68"),
                )
            ],
        )
        assert rows == []
