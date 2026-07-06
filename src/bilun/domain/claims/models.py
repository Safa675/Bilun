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
    copay_rate: Money | None = None
    surcharge_rate: Money | None = None
    lab_result_id: str = ""
    lab_billing_status: str = ""
    procedure_specialty_code: str = ""


@dataclass(frozen=True)
class PerformedProcedureLine:
    """EMR/OR log row for a procedure performed but not necessarily submitted."""

    performed_line_id: str
    claim_id: str
    patient_id: str
    episode_id: str
    service_date: date
    procedure_code: str
    procedure_name: str
    source: str = "emr"


@dataclass(frozen=True)
class MedulaRejectionEvent:
    """MEDULA gateway rejection snapshot linked to a claim."""

    rejection_event_id: str
    claim_id: str
    patient_id: str
    episode_id: str
    medula_stage: str
    sonuc_kodu: str
    hata_kodu: str = ""
    hata_mesaji: str = ""
    rejection_timestamp: date | None = None
    related_procedure_code: str = ""
    related_procedure_line_id: str = ""
    # Discriminator + id of the offending line the rejection is about.
    # `related_line_type` ∈ {"procedure", "material", "drug", "claim", ""};
    # `related_line_id` is the line id of that type on the same claim.
    # For materials/drugs these are the material_line_id / drug_claim_line_id,
    # which the legacy related_procedure_* fields could not express.
    related_line_type: str = ""
    related_line_id: str = ""


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
    # Phase 2.1c/d: EK-3B-1 / EK-3B-2 regulatory flags, derived at build time
    # from the canonical annex matchers (the same ones check_bundling_violations
    # and check_exclusion_violations use). Distinct from is_bundled, which is a
    # broader pricing/package-bundle concept sourced from the CSV column.
    # is_ek3b1_bundled = on the EK-3B-1 bundled-consumables annex (regulatory).
    # is_excluded      = on the EK-3B-2 non-reimbursable annex (regulatory).
    # Defaults False so existing construction sites don't break; the build-time
    # enricher (dataset_builder._enrich_material_regulatory_flags) populates
    # them. See plans/refactor/rule-encoding-gap-closure-roadmap.md Phase 2.1.
    is_ek3b1_bundled: bool = False
    is_excluded: bool = False
    # W2.2: dental evaluator flags (optional, surfaced from dict input by the
    # adapter when present). Enables rules 2-3 of dental_2_4_1.json.
    medical_necessity_board_report: bool | None = None
    treating_physician_different_from_board_signatory: bool | None = None
    patient_in_first_degree_relative_of_physician: bool | None = None
    titubb_registered: bool | None = None
    uts_registered: bool | None = None
    procurement_record_incomplete: bool = False
    procedure_not_reimbursed: bool = False
    foreign_facility: bool = False
    facility_procedure_restriction_violation: bool = False
    diagnosis_bundled_no_separate_bill: bool = False
    procurement_price_refs_insufficient: bool = False
    medula_code_undefined_on_date: bool = False
    barcode_sut_mismatch: bool = False
    diagnosis_bundled_material_scope: bool = False
    cross_branch_material_unauthorized: bool = False
    ortez_protez_contract_billing_invalid: bool = False
    maintenance_cost_exceeds_sut_cap: bool = False
    protez_repair_documentation_incomplete: bool = False
    warranty_maintenance_procedure_incomplete: bool = False
    ortez_protez_maintenance_unverified: bool = False
    ihale_dts_mandatory_fields_incomplete: bool = False
    supplier_contract_pricing_path: bool = False
    ek3c_inpatient_external_supply_invalid: bool = False
    ek3c_list_price_missing: bool = False
    ek3_quality_documentation_incomplete: bool = False
    ek3c_miat_early_renewal_unauthorized: bool = False
    ek3c_custom_order_billing_invalid: bool = False
    ek3c_medical_appropriateness_incomplete: bool = False
    ek3c_custom_garment_contract_invalid: bool = False
    ek3c_force_majeure_renewal_claim: bool = False
    ek3c_outpatient_material_scope: bool = False
    inpatient_material_facility_supply_violation: bool = False
    non_reimbursed_inpatient_patient_charge: bool = False
    lab_material_separate_billing: bool = False
    shared_consumable_wrong_branch_billing: bool = False
    material_prescription_quantity_exceeded: bool = False
    material_report_prescription_invalid: bool = False
    material_invoice_documentation_incomplete: bool = False
    diagnosis_package_material_unbundled: bool = False
    emergency_uncontracted_facility_material: bool = False
    unlisted_material_surcharge_billing: bool = False
    wheelchair_dual_prescription_invalid: bool = False
    outpatient_contract_center_supply_required: bool = False
    child_growth_miat_renewal_claim: bool = False
    facility_contract_material_supply_scope: bool = False
    ismarlama_device_component_titubb_incomplete: bool = False
    titubb_uts_barcode_documentation_missing: bool = False
    specialty_wound_care_excluded: bool = False
    skin_substitute_non_burn_use: bool = False
    immunobullous_wound_care_patient_supply: bool = False
    immunobullous_wound_care_non_moh_facility: bool = False
    optical_patient_access_deadline_missed: bool = False
    emergency_poliklinik_glasses_claim: bool = False
    optical_lens_upgrade_difference_claim: bool = False
    optical_telescopic_with_cap_claim: bool = False
    contact_lens_with_spectacle_billing: bool = False
    tv5680_with_tv1080_tv1090_combo: bool = False
    hearing_in_ear_under_age_limit: bool = False
    hearing_ear_mold_with_initial_device: bool = False
    cochlear_implant_under_12_months: bool = False
    speech_processor_under_5_years: bool = False
    brainstem_implant_under_12_months: bool = False
    incontinence_hydrophilic_catheter_diaper_only: bool = False
    tissue_bank_unauthorized_product: bool = False
    bone_stimulator_combined_use: bool = False
    bone_stimulator_hypertrophic_nonunion: bool = False
    bone_stimulator_with_autograft: bool = False
    bone_stimulator_benign_tumor_use: bool = False
    open_physis_primary_fracture_graft: bool = False
    adult_primary_fracture_bone_stimulator: bool = False
    hip_arthroplasty_graft_claim: bool = False
    graft_allograft_xenograft_combined: bool = False
    primary_ligament_tendon_injury_graft: bool = False
    glucose_meter_early_renewal: bool = False
    wheelchair_stand_device_duplicate_billing: bool = False
    stand_up_wheelchair_early_renewal: bool = False
    paraplegia_standing_table_over_age_limit: bool = False
    paraplegia_wheelchair_separate_billing: bool = False
    spinal_mobility_device_duplicate_billing: bool = False
    returned_device_without_kurum_approval: bool = False
    nimv_heated_humidifier_separate_billing: bool = False
    dental_prosthesis_adhesive_claim: bool = False
    dual_mesh_primary_hernia_repair: bool = False


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
    copay_rate: Money | None = None
    surcharge_rate: Money | None = None
    drug_specialty_board_report_present: bool | None = None
    drug_report_duration_months: int | None = None
    drug_inpatient_supply: bool | None = None
    prescriber_specialty: str | None = None
    # §4.2.33 anti-VEGF dose protocol (intravitreal injection counts)
    annual_application_count: int | None = None
    is_loading_phase: bool | None = None
    # §4.2.14.C oncology biomarker + prior-therapy gating (Bucket B)
    # biomarkers: [{"marker": "HER2", "status": "3+"}, {"marker": "ER", "status": "positive"}]
    biomarkers: tuple[dict[str, str], ...] | None = None
    # prior_therapies: [{"drug_or_class": "imatinib", "outcome": "resistant"}]
    prior_therapies: tuple[dict[str, str], ...] | None = None


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
