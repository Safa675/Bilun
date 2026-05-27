"use client";

import Link from "next/link";
import { useEffect } from "react";
import { Surface } from "@/components/primitives";
import { buildSutHomeHref, SUT_BRAND } from "@/lib/constants";

export default function SutError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
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
            Something went wrong in the SUT workspace
          </h1>
          <p className="mt-3 text-sm text-[var(--text-secondary)]">
            The current screen could not be rendered. Try again, or return to the main SUT workspace.
          </p>
          <p className="mt-4 rounded-[var(--r-md)] bg-[color-mix(in_srgb,var(--danger)_6%,transparent)] px-4 py-3 text-left text-sm text-[var(--danger)]">
            {error.message || "Unexpected SUT application error."}
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <button
              type="button"
              onClick={reset}
              className="sut-section-btn sut-section-btn-active"
            >
              Try again
            </button>
            <Link href={buildSutHomeHref("analytics")} className="sut-section-btn">
              Back to SUT workspace
            </Link>
          </div>
        </Surface>
      </section>
    </main>
  );
}
