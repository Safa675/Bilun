"use client";

import { useT } from "@/lib/i18n/useTranslations";

export default function SkipToContent() {
  const t = useT();
  return (
    <a
      href="#main-content"
      className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-[9999] focus:bg-white focus:px-4 focus:py-2 focus:rounded-lg focus:shadow-lg focus:text-[var(--text-primary)] focus:font-semibold"
    >
      {t("shell.skipToContent")}
    </a>
  );
}
