const operations = {
  queue: {
    title: "MEDULA rejection queue",
    empty: {
      noIngest: "MEDULA rejection ingest is not enabled for this cohort.",
      noEvents: "No MEDULA rejection records found.",
    },
    columns: {
      patient: "Patient",
      claim: "Claim",
      rejectionDate: "Rejection date",
      stage: "Stage",
      resultCode: "Result code",
      message: "MEDULA message",
      relatedLine: "Related line",
      playbook: "Playbook",
      rebill: "Rebill permitted",
    },
    lineType: {
      procedure: "Procedure",
      material: "Material",
      drug: "Drug",
      claim: "Claim",
    },
    stages: {
      fatura_kayit: "Invoice registration",
      hizmet_kayit: "Service registration",
      provizyon: "Provision",
    },
    playbooks: {
      "1688_molecular_microbiology": "Molecular microbiology report",
      "0612_board_report_missing": "Missing health board report",
      "1205_service_date_mismatch": "Service date mismatch",
      "0521_provision_not_obtained": "Missing provision",
      "0315_specialty_mismatch": "Specialty mismatch",
      "0901_duplicate_procedure": "Duplicate procedure",
      "0704_uts_barcode_missing": "Missing UTS barcode",
      "0320_package_bundled_procedure": "Package-bundled procedure",
      "0411_drug_report_missing": "Missing drug report",
      "1102_uncontracted_facility": "Facility contract issue",
      "0963_material_finalization": "Material finalization",
    },
    filters: {
      resultCode: "Result code",
      stage: "Stage",
      all: "All",
      matchedOnly: "Only matched templates",
      rebillPermittedOnly: "Only rebill permitted",
      searchPlaceholder: "Search patient or claim",
    },
    kpis: {
      total: "Total rejections",
      matched: "Playbook matched",
      rebillable: "Rebill permitted",
    },
    values: {
      yes: "Yes",
      no: "No",
      noTemplate: "No template",
    },
    correctiveSteps: "Corrective steps",
    noCorrectiveSteps: "No corrective steps for this record.",
  },
} as const;

export default operations;
