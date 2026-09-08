const common = {
  unavailable: "Unavailable",
  unknown: "Unknown",
  retry: "Retry",
  loading: "Loading…",
  dash: "—",
  close: "Close",
  skeleton: {
    patientAnalytics: "Loading patient analytics",
    patientAnalyticsWithId: "Loading patient {patientId}",
    billingReport: "Loading billing report",
    billingReportWithId: "Loading {patientId}",
  },
  requestAborted: "Request was interrupted. Reopen the tab to retry.",
  loadFailed: "Failed to load data.",
  unknownSurface: "Unknown",
  unknownKind: "Unknown",
  apiError: {
    couldNotReachApi: "Could not reach API at {url}",
    failedWithBody: "API error: {status} {statusText} - {detail}",
    failedWithoutBody: "API error: {status} {statusText}",
    invalidJson: "API returned invalid JSON from {path}",
  },
} as const;

export default common;
