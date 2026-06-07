const common = {
  unavailable: "Unavailable",
  unknown: "Unknown",
  yes: "Yes",
  no: "No",
  retry: "Retry",
  loading: "Loading…",
  dash: "—",
  close: "Close",
  previous: "Previous",
  next: "Next",
  search: "Search",
  clear: "Clear",
  simulate: "Simulate",
  simulating: "Simulating…",
  validating: "Validating…",
  prev: "Prev",
  go: "Go",
  skeleton: {
    patientAnalytics: "Loading patient analytics",
    patientAnalyticsWithId: "Loading patient {patientId}",
    billingReport: "Loading billing report",
    billingReportWithId: "Loading {patientId}",
  },
} as const;

export default common;
