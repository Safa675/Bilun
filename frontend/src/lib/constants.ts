/**
 * Static design tokens and CSS class mappings.
 *
 * Domain constants (risk tiers, rating tiers, state colors, etc.)
 * come from useConfig() in @/lib/configContext.tsx, sourced from the backend.
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
  productName: "Bilun",
  metaTitle: "Bilun",
  metaDescription: "Bilun billing rule intelligence module",
  heroDescription: "A standalone SUT workspace for SGK/SUT analytics, claim validation, financial exposure, and optimization workflows.",
  billingTitle: "Patient billing report",
  billingDescription: "Per-patient SUT rule review for labs, drugs, copay policy, billing strategy, and materials controls.",
  moduleLabel: "Bilun",
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
    subtitle: "What's wrong? EK-1A exemptions and surcharge flags (EK-2G).",
  },
  {
    id: "revenue",
    label: "Revenue Dashboard",
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
    requiredRole: ["dev"],
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
    for (const key of ["cohortQ", "cohortSex", "cohortAgeMin", "cohortAgeMax", "cohortDoctor", "admin", "p"] as const) {
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
