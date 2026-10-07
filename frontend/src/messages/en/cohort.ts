const cohort = {
  "filterBar": {
    "eyebrow": "Filtering",
    "matchedCount": "{matched} of {total} patients",
    "patientLabel": "Patient",
    "loadingPatients": "Loading patients…",
    "allPatients": "All patients",
    "sexLabel": "Sex",
    "sexAll": "All",
    "sexE": "E",
    "sexK": "K",
    "ageLabel": "Age",
    "agePlaceholder": "min - max",
    "doctorCodeLabel": "Doctor code",
    "doctorPlaceholder": "Contains…",
    "clearFilters": "Clear filters"
  },
  "patientSearch": {
    "defaultPlaceholder": "Search patient ID...",
    "selectedLabel": "Patient {patientId}",
    "searching": "Searching...",
    "noResults": "No patients found",
    "searchFailed": "Failed to search patients",
    "retry": "Retry search",
    "ageSuffix": "{age}y",
    "patientDetails": "{patientId} · {details}"
  }
} as const;

export default cohort;
