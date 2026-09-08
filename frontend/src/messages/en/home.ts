const home = {
  "patientTable": {
    "eyebrow": "Patient invoices",
    "loading": "Loading patient data…",
    "loadFailed": "Failed to load patient data",
    "emptyCohort": "No patients found in the current cohort.",
    "patientCount": "{count} patient",
    "patientCountPlural": "{count} patients",
    "exemptionGapOnly": "exemption gap",
    "sortBy": "Sort by {label}",
    "headers": {
      "patientId": "Patient ID",
      "age": "Age",
      "sex": "Sex",
      "recoverable": "Recoverable",
      "priority": "Priority",
      "actions": "Actions",
      "topAction": "Top action"
    },
    "pagination": {
      "prev": "Prev",
      "next": "Next",
      "pageOf": "Page {current} of {total}",
      "jumpToPage": "Jump to page",
      "go": "Go"
    }
  }
} as const;

export default home;
