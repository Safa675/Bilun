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
    drugIndicationCorpusNoncoverage:
      "Drug is not covered by the encoded Drug Indication corpus; manual SUT review is required and no financial value is inferred.",
    drugIndicationIngredientUnknown:
      "The active ingredient of a drug outside the encoded Drug Indication corpus could not be determined, so the SUT text could not be checked; manual SUT review is required and no financial value is inferred.",
    drugIndicationNameCheck:
      "Drug lines outside the encoded Drug Indication corpus were checked only by active ingredient name against the SUT text: no clause names the ingredient, but restrictions written for a whole drug class without naming the ingredient cannot be detected. No manual review is requested by default and no financial value is inferred.",
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
  paymentMethodKind: {
    drg_mandatory: "DRG — mandatory package",
    drg_overridable: "DRG — overridable",
    itemized: "Itemized",
    missing_inputs: "Missing inputs",
    not_in_sut: "Not in SUT",
  },
  billingProse: {
    yatakStandardWithSurgery:
      "Standard bed (510010): {days} billable bed-day(s) (gross LOS {grossDays} day(s) at {rate} TRY/day, surgery day {surgeryDay} bundled into EK-2/C package) = {amount} TRY (inclusive LOS, discharge day billed).",
    yatakStandard:
      "Standard bed (510010): {days} billable bed-day(s) (gross LOS {grossDays} day(s) at {rate} TRY/day) = {amount} TRY (inclusive LOS, discharge day billed).",
    catalogMiat: "Catalog MIAT period: {period} — verify interval vs patient history",
    preauthNote:
      "EK-3C-1 — medical appropriateness (tıbbi uygunluk) required before SGK submission (§3.1.2)",
    preauthFlagNote:
      "Pre-authorization review requested by the material-line input flag; EK-3C-1 catalog membership not verified",
    bundledEk3b1: "Bundled material billed separately — review package inclusion (EK-3B-1)",
    bundledPackageFlag:
      "Marked as package component and billed separately — invoice/package flag, not EK-3B-1 regulatory annex",
    claimPackageOk:
      "Claim {claimId} is billed correctly as package per SUT §2.2.2(1). Package total {amount} TRY.",
    claimItemizedOk:
      "Claim {claimId} is billed correctly as itemized per SUT §2.2. Itemized total {amount} TRY.",
    claimMandatePackage:
      "SUT §2.2 mandates package billing for claim {claimId} (EK-2/C procedure present). Package total {packageTotal} TRY vs itemized {itemizedTotal} TRY.",
    claimMandateItemized:
      "SUT §2.2 mandates itemized billing for claim {claimId}. Itemized total {itemizedTotal} TRY vs package {packageTotal} TRY.",
    claimOptionalPackageHigher:
      "Claim {claimId}: optional §2.2.2(2) override — package billing ({packageTotal} TRY) is the higher legal option vs itemized ({itemizedTotal} TRY).",
    claimOptionalItemizedHigher:
      "Claim {claimId}: optional §2.2.2(2) override — itemized billing ({itemizedTotal} TRY) is the higher legal option vs package ({packageTotal} TRY).",
    procedureMustPackage:
      "Procedure {code} must use package billing ({method}) per {section}.",
    procedureMustItemized:
      "Procedure {code} must use itemized billing ({method}) per {section}.",
    billedCorrectlyPackage: "Billed correctly as package.",
    billedCorrectlyItemized: "Billed correctly as itemized.",
    materialCopayRate: "SUT §1.8.3(2) material copay reference rate: {rate}%",
    ek1aChronic: "SUT §1.8.5(7) + EK-1/A chronic disease copay exemptions",
    emergencyWaiver: "SUT §1.8.5(5) emergency visit copay waiver (520021 excluded)",
    preventiveWaiver: "SUT §1.8.5(6) preventive health copay waiver",
    workAccident: "SUT §1.8.5(1) work accident / occupational disease",
    vataniHizmet: "SUT §1.8.5(11),(12) — Vatani Hizmet laws",
    gssBeneficiary: "SUT §1.8.5(22)a — 5510 md.60(12) GSS beneficiary groups",
    visitTypeRuleSource:
      "EK-1A, visit type (acil/koruyucu), SGK status, occupational context",
    ek1aChronicShort: "EK-1A chronic disease copay exemptions",
    ek1aChronicRanges: "EK-1A chronic disease copay exemptions (98 ICD-10 ranges)",
    honestyDrugIndication:
      "Registry is {status}; {encoded} rows encoded, {deferred} tier-C/structural deferred, {gaps} true algorithmic gaps. {emr} EMR-blocked (clinical data required).",
    honestyMaterialBundling:
      "Registry is implemented for the prose engine; manifest traces §3.1–3.2 encode candidates ({clauseIds} clause IDs) vs {rulesOnDisk} JSON rules on disk. Long-tail §3.1 fikra stay manifest-only.",
    honestySpecialty:
      "L4.4 export subset is 84 deontic §3.3 rows; manifest traces all of them while {rulesOnDisk} JSON rules cover branch themes (3.3.1–3.3.4). Catalog pricing (specialty_materials) remains separate.",
  },
  llmError: {
    malformed: "The request was malformed.",
    authFailed: "LLM authentication failed — the API key is missing or invalid.",
    quotaExhausted: "LLM quota exhausted — billing required.",
    forbidden: "LLM access forbidden.",
    timedOut: "The LLM request timed out.",
    contextTooLarge:
      "The request exceeded the model's context window — the workspace context is too large.",
    rateLimited: "The LLM rate limit was hit — please retry shortly.",
    serverError: "The LLM provider returned a server error ({status}). Please retry.",
    unexpected: "The LLM provider returned an unexpected error ({status}).",
    prefix: "API error {status}: {detail}",
  },
} as const;

export default api;
