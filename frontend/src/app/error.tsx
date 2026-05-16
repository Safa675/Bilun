"use client";

import Link from "next/link";
import { useEffect } from "react";
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
    <main id="main-content" className="min-h-screen px-6 py-8" style={{ background: "#FAFAF9" }}>
      <section className="mx-auto flex min-h-[70vh] max-w-3xl items-center justify-center">
        <div className="frost-panel w-full rounded-3xl p-8 text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.28em]" style={{ color: "#059669" }}>
            {SUT_BRAND.moduleLabel}
          </p>
          <h1 className="mt-4 text-3xl font-bold text-slate-950">Something went wrong in the SUT workspace</h1>
          <p className="mt-3 text-sm text-slate-600">
            The current screen could not be rendered. Try again, or return to the main SUT workspace.
          </p>
          <p className="mt-4 rounded-2xl px-4 py-3 text-left text-sm" style={{ background: "rgba(185, 28, 28, 0.04)", color: "#B91C1C" }}>
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
        </div>
      </section>
    </main>
  );
}
