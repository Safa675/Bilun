/**
 * Static design tokens and CSS class mappings.
 *
 * Domain constants (risk tiers, rating tiers, state colors, etc.)
 * are NOT here — they come from useConfig() / useRatingColors() / etc.
 * in @/lib/configContext.tsx, sourced from the backend.
 */

import { theme } from "@/lib/theme";

export const ACCENT = theme.accent;
export type SutHomeTab = "analytics" | "optimizer" | "reference-tools";

export const SUT_BRAND = {
  productName: "BILUN",
  metaTitle: "BILUN",
  metaDescription: "BILUN billing rule intelligence module",
  heroDescription: "A standalone SUT workspace for SGK/SUT analytics, claim validation, financial exposure, and optimization workflows.",
  billingTitle: "Patient billing report",
  billingDescription: "Per-patient SUT rule review for labs, drugs, copay policy, billing strategy, and materials controls.",
  moduleLabel: "BILUN",
} as const;

export const SUT_HOME_TABS: { id: SutHomeTab; label: string; subtitle: string }[] = [
  {
    id: "analytics",
    label: "SUT Analytics",
    subtitle: "Patient rule outcomes and exposure analysis",
  },
  {
    id: "optimizer",
    label: "SUT Optimizer",
    subtitle: "Compliance alerts, recovery review, and billing optimization",
  },
  {
    id: "reference-tools",
    label: "Reference Tools",
    subtitle: "Billing and gazette reference lookups, validators, and catalogs",
  },
];

export function parseSutHomeTab(value: string | null | undefined): SutHomeTab {
  if (value === "optimizer") return "optimizer";
  if (value === "reference-tools") return "reference-tools";
  return "analytics";
}

export function buildSutHomeHref(tab: SutHomeTab): string {
  return `/?tab=${tab}`;
}

export function buildSutPatientHref(patientId: string): string {
  return `/patient/${encodeURIComponent(patientId)}`;
}

export function buildSutBillingHref(patientId: string): string {
  return buildSutPatientHref(patientId);
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
