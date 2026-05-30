"use client";

import { cn } from "@/lib/cn";
import { useLocale, useLocaleContext } from "@/lib/i18n/LocaleProvider";
import { useT } from "@/lib/i18n/useTranslations";
import type { Locale } from "@/lib/i18n/types";

const LOCALES: { id: Locale; flag: string; labelKey: string }[] = [
  { id: "en", flag: "🇬🇧", labelKey: "shell.locale.en" },
  { id: "tr", flag: "🇹🇷", labelKey: "shell.locale.tr" },
];

export default function LocaleSwitcher() {
  const locale = useLocale();
  const { setLocale } = useLocaleContext();
  const t = useT();

  return (
    <div
      className="inline-flex items-center gap-0.5 rounded-[var(--r-md)] border border-[var(--border-subtle)] bg-[var(--surface-base)] p-0.5"
      role="group"
      aria-label={t("shell.locale.groupLabel")}
    >
      {LOCALES.map((item) => {
        const active = locale === item.id;
        return (
          <button
            key={item.id}
            type="button"
            onClick={() => setLocale(item.id)}
            aria-pressed={active}
            aria-label={t(item.labelKey)}
            title={t(item.labelKey)}
            className={cn(
              "inline-flex h-7 min-w-[2rem] items-center justify-center rounded-[var(--r-sm)] px-1.5 text-sm transition-colors",
              active
                ? "bg-[var(--gold-subtle)] ring-1 ring-[var(--gold)]"
                : "hover:bg-[var(--surface-tint)]",
            )}
          >
            <span aria-hidden="true">{item.flag}</span>
          </button>
        );
      })}
    </div>
  );
}
