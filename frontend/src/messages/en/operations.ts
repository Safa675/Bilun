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
