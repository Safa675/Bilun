"""Shared types for SUT prose rule evaluators."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

CareSetting = Literal["outpatient", "inpatient"]
PaymentMethod = Literal["package", "itemized", "unknown", "overridable"]
PaymentMethodKind = Literal[
    "DRG_MANDATORY",
    "DRG_OVERRIDABLE",
    "ITEMIZED",
    "NOT_IN_SUT",
]
PatientCopayProfile = Literal["sgk_income_recipient", "other"]


@dataclass(frozen=True)
class ProseRuleTrace:
    """Traceability back to SUT prose and decision table."""

    rule_id: str
    sut_section: str
    rule_set_id: str
    detail: str


@dataclass(frozen=True)
class PaymentMethodResult:
    procedure_code: str
    payment_method: PaymentMethod
    kind: PaymentMethodKind
    in_ek2b: bool
    in_ek2c: bool
    has_star: bool
    bill_materials_separately: bool
    bill_drugs_separately: bool
    visit_fee_annex: str | None
    trace: ProseRuleTrace
    payment_method_tr: str = ""
    allowed_methods: tuple[PaymentMethod, ...] = ()


@dataclass(frozen=True)
class PaymentMethodCompliance:
    procedure_code: str
    mandated_method: PaymentMethod
    kind: PaymentMethodKind
    billed_as_package: bool
    is_compliant: bool
    detail: str
    trace: ProseRuleTrace


@dataclass(frozen=True)
class SessionProcedureFactor:
    procedure_code: str
    point_factor: float
    is_primary: bool
    trace: ProseRuleTrace


@dataclass(frozen=True)
class SessionPricingResult:
    factors: tuple[SessionProcedureFactor, ...]
    rule_id: str
    sut_section: str
    metadata: dict[str, Any] = field(default_factory=dict)
