const patient = {
  "page": {
    "breadcrumbAria": "SUT patient breadcrumb",
    "workspace": "SUT workspace",
    "patient": "{patientId}",
    "patientUnknown": "Patient unknown",
    "searchEyebrow": "Patient search",
    "searchPlaceholder": "Jump to a different patient workspace...",
    "searchDescription": "Patient selection routes into the dedicated SUT workspace instead of loading inline on home.",
    "billingUnavailable": "Billing Report unavailable",
    "footerNormative": "Normative analysis based on official SUT gazette rule references (EK-1A, EK-2B, EK-2C, EK-4A)",
    "errors": {
      "outcome": "Failed to load patient SUT outcome.",
      "optimization": "Failed to load patient optimization.",
      "billing": "Failed to load patient billing report.",
      "claims": "Failed to load patient claims."
    }
  },
  "financialSummary": {
    "eyebrow": "Financial profile",
    "title": "All bills at a glance",
    "titleBill": "Bill {claimId}",
    "description": "Patient-level totals across every claim: what was billed, what SUT expects to pay, and how much BILUN can still recover.",
    "descriptionBill": "Totals and recoverable amounts for the selected bill only — sections below use the same scope.",
    "totalBilled": "Total billed",
    "expectedPayable": "Expected payable",
    "totalRecoverable": "Total recoverable (claim-backed)",
    "billCount": "Bills",
    "overallPriority": "Overall priority"
  },
  "billingGroups": {
    "overview": "Financial overview",
    "overviewDescription": "Summary KPIs and recommended actions for the active scope."
  },
  "billPicker": {
    "label": "Bills",
    "allBills": "All bills (summary)",
    "recoverable": "recoverable",
    "claimSingular": " bill",
    "claimPlural": " bills",
    "billMeta": "{claimType} · {amount}"
  },
  "originalBill": {
    "eyebrow": "As submitted",
    "title": "Original invoice",
    "description": "Full-fidelity view of this bill's line items: what was billed versus what SUT expects to pay on each row.",
    "proceduresTitle": "Procedures",
    "labsTitle": "Laboratory",
    "materialsTitle": "Materials",
    "drugsTitle": "Drugs",
    "asSubmitted": "Billed",
    "sutExpected": "SUT expected",
    "sectionSubtotal": "{section} subtotal",
    "linesSubtotal": "Line items subtotal",
    "variance": "Header vs lines",
    "noLabs": "No laboratory lines in this bill.",
    "facility": "Facility tier",
    "optimizationHint": "Per-bill optimization sections below show how this invoice could be billed under SUT.",
    "legacyGhostLineFootnote": "{count} line(s) with zero billed but non-zero SUT expected are excluded from subtotals; see optimization for the alternative billing path."
  },
  "claimDetail": {
    "loading": "Loading claim details…",
    "period": "Period",
    "totalBilled": "Total billed",
    "totalPayable": "Expected payable",
    "noProcedures": "No procedure lines in this claim.",
    "noMaterials": "No material lines in this claim.",
    "noDrugs": "No drug lines in this claim.",
    "date": "Date",
    "code": "Code",
    "name": "Name",
    "quantity": "Qty"
  },
  "workspace": {
    "eyebrow": "SUT patient workspace",
    "billingTitle": "Billing",
    "billingEmphasis": "Report",
    "description": "A dedicated patient-level exact-only workspace that composes surviving SUT outcome and optimization data before handing off to the deeper billing review.",
    "backToPatients": "Back to patients",
    "diagnoses": "Diagnoses",
    "icdChapters": "ICD chapters",
    "icdNone": "None",
    "primaryFocus": "Primary focus",
    "focusCopay": "Copay exemption",
    "focusExactness": "Exactness review",
    "clinicalSnapshotEyebrow": "Clinical & rule snapshot",
    "clinicalSnapshotDescription": "Diagnosis-driven SUT rule findings for this patient. Select a bill below for claim-scoped optimization.",
    "optimizationTitle": "Optimization snapshot",
    "optimizationDescription": "Patient-level SUT rule findings stay exactness-aware: unavailable inputs stay unavailable.",
    "copayEyebrow": "Copay exemption",
    "copayEligible": "Eligible",
    "copayNoMatch": "No exemption ground matched",
    "copayEk1a": "EK-1A chronic diagnosis: {count} qualifying {codeWord} for outpatient copay waiver.",
    "copayCodeSingular": "code",
    "copayCodePlural": "codes",
    "copayWaiverGrounds": "Waiver grounds: {basis}.",
    "copayGenericMatch": "Patient matches at least one evaluated copay waiver rule.",
    "copayNoInputs": "No EK-1A, visit-type, or status exemption matched with current claim and profile inputs.",
    "chipActionable": "Actionable",
    "chipClear": "Clear",
    "topMatchDetail": "ICD-10 {icd10} · Gazette range {range}",
    "surchargeTitle": "Surcharge exposure",
    "copayRateTitle": "EK-2C-1 copay rate",
    "drgTitle": "DRG package review",
    "applicableProcedures": "Applicable procedures",
    "exposureRate": "Exposure rate",
    "meanRate": "Mean rate",
    "chaptersAnalyzed": "Chapters analyzed",
    "riskState": "Risk state",
    "riskOpportunity": "Potential package opportunity",
    "riskNone": "No risk flagged",
    "reviewPackage": "Review package eligibility",
    "surchargeFallback": "Surcharge exposure stays unavailable until exact billed procedure lines are present.",
    "copayRateFallback": "EK-2C-1 copay rate stays unavailable until exact billed procedure lines are present.",
    "drgFallback": "DRG unbundling review stays unavailable until exact itemized claim lines exist."
  },
  "section": {
    "selectedPatient": {
      "eyebrow": "Selected patient",
      "label": "{patientId}",
      "statusLoading": "Refreshing exact DRG analytics...",
      "statusError": "Patient analytics could not be loaded.",
      "statusEmpty": "Patient-level DRG analytics are not currently loaded.",
      "statusReady": "Patient-level DRG analytics are ready."
    },
    "errors": {
      "retryHint": "Retry this patient, or pick a different patient from the table.",
      "retryButton": "Retry patient outcome"
    },
    "emptyState": {
      "message": "Patient-level SUT analytics are not currently loaded for patient {patientId}."
    },
    "outcomeSummary": {
      "eyebrow": "Exact-only patient outcome",
      "title": "Claim-line totals stay explicit",
      "paragraph1": "Estimate-backed SUT cost ranges and gap projections were removed.",
      "paragraph2": "This patient view keeps exact claim-line totals from the analytics cache; missing pricing metadata stays unavailable instead of being treated as exact."
    },
    "claimSummary": {
      "title": "Exact Claim-Line Summary",
      "description": "Patient-level SUT totals are assembled from exact synthetic claim headers and claim lines.",
      "totalBilled": "Total Billed",
      "expectedPayable": "Expected Payable",
      "claims": "Claims",
      "procedureLines": "Procedure Lines",
      "materialLines": "Material Lines",
      "drugLines": "Drug Lines",
      "diagnoses": "Diagnoses",
      "ruleFlags": "Rule Flags",
      "ruleFlagsSub": "Visible top procedures",
      "exactClaimLineAmount": "Exact claim-line amount",
      "syntheticExpectedOutput": "Synthetic expected output",
      "table": {
        "date": "Date",
        "procedure": "Procedure",
        "billed": "Billed",
        "surcharge": "Surcharge",
        "copayRate": "EK-2C-1 copay rate"
      }
    }
  }
} as const;

export default patient;
