"use client";

import { useState } from "react";
import { getOptimizationSummary } from "@/lib/api/sut";
import type { OptimizationSummary } from "@/lib/domains/sut";
import { useSutApi } from "./useSutApi";
import { SutReferenceSectionSkeleton } from "@/components/skeletons/SutSkeletons";
import { ClaimValidatorSection } from "./sections/ClaimValidatorSection";
import { MaterialPricingSection } from "./sections/MaterialPricingSection";
import { BundledConsumablesSection } from "./sections/BundledConsumablesSection";
import { TemporalPriceSection } from "./sections/TemporalPriceSection";
import { VisitPricingSection } from "./sections/VisitPricingSection";
import { DrugCatalogSection } from "./sections/DrugCatalogSection";
import { SpecialtyMaterialSection } from "./sections/SpecialtyMaterialSection";
import { LabPricesSection } from "./sections/LabPricesSection";
import { CheckupPricingSection } from "./sections/CheckupPricingSection";

export function ReferenceToolsContent() {
  return (
    <div>
      <div className="sut-section-divider mb-4">
        <span className="sut-section-divider-label">Billing &amp; Gazette Tools</span>
      </div>
      <BillingToolsSection />
    </div>
  );
}

type BillingToolSubSection =
  | "validator"
  | "search"
  | "bundled"
  | "price_history"
  | "visits"
  | "drugs"
  | "specialty"
  | "lab_prices"
  | "checkup";

const BILLING_SUBS: { id: BillingToolSubSection; label: string }[] = [
  { id: "validator", label: "Claim Validator" },
  { id: "search", label: "Material Search" },
  { id: "bundled", label: "Bundled Items" },
  { id: "price_history", label: "Price History" },
  { id: "visits", label: "Visit Pricing" },
  { id: "drugs", label: "Drug Catalog" },
  { id: "specialty", label: "By Specialty" },
  { id: "lab_prices", label: "Lab Prices" },
  { id: "checkup", label: "Checkup" },
];

function BillingToolsSection() {
  const [activeSub, setActiveSub] = useState<BillingToolSubSection>("validator");

  const { data: optData, loading: optLoading, error: optError } = useSutApi<OptimizationSummary>(
    (opts) => getOptimizationSummary(opts),
    {
      enabled: activeSub === "price_history",
      abortMessage: "Price history load was interrupted. Reopen the tab to retry.",
      errorFallback: "Price history data not available.",
    },
  );

  return (
    <div className="space-y-4">
      <div className="flex gap-2 flex-wrap">
        {BILLING_SUBS.map((sub) => (
          <button
            key={sub.id}
            type="button"
            onClick={() => setActiveSub(sub.id)}
            className={`sut-section-btn sut-section-btn-compact ${activeSub === sub.id ? "sut-section-btn-active" : ""}`}
          >
            <span className="text-xs font-semibold">{sub.label}</span>
          </button>
        ))}
      </div>

      {activeSub === "validator" && <ClaimValidatorSection />}
      {activeSub === "search" && <MaterialPricingSection />}
      {activeSub === "bundled" && <BundledConsumablesSection />}
      {activeSub === "price_history" && (
        optLoading ? (
          <SutReferenceSectionSkeleton title="Loading price history data" />
        ) : optError ? (
          <div className="frost-panel sut-premium-error rounded-2xl p-6 text-center">
            <p className="sut-premium-error-title text-sm">{optError}</p>
          </div>
        ) : optData ? (
          <TemporalPriceSection data={optData} />
        ) : (
          <div className="frost-panel rounded-2xl p-6 text-center">
            <p className="sut-section-description text-sm">Price history data not available.</p>
          </div>
        )
      )}
      {activeSub === "visits" && <VisitPricingSection />}
      {activeSub === "drugs" && <DrugCatalogSection />}
      {activeSub === "specialty" && <SpecialtyMaterialSection />}
      {activeSub === "lab_prices" && <LabPricesSection />}
      {activeSub === "checkup" && <CheckupPricingSection />}
    </div>
  );
}
