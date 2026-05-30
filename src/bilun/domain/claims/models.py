"""Typed rows and aggregate contracts for exact SUT claim datasets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


Money = Decimal


@dataclass(frozen=True)
class PatientCopayProfile:
    patient_id: str
    sgk_benefit_class: str = "standard"
    veteran_martyr_status: str = "none"
    national_service_status: str = "none"
    elderly_allowance_2022: bool = False
    birth_year: int | None = None


@dataclass(frozen=True)
class ClaimHeader:
    claim_id: str
    patient_id: str
    episode_id: str
    claim_type: str
    facility_tier: str
    provider_type: str
    department: str
    admission_date: date | None
    discharge_date: date | None
    claim_start_date: date
    claim_end_date: date
    primary_icd10: str
    package_candidate: bool
    expected_total_billed_try: Money
    expected_total_payable_try: Money
    expected_denial_reason: str
    scenario_tag: str
    occupational_context: str = "none"


@dataclass(frozen=True)
class ClaimDiagnosis:
    diagnosis_id: str
    claim_id: str
    patient_id: str
    episode_id: str
    icd10_code: str
    is_primary: bool
    diagnosis_role: str
    diagnosis_date: date
    exemption_eligible: bool


@dataclass(frozen=True)
class ProcedureClaimLine:
    procedure_line_id: str
    claim_id: str
    patient_id: str
    episode_id: str
    procedure_date: date
    procedure_code: str
    procedure_name: str
    procedure_category: str
    quantity: int
    unit_price_try: Money
    billed_amount_try: Money
    expected_payable_try: Money
    is_package_included: bool
    package_code: str
    surcharge_applicable: bool
    copay_rate_applicable: bool
    denial_reason_expected: str
    rule_trace_expected: str
    lab_result_id: str = ""
    lab_billing_status: str = ""


@dataclass(frozen=True)
class MaterialClaimLine:
    material_line_id: str
    claim_id: str
    procedure_line_id: str
    patient_id: str
    material_date: date
    material_code: str
    material_name: str
    material_type: str
    specialty_category: str
    quantity: int
    unit_price_try: Money
    billed_amount_try: Money
    expected_payable_try: Money
    is_bundled: bool
    requires_pre_auth: bool
    denial_reason_expected: str
    rule_trace_expected: str


@dataclass(frozen=True)
class DrugClaimLine:
    drug_claim_line_id: str
    prescription_id: str
    claim_id: str
    patient_id: str
    episode_id: str
    drug_claim_date: date
    drug_name: str
    drug_code: str
    barkod: str
    equivalence_group: str
    quantity: int
    unit_price_try: Money
    billed_amount_try: Money
    expected_payable_try: Money
    discount_tier_expected: Money
    denial_reason_expected: str
    rule_trace_expected: str


@dataclass(frozen=True)
class ExpectedRuleOutput:
    expected_output_id: str
    scenario_tag: str
    patient_id: str
    claim_id: str
    line_id: str
    line_type: str
    rule_family: str
    expected_status: str
    expected_payable_try: Money | None
    expected_savings_try: Money | None
    expected_denial_reason: str
    expected_rule_trace: str
    assertion_notes: str


@dataclass(frozen=True)
class ClaimTotals:
    claim_id: str
    patient_id: str
    total_billed_try: Money
    total_expected_payable_try: Money
    procedure_line_count: int
    material_line_count: int
    drug_line_count: int
    lab_billed_line_count: int
    exactness_status: str = "exact"
    source: str = "claim_lines"


@dataclass(frozen=True)
class PatientSUTClaimTotals:
    patient_id: str
    total_billed_try: Money
    total_expected_payable_try: Money
    claim_count: int
    procedure_line_count: int
    material_line_count: int
    drug_line_count: int
    lab_billed_line_count: int
    exactness_status: str = "exact"
    source: str = "claim_lines"
