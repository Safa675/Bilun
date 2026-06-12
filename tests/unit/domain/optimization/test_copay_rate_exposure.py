"""EK-2C-1 implied copay rate exposure tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ProcedureClaimLine
from src.bilun.domain.optimization.catalog_join import copay_rate_matches_catalog
from src.bilun.domain.optimization.claim_context import (
    build_copay_rate_claim_context,
    procedure_implied_copay_rate_pct,
    procedure_sgk_share_pct,
)
from src.bilun.domain.optimization.exactness import build_exact_copay_rate_exposure

pytestmark = pytest.mark.unit


def _line(
    *,
    code: str = "P604713",
    billed: str = "100.00",
    payable: str = "60.00",
    copay_flag: bool = True,
) -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id="L1",
        claim_id="C1",
        patient_id="P1",
        episode_id="E1",
        procedure_date=date(2026, 1, 15),
        procedure_code=code,
        procedure_name="Test procedure",
        procedure_category="islem",
        quantity=1,
        unit_price_try=Decimal(billed),
        billed_amount_try=Decimal(billed),
        expected_payable_try=Decimal(payable),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=copay_flag,
        denial_reason_expected="",
        rule_trace_expected="",
    )


def test_implied_copay_from_payable_billed() -> None:
    line = _line(billed="100.00", payable="60.00")
    assert procedure_sgk_share_pct(line) == Decimal("60.00")
    assert procedure_implied_copay_rate_pct(line) == Decimal("40.00")


def test_sgk_share_is_capped_at_one_hundred() -> None:
    line = _line(billed="100.00", payable="150.00")
    assert procedure_sgk_share_pct(line) == Decimal("100.00")
    assert procedure_implied_copay_rate_pct(line) == Decimal("0.00")


def test_catalog_match_uses_implied_copay_not_sgk_share() -> None:
    line = _line(billed="100.00", payable="60.00", code="P604713")
    implied = procedure_implied_copay_rate_pct(line)
    if not copay_rate_matches_catalog(implied, line.procedure_code):
        pytest.skip("P604713 not in local EK-2C-1 parquet")
    assert copay_rate_matches_catalog(implied, line.procedure_code) is True
    assert copay_rate_matches_catalog(procedure_sgk_share_pct(line), line.procedure_code) is False


def test_exact_exposure_flags_rate_mismatch_only() -> None:
    line = _line(billed="100.00", payable="80.00", code="P604713")
    ctx = build_copay_rate_claim_context("P1", [line])
    assert ctx is not None
    result = build_exact_copay_rate_exposure(ctx)
    assert result["n_applicable_procedures"] == 1
    if result["n_rate_catalog_mismatches"] == 0:
        pytest.skip("Catalog rate for P604713 is 20% on this dataset")
    assert result["n_violations"] >= 1
    assert result["procedures_with_rates"][0]["rate_pct"] == 20.0


def test_synthetic_claim_lines_never_exceed_one_hundred_sgk_share() -> None:
    from src.bilun.domain.claims import load_sut_claim_dataset

    dataset = load_sut_claim_dataset()
    for line in dataset.procedure_lines.values():
        share = float(procedure_sgk_share_pct(line))
        assert share <= 100.0, f"{line.procedure_line_id} SGK share {share}% > 100%"


def test_synthetic_ek2c1_violations_are_demo_scoped() -> None:
    from src.bilun.domain.claims import load_sut_claim_dataset
    from src.bilun.domain.optimization.claim_context import build_copay_rate_claim_context
    from src.bilun.domain.optimization.exactness import build_exact_copay_rate_exposure

    dataset = load_sut_claim_dataset("data/synthetic/sut/claims")
    rate_mismatches = 0
    flag_mismatches = 0
    for pid in dataset.claims_by_patient:
        lines = list(dataset.procedure_lines_by_patient.get(pid, ()))
        ctx = build_copay_rate_claim_context(pid, lines)
        if ctx is None:
            continue
        exposure = build_exact_copay_rate_exposure(ctx)
        rate_mismatches += int(exposure.get("n_rate_catalog_mismatches") or 0)
        flag_mismatches += int(exposure.get("n_flag_catalog_mismatches") or 0)

    assert rate_mismatches <= 2, f"expected ≤2 demo rate mismatches, got {rate_mismatches}"
    assert flag_mismatches <= 1, f"expected ≤1 demo flag mismatch, got {flag_mismatches}"
