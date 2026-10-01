const chat = {
  title: "Bilun Analysis",
  subtitle: {
    patient: "Patient: {patientId}",
    cohortOverview: "Cohort overview",
  },
  actions: {
    regenerateAnalysis: "Regenerate analysis",
    centerInline: "Center (inline)",
    dockRight: "Dock right",
    sendMessage: "Send message",
  },
  emptyState: "Bilun will brief each view and keep the full thread here.",
  devModeBadge: "Dev copilot",
  roles: {
    you: "You",
    bilun: "Bilun",
  },
  loading: {
    analyzing: "Bilun is analyzing...",
    thinking: "Thinking",
  },
  errors: {
    failedAutoAnalysis: "Failed to get SUT analysis. Click regenerate to retry.",
    failedFollowUp: "Failed to get a SUT response.",
    questionTooLong: "Your question is too long. Shorten it to {max} characters or fewer and try again.",
  },
  tip: {
    label: "Tip:",
    selectPatient:
      "Select a patient from the cohort table to get detailed billing analysis, including copay savings, lab optimization, drug substitution, and billing strategy comparisons.",
  },
  input: {
    placeholderPatient: "Ask Bilun about this patient or billing review...",
    placeholderWorkspace: "Ask Bilun about this workspace...",
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
    operations:
      "Summarize the MEDULA rejection queue. Highlight pending rejections, error-code categories, and corrective steps before resubmission. Reply in English.",
    referenceTools:
      "Explain which gazette reference tools are available and when a billing officer should use each lookup. Reply in English.",
    ruleDatabase:
      "Summarize the SUT rule database. Explain how rules map to source clauses and EK annexes, what the coverage statuses mean, and which rules still have gaps. Reply in English.",
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
