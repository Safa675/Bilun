import { getModuleLocale, getIntlLocale } from "./localeModule";

export function fmtNumber(
  value: number,
  options?: Intl.NumberFormatOptions,
): string {
  const locale = getIntlLocale(getModuleLocale());
  return new Intl.NumberFormat(locale, options).format(value);
}

export function fmtTRY(value: number): string {
  const locale = getModuleLocale();
  const formatted = fmtNumber(value, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });
  return locale === "tr" ? `₺${formatted}` : `${formatted} TRY`;
}

export function fmtTRY2(value: number): string {
  const locale = getModuleLocale();
  const formatted = fmtNumber(value, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return locale === "tr" ? `₺${formatted}` : `${formatted} TRY`;
}

export function fmtPct(value: number, decimals = 1): string {
  return `${fmtNumber(value, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}%`;
}

export function fmtNum(value: number): string {
  return fmtNumber(Math.round(value), { maximumFractionDigits: 0 });
}

/** Locale-aware short date (claim dates, service dates). */
export function fmtDate(
  iso: string | null | undefined,
  options?: Intl.DateTimeFormatOptions,
): string {
  if (!iso) return "—";
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) {
    return String(iso).slice(0, 10) || "—";
  }
  const locale = getIntlLocale(getModuleLocale());
  const formatOptions = options ?? { year: "numeric", month: "short", day: "numeric" };
  const isCivilDate = /^\d{4}-\d{2}-\d{2}$/.test(iso);
  // ISO date-only values are calendar dates, not instants in the browser's zone.
  // Reject normalized impossible days (e.g. February 30) using the existing fallback.
  if (isCivilDate && parsed.toISOString().slice(0, 10) !== iso) return iso;
  return parsed.toLocaleDateString(
    locale,
    isCivilDate ? { ...formatOptions, timeZone: "UTC" } : formatOptions,
  );
}

/** Locale-aware date + time (rejection timestamps, audit events). */
export function fmtDateTime(
  iso: string | null | undefined,
  options?: Intl.DateTimeFormatOptions,
): string {
  if (!iso) return "—";
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) {
    return String(iso).slice(0, 19) || "—";
  }
  const locale = getIntlLocale(getModuleLocale());
  return parsed.toLocaleString(
    locale,
    options ?? { dateStyle: "short", timeStyle: "short" },
  );
}
