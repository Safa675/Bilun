const chat = {
  title: "BILUN Analysis",
  subtitle: {
    patient: "Patient: {patientId}",
    cohortOverview: "Cohort overview",
  },
  actions: {
    regenerateAnalysis: "Regenerate analysis",
    dockLeft: "Dock left",
    centerInline: "Center (inline)",
    dockRight: "Dock right",
    sendMessage: "Send message",
  },
  emptyState: "BILUN will brief each view and keep the full thread here.",
  roles: {
    you: "You",
    bilun: "BILUN",
  },
  approve: {
    approved: "Approved",
    approve: "Approve",
  },
  loading: {
    analyzing: "BILUN is analyzing...",
  },
  errors: {
    failedAutoAnalysis: "Failed to get SUT analysis. Click regenerate to retry.",
    failedFollowUp: "Failed to get a SUT response.",
  },
  tip: {
    label: "Tip:",
    selectPatient:
      "Select a patient from the cohort table to get detailed billing analysis, including copay savings, lab optimization, drug substitution, and billing strategy comparisons.",
  },
  input: {
    placeholderPatient: "Ask BILUN about this patient or billing review...",
    placeholderWorkspace: "Ask BILUN about this workspace...",
  },
  defaultPrompts: {
    sutWorkspace:
      "Summarize the current SUT workspace. Highlight the main rule-review workflows available here and what the user should inspect first. Reply in English.",
    patients:
      "Summarize the patient cohort directory. Focus on recoverable totals, priority patients, and any exactness caveats before drilling into a patient. Reply in English.",
    compliance:
      "Summarize compliance alerts for the filtered cohort. Highlight copay exemptions (EK-1A), surcharge flags (EK-2G), EK-2C-1 copay rate issues, and where exactness blocks action. Reply in English.",
    revenue:
      "Summarize revenue recovery for the filtered cohort. Highlight recoverable totals, top patients, and where exactness limitations block action. Reply in English.",
    referenceTools:
      "Explain which gazette reference tools are available and when a billing officer should use each lookup. Reply in English.",
    sutPatientWorkspace:
      "Give a patient-level SUT briefing. Summarize the rule-calculation state, exactness-aware optimization findings, and what the billing review should confirm next. Reply in English.",
    sutBillingReview:
      "Summarize this SUT billing review. Explain which sections are exact, which remain unavailable, and what the user should verify before taking action. Reply in English.",
  },
  api: {
    requestTimedOut: "SUT chat request timed out. Please try again.",
    couldNotReachApi: "Could not reach API at {url}",
    failedWithBody: "SUT chat failed: {status} {statusText} - {body}",
    failedWithoutBody: "SUT chat failed: {status} {statusText}",
    noResponseBody: "SUT chat returned no response body.",
    noResponseReceived: "No response received from SUT chat. Please try again.",
    emptyResponse: "SUT chat returned an empty response.",
  },
} as const;

export default chat;
