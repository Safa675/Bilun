const constants = {
  brand: {
    productName: "Bilun",
    metaTitle: "Bilun",
    metaDescription: "Bilun billing rule intelligence module",
    heroDescription:
      "A standalone SUT workspace for SGK/SUT analytics, claim validation, financial exposure, and optimization workflows.",
    billingTitle: "Patient billing report",
    billingDescription:
      "Per-patient SUT rule review for labs, drugs, copay policy, billing strategy, and materials controls.",
    moduleLabel: "Bilun",
  },
  homeTabs: {
    patients: {
      label: "Patients",
      subtitle: "Who am I dealing with today? Cohort directory and recoverable summary.",
    },
    compliance: {
      label: "Compliance",
      subtitle: "What's wrong? Live cohort findings: exemptions, surcharge, materials, indication, lab, payment.",
    },
    revenue: {
      label: "Revenue Dashboard",
      subtitle: "Where's the money? Recovery totals, top patients, DRG and drug audits.",
    },
    operations: {
      label: "Rejection Queue",
      subtitle: "MEDULA rejection queue and follow-up.",
    },
    referenceTools: {
      label: "Reference Tools",
      subtitle: "What does the rule say? Gazette lookups, validators, and catalogs.",
    },
    ruleDatabase: {
      label: "Rule Database",
      subtitle: "Where is it written? Every extracted SUT rule with its source clauses and coverage.",
    },
  },
} as const;

export default constants;
