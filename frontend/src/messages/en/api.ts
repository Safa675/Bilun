const api = {
  exactness: {
    missingInputs: "Missing exact inputs: {inputs}.",
    reasonWithInputs: "{reason} Missing exact inputs: {inputs}.",
  },
  requiredInput: {
    billed_procedure_codes: "billed procedure codes",
    procedure_dates: "procedure dates",
    procedure_claim_dates: "claim dates",
    itemized_billed_procedure_lines: "itemized billed procedure lines",
    episode_package_eligibility_context: "package eligibility context",
    admission_dates: "admission dates",
    dispensed_drug_claim_lines: "dispensed drug claim lines",
    drug_claim_dates: "drug claim dates",
    billed_drug_amounts: "billed drug amounts",
    billed_material_codes: "billed material codes",
    exact_claim_headers: "exact claim headers",
    itemized_material_claim_lines: "itemized material claim lines",
    claim_lines: "claim lines",
    pricing_status: "pricing status",
    exactness_status: "exactness status",
    data_source: "data source",
    "data_source.is_synthetic": "data source synthetic flag",
    "data_source.mode": "data source mode",
    BILUN_DATA_MODE: "BILUN_DATA_MODE",
    BILUN_CLAIMS_DIR: "BILUN_CLAIMS_DIR",
    BILUN_CLEAN_DIR: "BILUN_CLEAN_DIR",
  },
  unavailableReason: {
    copayOptimizationUnavailable:
      "Copay optimization requires exact billed procedure codes, claim dates, dispensed drug claim lines, and billed amounts, which are not available in the active SUT runtime inputs.",
    materialsPartialUnavailable:
      "EK-3C-1 pre-authorization and EK-3C-2 MIAT require billed material claim lines. Partial mode shows EK-3 specialty price benchmarks (P90) only — not catalog pre-auth or MIAT flags.",
    billingReportPartialUnavailable:
      "Billing report totals combine exact and non-exact sections. Use section-level exactness metadata before treating aggregate savings as exact.",
    cohortRecoveryPartialUnavailable:
      "Revenue recovery totals aggregate billing reports that include non-exact sections. Treat cohort savings as mixed exactness unless every patient report is exact.",
    billingStrategyUnavailable:
      "Billing strategy comparison requires exact itemized billed procedure lines, package eligibility context, and admission dates, which are not available in the active SUT runtime inputs.",
    drgCostUnavailable:
      "DRG cost aggregation requires exact claim headers and itemized billed procedure, material, and drug claim lines.",
    drgEpisodeMissingAdmissionDate: "Missing admission date",
    drgEpisodeNoHistoricalPrice:
      "No exact historical DRG price available for admission date {admissionDate}",
    drgPartialExactUnavailable:
      "One or more episodes are missing admission dates or exact historical DRG prices.",
    drgUnknownDateUnavailable:
      "Episode pricing unavailable because admission dates or exact historical DRG prices are missing.",
    surchargeExposureUnavailable:
      "Surcharge compliance requires exact billed procedure codes and procedure dates, which are not available in the active SUT runtime inputs.",
    copayRateExposureUnavailable:
      "EK-2C-1 copay rate compliance requires exact billed procedure codes and claim dates, which are not available in the active SUT runtime inputs.",
    drgUnbundlingUnavailable:
      "DRG unbundling risk requires exact billed procedure lines, package eligibility context, and dated package pricing, which are not available in the active SUT runtime inputs.",
    missingExactnessMetadata: "Exactness metadata was not provided by the Bilun payload.",
    missingPricingMetadata: "Pricing exactness metadata was not provided by the Bilun payload.",
    missingDrgPricingMetadata: "DRG pricing exactness metadata was not provided by the Bilun payload.",
    exactClaimDatasetUnavailable: "Exact claim dataset is not available for this deployment.",
    exactClaimLinesMissingForPatient: "Exact claim lines are missing for this patient.",
    exactClaimPatientTotalsMissing: "Exact patient claim totals are missing.",
    bilunDataSourceMetadataMissing: "Bilun data-source metadata is missing.",
    bilunDataSourceConfigInvalid: "Bilun data-source configuration is invalid.",
    bilunDataSourceMetadataInvalid: "Bilun data-source metadata is invalid.",
    syntheticDemoRequiresIsSyntheticTrue: "Synthetic demo mode requires is_synthetic=true.",
    realClaimsRequiresIsSyntheticFalse: "Real-claims mode requires is_synthetic=false.",
    bilunDataSourceModeMissingOrInvalid: "Bilun data-source mode is missing or invalid.",
  },
  methodology: {
    billingStrategyReviewDetail:
      "Review EK-2C package vs itemized billing eligibility for ICD-10 chapter {chapter}.",
    surchargeExposureExact:
      "Uses exact dated procedure claim lines joined to EK-2/G (ek2g_no_surcharge.parquet) for surcharge prohibitions; n_applicable_procedures counts catalog-prohibited lines (ilave ücret must not be charged). Claim-line flags are validated against the catalog.",
    copayRateExposureExact:
      "Uses exact dated claim lines for EK-2C-1 listed procedures (ek2c1_copay_rates.parquet); compares implied copay % (100 − SGK payable/billed) to the gazette mandated rate (§2.2, not §1.8 general copay).",
    copayExemptionsCohort:
      "Composable copay exemption: EK-1A chronic ICD-10 ranges plus status/visit rules when patient profiles and claim visit types are available. The EK-2C-1 copay rate list is evaluated separately.",
    surchargeExposureCohortExact:
      "Aggregated exact surcharge_applicable procedure flags from claim lines across the active cohort.",
    copayRateExposureCohortExact:
      "Aggregated exact EK-2C-1 list procedure flags from claim lines across the active cohort.",
    drgUnbundlingPatient:
      "Uses exact claim lines with SUT §2.2 prose rules: package-included bundling, payment-method compliance (EK-2/B vs EK-2/C), same-session point factors (§2.2.2.B), and blood-component partial billing limits.",
    drgUnbundlingCohort:
      "Aggregated per-patient DRG unbundling findings from exact claim lines with SUT §2.2 prose rule checks.",
    temporalPriceValidation:
      "Loads the full temporal history of EK-2B (fee-for-service procedure points) and EK-2C (diagnosis-based package points) across all ingested gazette amendment dates. Compares the earliest and latest price for each code to detect changes. 100% real gazette data from official SUT amendments.",
  },
  validation: {
    bundlingViolationMessage:
      "'{materialName}' is bundled into the procedure price (EK-3B-1: {category}, match={matchKind}). Cannot be billed separately.",
    bundlingViolationSavingsSuffix: " Potential savings: {billedAmount} TRY.",
    exclusionViolationMessage:
      "'{materialName}' is non-reimbursable per EK-3B-2 ({label}, match={matchKind}). SGK will not cover {billedAmount} TRY.",
    noMaterialsToValidate: "No materials to validate.",
    claimValidSummary: "Claim {claimId}: VALID",
    claimInvalidSummary: "Claim {claimId}: INVALID",
    materialsTotalSummary: "{materialCount} materials, {totalAmount} TRY total",
    bundlingViolationsSummary:
      "{violationCount} bundling violation(s), savings: {savingsAmount} TRY",
    exclusionViolationsSummary:
      "{violationCount} exclusion violation(s), risk: {riskAmount} TRY",
    validatedInSummary: "validated in {elapsedMs}ms",
    summarySeparator: " | ",
  },
  provenance: {
    dataSourceUnavailableLabel: "Bilun data source unavailable",
    dataSourceMissingNotice:
      "Bilun data-source provenance was not provided; treat claim-derived values as unavailable until a build supplies provenance.",
    syntheticDemoLabel: "Synthetic Bilun demo claim data",
    hospitalClaimDataLabel: "Hospital claim data",
    syntheticDemoNotice: "Demo data only. Rule calculations are exact for these synthetic claim lines.",
    realClaimsNotice: "Hospital billing claim-line exports supplied by deployment configuration.",
  },
  consistencyWarning: {
    missingPriceProvenance: "Missing exact price provenance for one record.",
    needsProvenanceReview: "Needs provenance review.",
  },
  health: {
    healthy: "Healthy",
  },
  unknownViolation: "Unknown violation",
  unknownReason: "Unknown reason",
  unknownMethodology: "Methodology details unavailable",
  unknownProvenance: "Provenance details unavailable",
  unknownWarning: "Unknown consistency warning",
  unknownHealth: "Health details unavailable",
  unknownApiText: "Details unavailable",
  noMessage: "—",
  paymentMethodKind: {
    drg_mandatory: "DRG — mandatory package",
    drg_overridable: "DRG — overridable",
    itemized: "Itemized",
    missing_inputs: "Missing inputs",
    not_in_sut: "Not in SUT",
  },
} as const;

export default api;
