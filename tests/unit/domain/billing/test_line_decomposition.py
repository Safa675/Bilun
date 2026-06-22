"""Unit tests for claim-line copay / ilave decomposition."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.bilun.domain.billing.line_decomposition import decompose_line

pytestmark = pytest.mark.unit


def test_exact_when_copay_and_surcharge_rates_present() -> None:
    billed = Decimal("1200.00")
    payable = Decimal("600.00")
    copay_rate = Decimal("0.40")
    surcharge_rate = Decimal("0.20")

    result = decompose_line(
        billed,
        payable,
        copay_rate=copay_rate,
        surcharge_rate=surcharge_rate,
        copay_applicable=True,
        surcharge_applicable=True,
    )

    assert result.status == "exact"
    assert result.sgk_base_try == pytest.approx(Decimal("1000.00"))
    assert result.patient_copay_try == pytest.approx(Decimal("400.00"))
    assert result.ilave_ucret_try == pytest.approx(Decimal("200.00"))
    assert result.at_risk_total_try == pytest.approx(Decimal("600.00"))


def test_copay_only_when_surcharge_rate_missing() -> None:
    billed = Decimal("25629.44")
    payable = Decimal("15377.66")
    copay_rate = Decimal("0.40")

    result = decompose_line(
        billed,
        payable,
        copay_rate=copay_rate,
        surcharge_rate=None,
        copay_applicable=True,
        surcharge_applicable=True,
    )

    assert result.status == "copay_only"
    assert result.patient_copay_try == pytest.approx(Decimal("10251.77"))
    assert result.ilave_ucret_try == Decimal("0.00")
    assert result.at_risk_total_try == pytest.approx(Decimal("10251.78"))


def test_surcharge_only_with_zero_copay_rate_is_exact() -> None:
    billed = Decimal("1200.00")
    payable = Decimal("1000.00")
    surcharge_rate = Decimal("0.20")

    result = decompose_line(
        billed,
        payable,
        copay_rate=Decimal("0"),
        surcharge_rate=surcharge_rate,
        copay_applicable=True,
        surcharge_applicable=True,
    )

    assert result.status == "exact"
    assert result.patient_copay_try == Decimal("0.00")
    assert result.ilave_ucret_try == pytest.approx(Decimal("200.00"))
    assert result.at_risk_total_try == pytest.approx(Decimal("200.00"))


def test_missing_inputs_when_rates_absent() -> None:
    result = decompose_line(
        Decimal("500.00"),
        Decimal("400.00"),
        copay_rate=None,
        surcharge_rate=None,
        copay_applicable=False,
        surcharge_applicable=False,
    )

    assert result.status == "missing_inputs"
    assert result.patient_copay_try == Decimal("0.00")
    assert result.ilave_ucret_try == Decimal("0.00")
    assert result.at_risk_total_try == pytest.approx(Decimal("100.00"))


def test_missing_inputs_when_identity_does_not_hold() -> None:
    result = decompose_line(
        Decimal("1000.00"),
        Decimal("400.00"),
        copay_rate=Decimal("0.40"),
        surcharge_rate=Decimal("0.20"),
        copay_applicable=True,
        surcharge_applicable=True,
    )

    assert result.status == "missing_inputs"
    assert result.sgk_base_try is None
