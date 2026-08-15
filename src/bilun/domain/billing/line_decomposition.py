"""Claim-line copay vs ilave ücret decomposition (SUT §1.8 / §1.9)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from functools import lru_cache
from typing import Literal

from src.bilun.domain.claims.models import DrugClaimLine, ProcedureClaimLine
from src.bilun.domain.money import quantize_money, quantize_money_or_zero
from src.bilun.domain.sut.clause_reference import (
    RULE_TYPE_SURCHARGE_EXEMPTION,
    RULE_TYPE_SURCHARGE_PROHIBITION,
    SutClauseReference,
    sut_clause_reference,
)

LineDecompositionStatus = Literal["exact", "copay_only", "missing_inputs"]

DEFAULT_IDENTITY_TOLERANCE = Decimal("0.10")

# Track E clause cites for the surcharge (ilave ücret) rules. Verified against
# data/gazette/sut_clause_coverage.parquet: ilave ücret is legislated under
# SUT §1.9 (not §2.4.4 — that section is "Diğer bazı tetkik ve tedavi
# yöntemleri" and no 2.4.4 sub-clause carries ilave-ücret wording).
# §1.9.1 scopes ilave ücret to EK-2/B + EK-2/C list prices, so drugs (billed
# via EK-4/A) can never carry one; the statutory anchor is 5510 md.73.
# §1.9.3 lists services from which no ilave ücret may be taken: bent (a)
# acil haller, bent (ç) kanser tedavisi.
_DRUG_SURCHARGE_SCOPE_COORDINATE = "1.9.1"
_EMERGENCY_SURCHARGE_EXEMPTION_COORDINATE = "1.9.3.a"
_CANCER_SURCHARGE_EXEMPTION_COORDINATE = "1.9.3.ç"
_DRUG_SURCHARGE_PROHIBITION_LAW = "5510 Sayılı Kanun Madde 73"


@lru_cache(maxsize=1)
def drug_surcharge_prohibition_clause() -> SutClauseReference:
    """SUT §1.9.1 + 5510 md.73: an ilave ücret on drugs is legally prohibited."""
    return sut_clause_reference(
        _DRUG_SURCHARGE_SCOPE_COORDINATE,
        rule_type=RULE_TYPE_SURCHARGE_PROHIBITION,
        statutory_law=_DRUG_SURCHARGE_PROHIBITION_LAW,
    )


@lru_cache(maxsize=1)
def emergency_surcharge_exemption_clause() -> SutClauseReference:
    """SUT §1.9.3(a): no ilave ücret on services delivered as acil haller."""
    return sut_clause_reference(
        _EMERGENCY_SURCHARGE_EXEMPTION_COORDINATE,
        rule_type=RULE_TYPE_SURCHARGE_EXEMPTION,
    )


@lru_cache(maxsize=1)
def cancer_surcharge_exemption_clause() -> SutClauseReference:
    """SUT §1.9.3(ç): no ilave ücret on kanser tedavisi."""
    return sut_clause_reference(
        _CANCER_SURCHARGE_EXEMPTION_COORDINATE,
        rule_type=RULE_TYPE_SURCHARGE_EXEMPTION,
    )


@dataclass(frozen=True)
class LineDecomposition:
    """Per-line split of patient-side amounts vs SGK payable."""

    status: LineDecompositionStatus
    billed_try: Decimal
    expected_payable_try: Decimal
    sgk_base_try: Decimal | None
    patient_copay_try: Decimal
    ilave_ucret_try: Decimal
    at_risk_total_try: Decimal
    ilave_ucret_status: str = "none"
    surcharge_clause: SutClauseReference | None = None


def _rate_decimal(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return quantize_money(value)


def _identity_holds(
    *,
    at_risk_total: Decimal,
    patient_copay: Decimal,
    ilave_ucret: Decimal,
    tolerance: Decimal,
) -> bool:
    return abs(at_risk_total - (patient_copay + ilave_ucret)) <= tolerance


def decompose_line(
    billed: Decimal,
    expected_payable: Decimal,
    *,
    copay_rate: Decimal | None,
    surcharge_rate: Decimal | None,
    copay_applicable: bool,
    surcharge_applicable: bool,
    tolerance: Decimal = DEFAULT_IDENTITY_TOLERANCE,
) -> LineDecomposition:
    """Split billed vs SGK payable into waivable copay and ilave ücret.

    Accounting identity (when claim-exact rates are present):

        sgk_base = expected_payable / (1 - copay_rate)   [when copay applies]
        patient_copay = sgk_base * copay_rate
        ilave_ucret = sgk_base * surcharge_rate            [when surcharge applies]
        billed ≈ expected_payable + patient_copay + ilave_ucret
    """

    billed_q = quantize_money_or_zero(billed)
    payable_q = quantize_money_or_zero(expected_payable)
    at_risk_total = quantize_money_or_zero(
        billed_q - payable_q if billed_q > payable_q else Decimal("0")
    )

    copay_rate_q = _rate_decimal(copay_rate) if copay_applicable else None
    surcharge_rate_q = _rate_decimal(surcharge_rate) if surcharge_applicable else None

    has_copay_rate = copay_applicable and copay_rate_q is not None
    has_surcharge_rate = surcharge_applicable and surcharge_rate_q is not None

    if not has_copay_rate and not has_surcharge_rate:
        return LineDecomposition(
            status="missing_inputs",
            billed_try=billed_q,
            expected_payable_try=payable_q,
            sgk_base_try=None,
            patient_copay_try=Decimal("0.00"),
            ilave_ucret_try=Decimal("0.00"),
            at_risk_total_try=at_risk_total,
        )

    sgk_base: Decimal | None = None
    patient_copay = Decimal("0.00")
    ilave_ucret = Decimal("0.00")

    if has_copay_rate and copay_rate_q is not None and copay_rate_q > 0:
        denominator = Decimal("1") - copay_rate_q
        if denominator <= 0:
            return _missing_result(billed_q, payable_q, at_risk_total)
        sgk_base = quantize_money_or_zero(payable_q / denominator)
        patient_copay = quantize_money_or_zero(sgk_base * copay_rate_q)
    else:
        sgk_base = payable_q

    if has_surcharge_rate and surcharge_rate_q is not None and surcharge_rate_q > 0:
        if sgk_base is None:
            return _missing_result(billed_q, payable_q, at_risk_total)
        ilave_ucret = quantize_money_or_zero(sgk_base * surcharge_rate_q)

    if not _identity_holds(
        at_risk_total=at_risk_total,
        patient_copay=patient_copay,
        ilave_ucret=ilave_ucret,
        tolerance=tolerance,
    ):
        return _missing_result(billed_q, payable_q, at_risk_total)

    if has_copay_rate and has_surcharge_rate:
        status: LineDecompositionStatus = "exact"
    elif has_copay_rate:
        status = "copay_only"
    else:
        status = "missing_inputs"

    return LineDecomposition(
        status=status,
        billed_try=billed_q,
        expected_payable_try=payable_q,
        sgk_base_try=sgk_base,
        patient_copay_try=patient_copay,
        ilave_ucret_try=ilave_ucret,
        at_risk_total_try=at_risk_total,
    )


def decompose_procedure_line(
    line: ProcedureClaimLine,
    *,
    cancer_exempt: bool = False,
    emergency_exempt: bool = False,
) -> LineDecomposition:
    """Decompose a procedure line and annotate its ilave ücret status.

    The money math is unchanged (``decompose_line``); the annotation only
    links the governing SUT §1.9.3 surcharge-exemption clause when a
    surcharge applies.
    """

    base = decompose_line(
        line.billed_amount_try,
        line.expected_payable_try,
        copay_rate=line.copay_rate,
        surcharge_rate=line.surcharge_rate,
        copay_applicable=line.copay_rate_applicable,
        surcharge_applicable=line.surcharge_applicable,
    )
    if not (line.surcharge_applicable and line.surcharge_rate is not None):
        return base
    if cancer_exempt:
        return replace(
            base,
            ilave_ucret_status="cancer_exempt",
            surcharge_clause=cancer_surcharge_exemption_clause(),
        )
    if emergency_exempt:
        return replace(
            base,
            ilave_ucret_status="emergency_exempt",
            surcharge_clause=emergency_surcharge_exemption_clause(),
        )
    return replace(base, ilave_ucret_status="applicable")


def decompose_drug_line(line: DrugClaimLine) -> LineDecomposition:
    """Decompose a drug line; the drug surcharge prohibition is unconditional.

    SUT §1.9.1 + 5510 md.73: an ilave ücret on drugs is legally prohibited,
    so the annotation applies even when decomposition returns missing_inputs.
    The money math is unchanged (``decompose_line``).
    """

    copay_rate = line.copay_rate
    if copay_rate is None and line.discount_tier_expected is not None:
        copay_rate = line.discount_tier_expected
    base = decompose_line(
        line.billed_amount_try,
        line.expected_payable_try,
        copay_rate=copay_rate,
        surcharge_rate=line.surcharge_rate,
        copay_applicable=copay_rate is not None,
        surcharge_applicable=line.surcharge_rate is not None,
    )
    return replace(
        base,
        ilave_ucret_status="drug_prohibited",
        surcharge_clause=drug_surcharge_prohibition_clause(),
    )


def aggregate_decomposition_status(
    statuses: list[LineDecompositionStatus],
) -> LineDecompositionStatus:
    if not statuses:
        return "missing_inputs"
    if any(status == "exact" for status in statuses):
        return "exact"
    if all(status == "copay_only" for status in statuses):
        return "copay_only"
    return "missing_inputs"


def _missing_result(
    billed: Decimal,
    payable: Decimal,
    at_risk_total: Decimal,
) -> LineDecomposition:
    return LineDecomposition(
        status="missing_inputs",
        billed_try=billed,
        expected_payable_try=payable,
        sgk_base_try=None,
        patient_copay_try=Decimal("0.00"),
        ilave_ucret_try=Decimal("0.00"),
        at_risk_total_try=at_risk_total,
    )
