"""Unit tests for prospective gazette repricing detector."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.prose_rules.gazette_repricing import (
    detect_gazette_repricing_opportunities,
    load_gazette_repricing_rules,
)


def _claim(**overrides) -> ClaimHeader:
    # Service date is kept within 90 days of the 2026-01-01 tebliğ so the
    # line is still flagged as a prospective repricing opportunity.
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
        "claim_start_date": date(2025, 12, 1),
        "claim_end_date": date(2025, 12, 1),
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
        "procedure_date": date(2025, 12, 1),
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

    def test_skips_when_amendment_is_beyond_window(self) -> None:
        # 2024-06-01 → 2026-01-01 is ~579 days, well beyond the 90-day window.
        rows = detect_gazette_repricing_opportunities(
            _claim(
                claim_start_date=date(2024, 6, 1),
                claim_end_date=date(2024, 6, 1),
            ),
            [_proc_line(procedure_date=date(2024, 6, 1))],
        )
        assert rows == []


def test_gazette_repricing_rules_corpus_seeded() -> None:
    rules = load_gazette_repricing_rules()
    assert len(rules.get("rules", [])) >= 2
    codes = {code for rule in rules["rules"] for code in rule.get("procedure_codes", [])}
    assert "600150" in codes
