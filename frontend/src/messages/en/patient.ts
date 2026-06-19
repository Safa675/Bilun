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
    "description": "Patient-level totals across every claim: what was billed, what SUT expects to pay, and how much BILUN can still recover.",
    "totalBilled": "Total billed",
    "expectedPayable": "Expected payable",
    "totalRecoverable": "Total recoverable (claim-backed)",
    "billCount": "Bills",
    "overallPriority": "Overall priority"
  },
  "claimSelector": {
    "label": "Invoice / Claim",
    "allClaims": "All claims",
    "claimCount": "{count}",
    "claimSingular": " claim",
    "claimPlural": " claims"
  },
  "billPicker": {
    "label": "Bills",
    "allBills": "All bills (summary)",
    "recoverable": "recoverable",
    "billed": "billed",
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
    "eyebrow": "Selected claim",
    "period": "Period",
    "totalBilled": "Total billed",
    "totalPayable": "Expected payable",
    "lines": "Lines",
    "proceduresTitle": "Procedures",
    "materialsTitle": "Materials",
    "drugsTitle": "Drugs",
    "noProcedures": "No procedure lines in this claim.",
    "noMaterials": "No material lines in this claim.",
    "noDrugs": "No drug lines in this claim.",
    "date": "Date",
    "code": "Code",
    "name": "Name",
    "quantity": "Qty",
    "billed": "Billed",
    "payable": "Payable"
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
    "consistencyEyebrow": "Consistency note",
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
      "title": "DRG package review stays explicit",
      "paragraph1": "Estimate-backed SUT cost ranges and gap projections were removed.",
      "paragraph2": "This patient view now keeps only the surviving DRG package outcome surface, and missing pricing metadata stays unavailable instead of being treated as exact."
    },
    "noDrgSummary": {
      "title": "No DRG episode summary available",
      "body": "This patient outcome no longer includes estimate-backed fallback sections. If exact DRG pricing inputs are unavailable, the patient remains unavailable here."
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
    },
    "drgPanel": {
      "title": "DRG Episode Cost Modeling",
      "description": "Claim-exact comparison of itemized inpatient costs against billed SGK DRG package prices (EK-2C). LOS and package prices come from real claim lines, not estimates.",
      "unavailableFallback": "DRG package pricing is unavailable when an inpatient claim has no billed package (P#####) line or missing admission/discharge dates.",
      "episodes": "Episodes:",
      "itemizedCost": "Itemized Cost:",
      "drgPackagePrice": "DRG Package Price:",
      "meanEpisode": "Mean/Episode:",
      "costliest": "Costliest:",
      "table": {
        "index": "#",
        "claimId": "Claim",
        "icd10": "ICD-10",
        "description": "Description",
        "group": "Group",
        "packageCode": "Package",
        "los": "LOS",
        "lab": "Lab",
        "visit": "Visit",
        "rx": "Rx",
        "proc": "Proc",
        "itemized": "Itemized",
        "drgPrice": "DRG Price"
      }
    }
  }
} as const;

export default patient;
