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
      "billing": "Failed to load patient billing report."
    }
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
      "description": "Compares itemized episode costs against SGK bundled DRG package prices (EK-2C). Surplus means the DRG package covers more than itemized costs.",
      "unavailableFallback": "DRG package pricing remains unavailable until every episode has an exact admission date and historical package price.",
      "episodes": "Episodes:",
      "itemizedCost": "Itemized Cost:",
      "drgPackagePrice": "DRG Package Price:",
      "meanEpisode": "Mean/Episode:",
      "costliest": "Costliest:",
      "table": {
        "index": "#",
        "icd10": "ICD-10",
        "description": "Description",
        "group": "Group",
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
