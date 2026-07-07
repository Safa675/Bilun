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
  return parsed.toLocaleDateString(
    locale,
    options ?? { year: "numeric", month: "short", day: "numeric" },
  );
}
