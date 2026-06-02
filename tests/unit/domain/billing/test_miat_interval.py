"""MIAT interval checks (L3.5)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

pytestmark = pytest.mark.unit


def test_parse_miat_period_days() -> None:
    from src.bilun.domain.billing.miat_interval import parse_miat_period_days

    assert parse_miat_period_days("6 ay") == 180
    assert parse_miat_period_days("1 yıl") == 365


def test_miat_interval_violation_when_prior_use_too_recent() -> None:
    from src.bilun.domain.billing.miat_interval import check_miat_interval_violation
    from src.bilun.domain.claims.models import MaterialClaimLine
    from src.bilun.domain.claims.patient_context import PatientClaimContext

    prior = MaterialClaimLine(
        material_line_id="M1",
        claim_id="C1",
        procedure_line_id="P1",
        patient_id="PT1",
        material_date=date(2024, 1, 1),
        material_code="OP1000",
        material_name="Brace",
        material_type="ortez",
        specialty_category="ortho",
        quantity=1,
        unit_price_try=Decimal("100"),
        billed_amount_try=Decimal("100"),
        expected_payable_try=Decimal("80"),
        is_bundled=False,
        requires_pre_auth=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    current = MaterialClaimLine(
        material_line_id="M2",
        claim_id="C2",
        procedure_line_id="P2",
        patient_id="PT1",
        material_date=date(2024, 2, 1),
        material_code="OP1000",
        material_name="Brace",
        material_type="ortez",
        specialty_category="ortho",
        quantity=1,
        unit_price_try=Decimal("100"),
        billed_amount_try=Decimal("100"),
        expected_payable_try=Decimal("80"),
        is_bundled=False,
        requires_pre_auth=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    ctx = PatientClaimContext(
        patient_id="PT1",
        claims=(),
        procedure_lines=(),
        material_lines=(prior, current),
        drug_lines=(),
        diagnoses=(),
    )

    hit = check_miat_interval_violation(ctx, current, miat_period="6 ay")
    assert hit is not None
    assert hit["savings_try"] is None
    assert hit["last_use_date"] == "2024-01-01"
