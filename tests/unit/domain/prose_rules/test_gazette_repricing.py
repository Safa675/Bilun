"""Unit tests for prospective gazette repricing detector.

Temporal catalog lookups are stubbed so absolute TRY amounts come from the
test fixture, not the live gazette as-of.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.prose_rules.gazette_repricing import (
    detect_gazette_repricing_opportunities,
    load_gazette_repricing_rules,
)
from tests.unit._helpers.catalog_stubs import (
    FIXTURE_GAZETTE_AMENDED_TRY,
    FIXTURE_GAZETTE_SERVICE_TRY,
    install_gazette_price_stub,
)


@pytest.fixture(autouse=True)
def _stub_gazette(monkeypatch: pytest.MonkeyPatch) -> dict:
    return install_gazette_price_stub(monkeypatch)


def _claim(**overrides) -> ClaimHeader:
    # Service date within 30 days of the fixture amendment (2026-01-01).
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
        "claim_start_date": date(2025, 12, 2),
        "claim_end_date": date(2025, 12, 2),
        "primary_icd10": "L98.9",
        "package_candidate": False,
        "expected_total_billed_try": Decimal(str(FIXTURE_GAZETTE_SERVICE_TRY)),
        "expected_total_payable_try": Decimal(str(FIXTURE_GAZETTE_SERVICE_TRY)),
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
        "procedure_date": date(2025, 12, 2),
        "procedure_code": "600150",
        "procedure_name": "Proc",
        "procedure_category": "islem",
        "quantity": 1,
        "unit_price_try": Decimal(str(FIXTURE_GAZETTE_SERVICE_TRY)),
        "billed_amount_try": Decimal(str(FIXTURE_GAZETTE_SERVICE_TRY)),
        "expected_payable_try": Decimal(str(FIXTURE_GAZETTE_SERVICE_TRY)),
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
    def test_flags_stale_price_after_teblig(self, _stub_gazette: dict) -> None:
        rows = detect_gazette_repricing_opportunities(
            _claim(),
            [_proc_line()],
        )
        assert len(rows) == 1
        assert rows[0]["procedure_code"] == "600150"
        assert rows[0]["price_at_service_try"] == _stub_gazette["service_price"]
        assert rows[0]["amended_list_price_try"] == _stub_gazette["amended_price"]
        assert rows[0]["recoverable_repricing_try"] == pytest.approx(
            float(_stub_gazette["recoverable"]), abs=0.01
        )
        assert rows[0]["included_in_sgk_total"] is False
        assert rows[0]["rebill_permitted"] is False
        assert rows[0]["review_only"] is True
        assert rows[0]["recommendation_kind"] == "prospective_repricing"

    def test_skips_when_payable_already_at_new_price(self) -> None:
        rows = detect_gazette_repricing_opportunities(
            _claim(),
            [
                _proc_line(
                    expected_payable_try=Decimal(str(FIXTURE_GAZETTE_AMENDED_TRY)),
                    billed_amount_try=Decimal(str(FIXTURE_GAZETTE_AMENDED_TRY)),
                    unit_price_try=Decimal(str(FIXTURE_GAZETTE_AMENDED_TRY)),
                )
            ],
        )
        assert rows == []

    def test_skips_when_amendment_is_beyond_window(self) -> None:
        rows = detect_gazette_repricing_opportunities(
            _claim(
                claim_start_date=date(2024, 6, 1),
                claim_end_date=date(2024, 6, 1),
            ),
            [_proc_line(procedure_date=date(2024, 6, 1))],
        )
        assert rows == []

    def test_skips_when_amendment_is_31_days_after_service(self) -> None:
        rows = detect_gazette_repricing_opportunities(
            _claim(
                claim_start_date=date(2025, 12, 1),
                claim_end_date=date(2025, 12, 1),
            ),
            [_proc_line(procedure_date=date(2025, 12, 1))],
        )
        assert rows == []


def test_gazette_repricing_rules_corpus_seeded() -> None:
    rules = load_gazette_repricing_rules()
    assert rules.get("max_days_after_service") == 30
    assert rules.get("detector_enabled") is True
    assert rules.get("rebill_permitted_default") is False
    assert rules.get("review_only") is True
    assert len(rules.get("rules", [])) >= 10
    codes = {code for rule in rules["rules"] for code in rule.get("procedure_codes", [])}
    assert "600150" in codes
    assert "600160" in codes
    assert "609300" in codes
    assert "701450" in codes
