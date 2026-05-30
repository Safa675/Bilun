import type { ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { LocaleProvider } from "@/lib/i18n/LocaleProvider";
import type { Locale } from "@/lib/i18n/types";

export function renderToStaticMarkupWithLocale(
  ui: ReactElement,
  locale: Locale = "en",
): string {
  return renderToStaticMarkup(
    <LocaleProvider initialLocale={locale}>{ui}</LocaleProvider>,
  );
}
