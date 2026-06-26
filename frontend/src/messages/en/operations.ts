const operations = {
  queue: {
    title: "MEDULA rejection queue",
    subtitle: "Reactive triage for claims rejected by MEDULA. Operational guidance only — not included in SGK uplift.",
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
      procedure: "Procedure",
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
      matchedOnly: "Only matched templates",
      rebillPermittedOnly: "Only rebill permitted",
      searchPlaceholder: "Search patient or claim",
    },
    values: {
      yes: "Yes",
      no: "No",
      noTemplate: "No template",
    },
  },
} as const;

export default operations;
