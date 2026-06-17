"""Golden tests for gazette repricing corpus (Wave 1)."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.prose_rules.gazette_repricing import (
    detect_gazette_repricing_opportunities,
    load_gazette_repricing_rules,
)

_GOLDEN_PATH = (
    Path(__file__).resolve().parents[4]
    / "data/gazette/prose_rules/golden/gazette_repricing_batch_a.json"
)


def _load_golden_cases() -> list[dict]:
    payload = json.loads(_GOLDEN_PATH.read_text(encoding="utf-8"))
    return list(payload.get("cases", []))


def _claim(service_date: str) -> ClaimHeader:
    service = date.fromisoformat(service_date)
    return ClaimHeader(
        claim_id="F-GOLDEN-001",
        patient_id="P1",
        episode_id="E1",
        claim_type="poliklinik",
        facility_tier="2_basamak_kamu",
        provider_type="Kamu",
        department="Genel",
        admission_date=None,
        discharge_date=None,
        claim_start_date=service,
        claim_end_date=service,
        primary_icd10="L98.9",
        package_candidate=False,
        expected_total_billed_try=Decimal("1000"),
        expected_total_payable_try=Decimal("1000"),
        expected_denial_reason="",
        scenario_tag="gazette_repricing_golden",
    )


def _proc_line(case: dict) -> ProcedureClaimLine:
    service = date.fromisoformat(str(case["service_date"]))
    payable = Decimal(str(case["stale_payable_per_unit"]))
    return ProcedureClaimLine(
        procedure_line_id=f"ISL-{case['case_id']}",
        claim_id="F-GOLDEN-001",
        patient_id="P1",
        episode_id="E1",
        procedure_date=service,
        procedure_code=str(case["procedure_code"]),
        procedure_name=str(case["procedure_code"]),
        procedure_category=str(case["procedure_category"]),
        quantity=1,
        unit_price_try=payable,
        billed_amount_try=payable,
        expected_payable_try=payable,
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )


@pytest.mark.parametrize("case", _load_golden_cases(), ids=lambda c: c["case_id"])
def test_gazette_repricing_golden_case(case: dict) -> None:
    claim = _claim(str(case["service_date"]))
    line = _proc_line(case)
    rows = detect_gazette_repricing_opportunities(claim, [line])
    assert len(rows) == 1
    row = rows[0]
    assert row["price_at_service_try"] == pytest.approx(
        float(case["expected_price_at_service_try"]), rel=0.01
    )
    assert row["amended_list_price_try"] == pytest.approx(
        float(case["expected_amended_list_price_try"]), rel=0.01
    )
    assert row["recoverable_repricing_try"] == pytest.approx(
        float(case["expected_recoverable_repricing_try"]), rel=0.01
    )
    assert row["included_in_sgk_total"] is case["expected_included_in_sgk_total"]


def test_gazette_repricing_corpus_wave1_size() -> None:
    rules = load_gazette_repricing_rules()
    assert len(rules.get("rules", [])) >= 10
    codes = {
        code
        for rule in rules["rules"]
        for code in rule.get("procedure_codes", [])
    }
    assert "600150" in codes
    assert "609270" in codes
    assert "616190" in codes
    assert "701450" in codes
