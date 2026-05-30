import type { Locale } from "./types";

let moduleLocale: Locale = "en";

export function getModuleLocale(): Locale {
  return moduleLocale;
}

export function setModuleLocale(locale: Locale): void {
  moduleLocale = locale;
}

export function getIntlLocale(locale: Locale): string {
  return locale === "tr" ? "tr-TR" : "en-US";
}
