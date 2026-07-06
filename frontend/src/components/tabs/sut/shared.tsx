import { theme } from "@/lib/theme";
import { ACCENT } from "@/lib/constants";
import type { SutMaterialItem } from "@/lib/api/sut";
import { translateMethodology } from "@/lib/apiMessages";
import { getSutDomainLabel, getSutPriorityLabel, getSutRiskTierLabel } from "../../../lib/sutLabels";
import { fmtNum as fmtNumLocale, fmtNumber, fmtPct as fmtPctLocale, fmtTRY as fmtTRYLocale, fmtTRY2 as fmtTRYLocale2 } from "@/lib/i18n/formatters";
import { translate } from "@/lib/i18n/translate";
import enMessages from "@/messages/en/index";
import trMessages from "@/messages/tr/index";
import { getModuleLocale } from "@/lib/i18n/localeModule";

const FACILITY_TIER_OPTIONS = [
  { value: "1_basamak", key: "1Basamak" },
  { value: "2_basamak_resmi", key: "2BasamakResmi" },
  { value: "3_basamak_resmi", key: "3BasamakResmi" },
  { value: "egitim_arastirma", key: "egitimArastirma" },
  { value: "universite_devlet", key: "universiteDevlet" },
  { value: "universite_vakif", key: "universiteVakif" },
  { value: "2_3_basamak_ozel", key: "2_3BasamakOzel" },
] as const;

const PATIENT_CATEGORY_OPTIONS = [
  { value: "diger", key: "diger" },
  { value: "gelir_aylik_alan", key: "gelirAylikAlan" },
] as const;

function localizedMessages() {
  return getModuleLocale() === "tr" ? trMessages : enMessages;
}

export const ACCENT_LOCAL = theme.accent;

function unavailableLabel(): string {
  const messages = getModuleLocale() === "tr" ? trMessages : enMessages;
  return translate(messages, "common.unavailable");
}

function localizedUnknown(): string {
  const messages = getModuleLocale() === "tr" ? trMessages : enMessages;
  return translate(messages, "common.unknown");
}

export function fmtTRY(value: number): string {
  return fmtTRYLocale(value);
}

export function fmtTRY2(value: number): string {
  return fmtTRYLocale2(value);
}

export function fmtTRYOrUnavailable(value: number | null | undefined): string {
  return value == null ? unavailableLabel() : fmtTRY(value);
}

export function fmtTRY2OrUnavailable(value: number | null | undefined): string {
  return value == null ? unavailableLabel() : fmtTRY2(value);
}

export function fmtNumOrUnavailable(value: number | null | undefined): string {
  return value == null ? unavailableLabel() : fmtNum(value);
}

export function fmtPct(value: number, decimals = 1): string {
  return fmtPctLocale(value, decimals);
}

export function fmtNum(value: number): string {
  return fmtNumLocale(value);
}

export function fmtPctRatio(value: number, decimals = 1): string {
  return fmtPct(value * 100, decimals);
}

export function fmtLabel(value: string | null | undefined): string {
  return getSutDomainLabel(value);
}

export function fmtPriorityLabel(value: string | null | undefined): string {
  return getSutPriorityLabel(value);
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
      <p className="text-xs font-medium text-[var(--text-muted)]">
        {label}
      </p>
      <p
        className="text-2xl font-semibold tabular-nums lining-nums leading-tight"
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
  code: "",
  unit_price: 0,
  quantity: 1,
};

export function MethodologyBadge({ text, badgeLabel }: { text: string; badgeLabel?: string }) {
  const resolvedBadgeLabel =
    badgeLabel ?? translate(localizedMessages(), "optimizer.methodology.gazetteData");
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
        {resolvedBadgeLabel}
      </span>
      <span className="mx-1.5 text-[var(--gold-light)]">|</span>
      {translateMethodology(text)}
    </div>
  );
}
