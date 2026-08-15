"""Unit tests for claim-line copay / ilave decomposition."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.billing.line_decomposition import (
    decompose_drug_line,
    decompose_line,
    decompose_procedure_line,
)
from src.bilun.domain.claims.models import DrugClaimLine, ProcedureClaimLine
from src.bilun.domain.sut.clause_reference import (
    RULE_TYPE_SURCHARGE_EXEMPTION,
    RULE_TYPE_SURCHARGE_PROHIBITION,
)

pytestmark = pytest.mark.unit


def _drug_line(
    *,
    billed: Decimal,
    payable: Decimal,
    copay_rate: Decimal | None = None,
    surcharge_rate: Decimal | None = None,
) -> DrugClaimLine:
    return DrugClaimLine(
        drug_claim_line_id="DL-1",
        prescription_id="RX-1",
        claim_id="F-TEST-100",
        patient_id="PT-1",
        episode_id="EP-1",
        drug_claim_date=date(2026, 3, 10),
        drug_name="Test Drug",
        drug_code="P-TEST",
        barkod="",
        equivalence_group="",
        quantity=1,
        unit_price_try=billed,
        billed_amount_try=billed,
        expected_payable_try=payable,
        discount_tier_expected=Decimal("0"),
        denial_reason_expected="",
        rule_trace_expected="",
        copay_rate=copay_rate,
        surcharge_rate=surcharge_rate,
    )


def _procedure_line(
    *,
    billed: Decimal,
    payable: Decimal,
    copay_rate: Decimal | None,
    surcharge_rate: Decimal | None,
    surcharge_applicable: bool,
) -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id="PL-1",
        claim_id="F-TEST-100",
        patient_id="PT-1",
        episode_id="EP-1",
        procedure_date=date(2026, 3, 10),
        procedure_code="P100000",
        procedure_name="Procedure",
        procedure_category="paket",
        quantity=1,
        unit_price_try=billed,
        billed_amount_try=billed,
        expected_payable_try=payable,
        is_package_included=False,
        package_code="",
        surcharge_applicable=surcharge_applicable,
        copay_rate_applicable=copay_rate is not None,
        denial_reason_expected="",
        rule_trace_expected="",
        copay_rate=copay_rate,
        surcharge_rate=surcharge_rate,
    )


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


def test_drug_line_is_drug_prohibited_with_resolved_surcharge_clause() -> None:
    line = _drug_line(
        billed=Decimal("100.00"),
        payable=Decimal("60.00"),
        copay_rate=Decimal("0.40"),
    )

    result = decompose_drug_line(line)

    # Money math unchanged: copay-only split of the 40 TRY gap.
    assert result.status == "copay_only"
    assert result.patient_copay_try == pytest.approx(Decimal("40.00"))
    assert result.ilave_ucret_try == Decimal("0.00")
    assert result.at_risk_total_try == pytest.approx(Decimal("40.00"))

    # SUT §1.9.1 + 5510 md.73 drug surcharge prohibition annotation.
    assert result.ilave_ucret_status == "drug_prohibited"
    assert result.surcharge_clause is not None
    assert result.surcharge_clause.clause_coordinate == "1.9.1"
    assert result.surcharge_clause.clause_key  # resolved, non-empty
    assert result.surcharge_clause.clause_key.startswith("1.9.1#")
    assert result.surcharge_clause.rule_type == RULE_TYPE_SURCHARGE_PROHIBITION
    assert result.surcharge_clause.statutory_law == "5510 Sayılı Kanun Madde 73"


def test_drug_line_is_drug_prohibited_even_with_missing_inputs() -> None:
    # Billed/payable gap far exceeds the copay implied by the rate, so the
    # accounting identity fails and decomposition returns missing_inputs.
    line = _drug_line(
        billed=Decimal("1000.00"),
        payable=Decimal("100.00"),
        copay_rate=Decimal("0.20"),
    )

    result = decompose_drug_line(line)

    assert result.status == "missing_inputs"
    assert result.sgk_base_try is None
    assert result.ilave_ucret_status == "drug_prohibited"
    assert result.surcharge_clause is not None
    assert result.surcharge_clause.clause_key  # resolved, non-empty
    assert result.surcharge_clause.rule_type == RULE_TYPE_SURCHARGE_PROHIBITION


def test_procedure_line_cancer_exempt_with_surcharge() -> None:
    line = _procedure_line(
        billed=Decimal("1200.00"),
        payable=Decimal("600.00"),
        copay_rate=Decimal("0.40"),
        surcharge_rate=Decimal("0.20"),
        surcharge_applicable=True,
    )

    result = decompose_procedure_line(line, cancer_exempt=True)

    # Money math unchanged vs the exact split.
    assert result.status == "exact"
    assert result.patient_copay_try == pytest.approx(Decimal("400.00"))
    assert result.ilave_ucret_try == pytest.approx(Decimal("200.00"))

    assert result.ilave_ucret_status == "cancer_exempt"
    assert result.surcharge_clause is not None
    assert result.surcharge_clause.clause_coordinate == "1.9.3.ç"
    assert result.surcharge_clause.clause_key  # resolved, non-empty
    assert result.surcharge_clause.rule_type == RULE_TYPE_SURCHARGE_EXEMPTION


def test_procedure_line_emergency_exempt_with_surcharge() -> None:
    line = _procedure_line(
        billed=Decimal("1200.00"),
        payable=Decimal("600.00"),
        copay_rate=Decimal("0.40"),
        surcharge_rate=Decimal("0.20"),
        surcharge_applicable=True,
    )

    result = decompose_procedure_line(line, emergency_exempt=True)

    assert result.ilave_ucret_status == "emergency_exempt"
    assert result.surcharge_clause is not None
    assert result.surcharge_clause.clause_coordinate == "1.9.3.a"
    assert result.surcharge_clause.rule_type == RULE_TYPE_SURCHARGE_EXEMPTION


def test_procedure_line_applicable_surcharge_without_exemption() -> None:
    line = _procedure_line(
        billed=Decimal("1200.00"),
        payable=Decimal("600.00"),
        copay_rate=Decimal("0.40"),
        surcharge_rate=Decimal("0.20"),
        surcharge_applicable=True,
    )

    result = decompose_procedure_line(line)

    # A lawful surcharge is annotated "applicable" without an exemption clause.
    assert result.ilave_ucret_status == "applicable"
    assert result.surcharge_clause is None


def test_procedure_line_without_surcharge_is_none() -> None:
    line = _procedure_line(
        billed=Decimal("1200.00"),
        payable=Decimal("600.00"),
        copay_rate=Decimal("0.40"),
        surcharge_rate=None,
        surcharge_applicable=False,
    )

    result = decompose_procedure_line(line, cancer_exempt=True, emergency_exempt=True)

    assert result.ilave_ucret_status == "none"
    assert result.surcharge_clause is None
