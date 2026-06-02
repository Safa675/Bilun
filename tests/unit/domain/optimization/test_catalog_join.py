"""L2.3 / L2.4 — runtime EK-2G and EK-2C-1 catalog joins."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ProcedureClaimLine
from src.bilun.domain.optimization.catalog_join import (
    catalog_copay_rate_applicable,
    catalog_surcharge_eligible,
    copay_rate_matches_catalog,
    is_ek2g_surcharge_prohibited,
)
from src.bilun.domain.optimization.claim_context import build_surcharge_claim_context
from src.bilun.domain.optimization.exactness import build_exact_surcharge_exposure

pytestmark = pytest.mark.unit


def test_ek2g_catalog_marks_prohibited_codes() -> None:
    assert is_ek2g_surcharge_prohibited("551120") is True
    assert catalog_surcharge_eligible("551120") is False


def test_surcharge_exposure_uses_catalog_not_misleading_flags(monkeypatch) -> None:
    line = ProcedureClaimLine(
        procedure_line_id="P1",
        claim_id="C1",
        patient_id="PT",
        episode_id="E1",
        procedure_date=__import__("datetime").date(2026, 1, 1),
        procedure_code="551120",
        procedure_name="EK-2G listed",
        procedure_category="islem",
        quantity=1,
        unit_price_try=Decimal("100"),
        billed_amount_try=Decimal("100"),
        expected_payable_try=Decimal("80"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=True,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    ctx = build_surcharge_claim_context("PT", [line])
    assert ctx is not None
    result = build_exact_surcharge_exposure(ctx)
    assert result["n_applicable_procedures"] == 0
    assert result["n_flag_catalog_mismatches"] == 1


def test_ek2c1_rate_match_tolerance() -> None:
    if not catalog_copay_rate_applicable("P552001"):
        pytest.skip("P552001 not in local EK-2C-1 parquet")
    assert copay_rate_matches_catalog(Decimal("100"), "P552001") is True
    assert copay_rate_matches_catalog(Decimal("50"), "P552001") is False
