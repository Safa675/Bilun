/**
 * Static design tokens and CSS class mappings.
 *
 * Domain constants (risk tiers, rating tiers, state colors, etc.)
 * are NOT here — they come from useConfig() / useRatingColors() / etc.
 * in @/lib/configContext.tsx, sourced from the backend.
 */

import { theme } from "@/lib/theme";

export const ACCENT = theme.accent;
export type SutHomeTab = "analytics" | "optimizer";

export const SUT_BRAND = {
  productName: "ILAY SUT",
  metaTitle: "ILAY SUT",
  metaDescription: "ILAY SUT billing rule intelligence module",
  heroTitle: "Billing rule intelligence",
  heroDescription: "A standalone SUT workspace for SGK/SUT analytics, claim validation, financial exposure, and optimization workflows.",
  billingTitle: "Patient billing report",
  billingDescription: "Per-patient SUT rule review for labs, drugs, copay policy, billing strategy, and materials controls.",
  moduleLabel: "ILAY SUT",
} as const;

export const SUT_HOME_TABS: { id: SutHomeTab; label: string; subtitle: string }[] = [
  {
    id: "analytics",
    label: "SUT Analytics",
    subtitle: "Patient rule outcomes, exposure, and reference tools",
  },
  {
    id: "optimizer",
    label: "SUT Optimizer",
    subtitle: "Compliance alerts, recovery review, and billing optimization",
  },
];

export function parseSutHomeTab(value: string | null | undefined): SutHomeTab {
  return value === "optimizer" ? "optimizer" : "analytics";
}

export function buildSutHomeHref(tab: SutHomeTab): string {
  return `/?tab=${tab}`;
}

export function buildSutPatientHref(patientId: string): string {
  return `/patient/${encodeURIComponent(patientId)}`;
}

export function buildSutBillingHref(patientId: string): string {
  return `${buildSutPatientHref(patientId)}/billing`;
}

export const TAB_BACKGROUNDS = ["", "", "", "", "", ""];

export const CHART_COLORS = {
  bg: "#FAFAF9",
  grid: "#F4F4F5",
  axis: "#E4E4E7",
  text: "#A1A1AA",
  accent: ACCENT,
  prescription: "#B45309",
  positive: theme.accentDark,
  negative: "#B91C1C",
  neutral: "#A1A1AA",
  amber: "#B45309",
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
