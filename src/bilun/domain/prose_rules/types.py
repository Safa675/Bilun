"""Shared types for SUT prose rule evaluators."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from src.bilun.domain.sut.clause_reference import SOURCE_SUT_CLAUSE

CareSetting = Literal["outpatient", "inpatient"]
PaymentMethod = Literal["package", "itemized", "unknown", "overridable"]
PaymentMethodKind = Literal[
    "DRG_MANDATORY",
    "DRG_OVERRIDABLE",
    "ITEMIZED",
    "MISSING_INPUTS",
    "NOT_IN_SUT",
]
PatientCopayProfile = Literal["sgk_income_recipient", "other"]


@dataclass(frozen=True)
class ProseRuleTrace:
    """Traceability back to SUT prose and decision table.

    Phase 2 provenance fields (additive): ``source_type`` classifies the
    cite (``sut_clause`` vs non-SUT sources such as ``el_kitabi`` /
    ``algoritma_rehberi`` / ``kanun`` / ``rehber``) and ``clause_ref``
    carries the structured ``SutClauseReference.to_dict()`` payload when
    one is attached to the finding. Defaults keep every existing
    constructor working unchanged.
    """

    rule_id: str
    sut_section: str
    rule_set_id: str
    detail: str
    source_type: str = SOURCE_SUT_CLAUSE
    clause_ref: dict | None = None


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
    # Structured message contract (§2.2 surface): consumers localize via
    # message_code + message_params instead of regex-parsing ``detail``.
    message_code: str = ""
    message_params: dict | None = None


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


SAVINGS_CATEGORY_SGK_UPLIFT = "sgk_uplift"
SAVINGS_CATEGORY_COMPLIANCE = "compliance_adjustment"
SAVINGS_CATEGORY_COPAY_WAIVER = "patient_copay_waiver"
SAVINGS_CATEGORY_AUDIT_EXPOSURE = "audit_exposure"
SAVINGS_CATEGORY_CAPTURE_GAP = "capture_gap"
SAVINGS_CATEGORY_PACKAGE_ADEQUACY = "package_adequacy_review"
SAVINGS_CATEGORY_MEDULA_PLAYBOOK = "medula_playbook"
SAVINGS_BASIS_SOURCED = "sourced"
SAVINGS_BASIS_OPTIONAL_OVERRIDE = "optional_override"
SAVINGS_BASIS_HEURISTIC = "heuristic"
