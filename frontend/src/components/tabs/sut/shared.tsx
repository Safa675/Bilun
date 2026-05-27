import { theme } from "@/lib/theme";
import { ACCENT } from "@/lib/constants";
import type { SutMaterialItem } from "@/lib/api/sut";
import { getSutRiskTierLabel } from "../../../lib/sutLabels";

export const ACCENT_LOCAL = theme.accent;
export const SUT_PRIMARY_LOCALE = "en-US";
export const SUT_CURRENCY_CODE = "TRY";

function formatLocaleNumber(
  value: number,
  options?: Intl.NumberFormatOptions,
): string {
  return new Intl.NumberFormat(SUT_PRIMARY_LOCALE, options).format(value);
}

export function fmtTRY(value: number): string {
  return `${formatLocaleNumber(value, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })} ${SUT_CURRENCY_CODE}`;
}

export function fmtTRY2(value: number): string {
  return `${formatLocaleNumber(value, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} ${SUT_CURRENCY_CODE}`;
}

export function fmtTRYOrUnavailable(value: number | null | undefined): string {
  return value == null ? "Unavailable" : fmtTRY(value);
}

export function fmtTRY2OrUnavailable(value: number | null | undefined): string {
  return value == null ? "Unavailable" : fmtTRY2(value);
}

export function fmtNumOrUnavailable(value: number | null | undefined): string {
  return value == null ? "Unavailable" : fmtNum(value);
}

export function fmtPct(value: number, decimals = 1): string {
  return `${formatLocaleNumber(value, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}%`;
}

export function fmtNum(value: number): string {
  return formatLocaleNumber(Math.round(value), {
    maximumFractionDigits: 0,
  });
}

export function fmtPctRatio(value: number, decimals = 1): string {
  return fmtPct(value * 100, decimals);
}

function titleCaseWord(word: string): string {
  if (!word) {
    return "";
  }
  return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
}

export function fmtLabel(value: string | null | undefined): string {
  const normalized = value?.trim();
  if (!normalized) {
    return "Unknown";
  }
  return normalized
    .replace(/[_-]+/g, " ")
    .split(/\s+/)
    .map(titleCaseWord)
    .join(" ");
}

export function fmtTierLabel(value: string | null | undefined): string {
  return fmtLabel(value);
}

export function fmtPriorityLabel(value: string | null | undefined): string {
  return fmtLabel(value);
}

export function fmtRiskLabel(value: string | null | undefined): string {
  return getSutRiskTierLabel(value);
}

export type PatientOutcomeViewState = "idle" | "loading" | "error" | "empty" | "ready";

export function getSutOutcomeViewState({
  selectedPatientId,
  loading,
  error,
  hasData,
}: {
  selectedPatientId: string | null;
  loading: boolean;
  error: string | null;
  hasData: boolean;
}): PatientOutcomeViewState {
  if (!selectedPatientId) {
    return "idle";
  }
  if (loading) {
    return "loading";
  }
  if (error) {
    return "error";
  }
  if (!hasData) {
    return "empty";
  }
  return "ready";
}

export function KpiCard({
  label,
  value,
  valueColor,
  sub,
}: {
  label: string;
  value: string;
  valueColor?: string;
  sub?: string;
}) {
  // Phase 4: chrome stripped. Renders as a flat label/value block on a
  // transparent surface. Caller's grid container owns layout/spacing.
  // `valueColor` is still honored for status colors; default is navy.
  return (
    <div className="flex flex-col gap-1.5">
      <p className="text-[0.68rem] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">
        {label}
      </p>
      <p
        className="text-lg font-semibold tabular-nums lining-nums leading-tight"
        style={{ color: valueColor ?? "var(--text-primary)" }}
      >
        {value}
      </p>
      {sub && (
        <p className="text-xs leading-snug text-[var(--text-secondary)]">{sub}</p>
      )}
    </div>
  );
}

export function ChartTooltipContent({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { value: number; fill?: string }[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-[var(--r-md)] border border-[var(--border-subtle)] bg-[var(--surface-base)] px-3 py-2 text-xs shadow-[var(--shadow-1)]">
      <p className="mb-1 font-medium text-[var(--text-primary)]">{label}</p>
      {payload.map((entry, i) => (
        <p key={i} style={{ color: entry.fill || ACCENT }}>
          {typeof entry.value === "number"
            ? formatLocaleNumber(entry.value, {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })
            : entry.value}
        </p>
      ))}
    </div>
  );
}

export const TIER_COLORS: Record<string, string> = {
  "Very High": "#B91C1C",
  "High": "#B45309",
  "Moderate": "#B45309",
  "Low": theme.accent,
  "Minimal": theme.accent,
};

export const CATEGORY_COLORS: Record<string, string> = {
  lab: theme.gold,
  visit: theme.textPrimary,
  rx: theme.warning,
  procedure: theme.textSecondary,
};

export const SEVERITY_COLORS: Record<
  string,
  { bg: string; text: string; border: string }
> = {
  error: {
    bg: "rgba(185, 28, 28, 0.08)",
    text: "#B91C1C",
    border: "rgba(185, 28, 28, 0.25)",
  },
  warning: {
    bg: "rgba(180, 83, 9, 0.08)",
    text: "#B45309",
    border: "rgba(180, 83, 9, 0.25)",
  },
  info: {
    bg: theme.accentAlpha(0.08),
    text: ACCENT_LOCAL,
    border: theme.accentAlpha(0.25),
  },
};

export const EMPTY_MATERIAL: SutMaterialItem = {
  name: "",
  unit_price: 0,
  quantity: 1,
};

export const FACILITY_TIERS = [
  { value: "1_basamak", label: "1st Level (Family Doctor)" },
  { value: "2_basamak_resmi", label: "2nd Level Public" },
  { value: "3_basamak_resmi", label: "3rd Level Public" },
  { value: "egitim_arastirma", label: "Training & Research Hospital" },
  { value: "universite_devlet", label: "State University Hospital" },
  { value: "universite_vakif", label: "Foundation University Hospital" },
  { value: "2_3_basamak_ozel", label: "2nd/3rd Level Private" },
];

export const PATIENT_CATEGORIES = [
  { value: "diger", label: "Standard (Other)" },
  { value: "gelir_aylik_alan", label: "Pensioner / Income-Based" },
];

export function MethodologyBadge({ text }: { text: string }) {
  return (
    <div
      className="rounded-lg px-3 py-2 text-xs leading-relaxed"
      style={{
        background: theme.accentAlpha(0.06),
        border: `1px solid ${theme.accentAlpha(0.2)}`,
        color: "#71717A",
      }}
    >
      <span className="font-bold uppercase tracking-wider" style={{ color: theme.accent }}>
        100% Gazette Data
      </span>
      <span className="mx-1.5 text-[var(--gold-light)]">|</span>
      {text}
    </div>
  );
}
