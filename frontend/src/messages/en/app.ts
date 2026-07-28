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
    "intro": "The split SUT app focuses on billing rule analytics, exactness-aware optimization, and patient financial review without reaching back into mixed legacy IHP surfaces.",
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
        "description": "The patient workspace composes SUT outcome and optimization data to show cost, rule-calculation status, and exactness-aware patient findings.",
        "detail1": "Outcome data provides cost, DRG summary, and claim-line rule context.",
        "detail2": "Optimization data provides copay exemption and exactness-aware rule findings.",
        "detail3": "Home patient search now routes into the dedicated patient workspace.",
        "feedsInto": "Patient workspace and billing handoff"
      },
      "03": {
        "title": "Exactness-first optimization",
        "description": "Unavailable optimization surfaces stay unavailable until the exact billed inputs exist, rather than being shown as low risk or zero impact.",
        "detail1": "Copay exemptions stay actionable when exact.",
        "detail2": "Surcharge, EK-2C-1 copay rate, and DRG-unbundling findings respect missing exact inputs.",
        "detail3": "The patient workspace and optimizer share the same exactness semantics.",
        "feedsInto": "Optimizer alerts and revenue recovery review"
      },
      "04": {
        "title": "Dedicated billing handoff",
        "description": "Patient-level financial review stays split across a high-level patient workspace and the deeper billing route, instead of pushing everything into home.",
        "detail1": "The new `/patient/[id]` page becomes the main patient shell.",
        "detail2": "Detailed section-by-section billing remains on `/patient/[id]/billing`.",
        "detail3": "The handoff keeps ownership and routing clear inside the split app.",
        "feedsInto": "Patient route and dedicated billing route"
      },
      "05": {
        "title": "Product-owned SUT assistant",
        "description": "The restored chatbot is wired to SUT-only context so it can explain exposure, optimization, and patient SUT rule state without depending on IHP cache readiness.",
        "detail1": "Frontend chat requests use `/api/chat`.",
        "detail2": "Context assembly stays inside SUT exposure, optimization, and patient routes.",
        "detail3": "Unavailable exactness states are explained, not converted into fake numerics.",
        "feedsInto": "SUT-owned assistant context"
      }
    }
  }
} as const;

export default app;
