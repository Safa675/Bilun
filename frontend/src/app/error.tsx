"use client";

import Link from "next/link";
import { useEffect } from "react";
import { Surface, Button, buttonActiveClass } from "@/components/primitives";
import { buildSutHomeHref, SUT_BRAND } from "@/lib/constants";
import { useT } from "@/lib/i18n/useTranslations";

export default function SutError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const t = useT();

  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main id="main-content" className="min-h-screen bg-[var(--surface-base)] px-6 py-8">
      <section className="mx-auto flex min-h-[70vh] max-w-3xl items-center justify-center">
        <Surface variant="soft" padding="lg" className="w-full text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-[var(--gold)]">
            {SUT_BRAND.moduleLabel}
          </p>
          <h1 className="mt-4 font-[var(--font-display)] text-3xl font-medium text-[var(--text-primary)]">
            {t("app.error.title")}
          </h1>
          <p className="mt-3 text-sm text-[var(--text-secondary)]">
            {t("app.error.description")}
          </p>
          <p className="mt-4 rounded-[var(--r-md)] bg-[color-mix(in_srgb,var(--danger)_6%,transparent)] px-4 py-3 text-left text-sm text-[var(--danger)]">
            {error.message || t("app.error.fallbackMessage")}
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Button
              variant="secondary"
              className={buttonActiveClass}
              onClick={reset}
            >
              {t("app.error.tryAgain")}
            </Button>
            <Button asChild variant="secondary">
              <Link href={buildSutHomeHref("patients")}>
                {t("app.error.backToWorkspace")}
              </Link>
            </Button>
          </div>
        </Surface>
      </section>
    </main>
  );
}
