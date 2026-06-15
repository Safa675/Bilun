/**
 * Static design tokens and CSS class mappings.
 *
 * Domain constants (risk tiers, rating tiers, state colors, etc.)
 * are NOT here — they come from useConfig() / useRatingColors() / etc.
 * in @/lib/configContext.tsx, sourced from the backend.
 */

import { theme } from "@/lib/theme";
import type { UserRole } from "@/lib/userRole";

export const ACCENT = theme.accent;
export type SutHomeTab =
  | "patients"
  | "compliance"
  | "revenue"
  | "operations"
  | "reference-tools"
  | "rule-database";

export const LEGACY_SUT_HOME_TAB_ALIASES: Record<string, SutHomeTab> = {
  analytics: "patients",
  optimizer: "compliance",
};

export const SUT_BRAND = {
  productName: "BILUN",
  metaTitle: "BILUN",
  metaDescription: "BILUN billing rule intelligence module",
  heroDescription: "A standalone SUT workspace for SGK/SUT analytics, claim validation, financial exposure, and optimization workflows.",
  billingTitle: "Patient billing report",
  billingDescription: "Per-patient SUT rule review for labs, drugs, copay policy, billing strategy, and materials controls.",
  moduleLabel: "BILUN",
} as const;

export interface SutHomeTabMeta {
  id: SutHomeTab;
  label: string;
  subtitle: string;
  requiredRole?: UserRole[];
}

export const SUT_HOME_TABS: SutHomeTabMeta[] = [
  {
    id: "patients",
    label: "Patients",
    subtitle: "Who am I dealing with today? Cohort directory and recoverable summary.",
  },
  {
    id: "compliance",
    label: "Compliance",
    subtitle: "What's wrong? EK-1A exemptions, surcharge flags (EK-2G), and EK-2C-1 add-on rate alerts.",
  },
  {
    id: "revenue",
    label: "Revenue",
    subtitle: "Where's the money? Recovery totals, top patients, DRG and drug audits.",
  },
  {
    id: "operations",
    label: "Operations",
    subtitle: "MEDULA rejection queue and operational follow-up workflows.",
  },
  {
    id: "reference-tools",
    label: "Reference Tools",
    subtitle: "What does the rule say? Gazette lookups, validators, and catalogs.",
  },
  {
    id: "rule-database",
    label: "Rule Database",
    subtitle: "Where is it written? Every extracted SUT rule with its source clauses and coverage.",
    requiredRole: ["compliance_engineer", "dev", "admin"],
  },
];

export function parseSutHomeTab(value: string | null | undefined): SutHomeTab {
  if (value && value in LEGACY_SUT_HOME_TAB_ALIASES) {
    return LEGACY_SUT_HOME_TAB_ALIASES[value];
  }
  if (value === "compliance") return "compliance";
  if (value === "revenue") return "revenue";
  if (value === "operations") return "operations";
  if (value === "reference-tools") return "reference-tools";
  if (value === "rule-database") return "rule-database";
  if (value === "patients") return "patients";
  return "patients";
}

export function buildSutHomeHref(
  tab: SutHomeTab,
  preserveParams?: Pick<URLSearchParams, "get"> | null,
): string {
  const params = new URLSearchParams();
  params.set("tab", tab);
  if (preserveParams) {
    for (const key of ["cohortQ", "cohortSex", "cohortAgeMin", "cohortAgeMax", "cohortDoctor", "admin"] as const) {
      const value = preserveParams.get(key);
      if (value) params.set(key, value);
    }
  }
  const query = params.toString();
  return query ? `/?${query}` : "/";
}

export function buildSutPatientHref(
  patientId: string,
  params?: { claimId?: string; section?: string },
): string {
  const path = `/patient/${encodeURIComponent(patientId)}`;
  const query = new URLSearchParams();
  if (params?.claimId) query.set("claim", params.claimId);
  if (params?.section) query.set("section", params.section);
  const queryString = query.toString();
  return queryString ? `${path}?${queryString}` : path;
}

export function buildSutBillingHref(
  patientId: string,
  params?: { claimId?: string; section?: string },
): string {
  return buildSutPatientHref(patientId, params);
}

export const TAB_BACKGROUNDS = ["", "", "", "", "", ""];

export const CHART_COLORS = {
  bg: theme.surfaceBase,
  grid: theme.borderSubtle,
  axis: theme.borderSubtle,
  text: theme.textMuted,
  accent: theme.gold,
  prescription: theme.warning,
  positive: theme.success,
  negative: theme.danger,
  neutral: theme.textMuted,
  amber: theme.warning,
  band: theme.accentAlpha(0.04),
};

export const BADGE_CLASS: Record<string, string> = {
  AAA: "badge-aaa",
  AA: "badge-aa",
  A: "badge-a",
  BBB: "badge-bbb",
  BB: "badge-bb",
  "B/CCC": "badge-bccc",
};
