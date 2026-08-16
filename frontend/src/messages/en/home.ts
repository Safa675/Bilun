const home = {
  "workspaceLanding": {
    "openPatientWorkspace": "Open a patient workspace",
    "searchPlaceholder": "Search a patient ID…",
    "recentPatients": "Recent patients",
    "recentPatientsEmpty": "No recent patients yet. Search above to open one.",
    "recentBilling": "Recent billing reports",
    "recentBillingEmpty": "No recent billing reports yet. Open a patient, then the billing tab.",
    "jumpInto": "Or jump straight into",
    "tabPatients": "Patients",
    "tabCompliance": "Compliance",
    "tabRevenue": "Revenue Dashboard",
    "howItWorks": "How it works",
    "relativeTime": {
      "justNow": "just now",
      "minutesAgo": "{count}m ago",
      "hoursAgo": "{count}h ago",
      "daysAgo": "{count}d ago",
      "monthsAgo": "{count}mo ago",
      "yearsAgo": "{count}y ago"
    }
  },
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
