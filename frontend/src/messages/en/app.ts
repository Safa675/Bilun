const app = {
  "error": {
    "title": "Something went wrong in the SUT workspace",
    "description": "The current screen could not be rendered. Try again, or return to the main SUT workspace.",
    "fallbackMessage": "Unexpected SUT application error.",
    "tryAgain": "Try again",
    "backToWorkspace": "Back to SUT workspace"
  },
  "howItWorks": {
    "ariaLabel": "How Bilun works",
    "closeAria": "Close how it works modal",
    "kicker": "Bilun",
    "title": "How the SUT workspace works",
    "intro": "Bilun checks bills against SUT rules and shows findings, recoverable amounts and missing information.",
    "phaseNavAria": "SUT methodology phases",
    "phaseBadge": "Phase {number}",
    "powersLabel": "Powers",
    "previous": "Previous",
    "nextPhase": "Next Phase",
    "gotIt": "Got It",
    "phases": {
      "01": {
        "title": "Gazette catalog assembly",
        "description": "Bilun reads the curated gazette schedules that back current procedure pricing, DRG package pricing, and normative SUT controls.",
        "detail1": "Canonical SUT pricing uses dated gazette catalog lookups.",
        "detail2": "Procedure, DRG, and material references stay within SUT-owned routes.",
        "detail3": "Historical package availability is preserved instead of silently falling forward.",
        "feedsInto": "SUT reference tools, pricing APIs, and billing review"
      },
      "02": {
        "title": "Patient SUT rule assembly",
        "description": "The patient report brings billed amounts, SUT findings and missing information together.",
        "detail1": "Billed items provide the amounts and procedure details.",
        "detail2": "SUT checks show exemptions and findings with their calculation status.",
        "detail3": "Each patient opens in a separate report.",
        "feedsInto": "Patient report and bill review"
      },
      "03": {
        "title": "Exactness-first optimization",
        "description": "Unavailable optimization surfaces stay unavailable until the exact billed inputs exist, rather than being shown as low risk or zero impact.",
        "detail1": "Copay exemptions stay actionable when exact.",
        "detail2": "Surcharge, EK-2C-1 copay rate, and DRG-unbundling findings respect missing exact inputs.",
        "detail3": "Missing amounts stay unavailable in both patient and summary views.",
        "feedsInto": "Optimizer alerts and revenue recovery review"
      },
      "04": {
        "title": "Bill review",
        "description": "The patient report shows the summary and the details for each selected bill.",
        "detail1": "The summary shows billed, expected payable and recoverable amounts.",
        "detail2": "Bill details show the itemized procedures, materials and drugs.",
        "detail3": "Each view identifies whether it covers one bill or all bills.",
        "feedsInto": "Patient summary and bill details"
      },
      "05": {
        "title": "SUT assistant",
        "description": "The assistant explains the available patient findings and SUT references.",
        "detail1": "Answers use the current patient and billing context.",
        "detail2": "Findings stay linked to their available SUT sources.",
        "detail3": "Missing information is explained, not replaced with a zero amount.",
        "feedsInto": "SUT finding explanations"
      }
    }
  }
} as const;

export default app;
