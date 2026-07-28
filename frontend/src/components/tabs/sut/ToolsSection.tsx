"use client";

import { useMemo, useState } from "react";
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
import { Chip, Surface, Button, buttonActiveClass } from "@/components/primitives";
import { cn } from "@/lib/cn";
import { useT } from "@/lib/i18n/useTranslations";

export function ReferenceToolsContent() {
  const t = useT();

  return (
    <div>
      <div className="mb-4 flex items-center gap-3">
        <span className="h-px flex-1 bg-[var(--border-subtle)]" />
        <span className="whitespace-nowrap text-[0.72rem] font-extrabold uppercase tracking-[0.16em] text-[var(--gold)]">
          {t("sections.tools.dividerLabel")}
        </span>
        <span className="h-px flex-1 bg-[var(--border-subtle)]" />
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
  | "lab_prices";

const BILLING_SUB_IDS: BillingToolSubSection[] = [
  "validator",
  "search",
  "bundled",
  "price_history",
  "visits",
  "drugs",
  "specialty",
  "lab_prices",
];

const BILLING_SUB_KEY = {
  validator: "validator",
  search: "search",
  bundled: "bundled",
  price_history: "priceHistory",
  visits: "visits",
  drugs: "drugs",
  specialty: "specialty",
  lab_prices: "labPrices",
} as const satisfies Record<BillingToolSubSection, string>;

function BillingToolsSection() {
  const t = useT();
  const [activeSub, setActiveSub] = useState<BillingToolSubSection>("validator");

  const billingSubs = useMemo(
    () =>
      BILLING_SUB_IDS.map((id) => ({
        id,
        label: t(`sections.tools.subs.${BILLING_SUB_KEY[id]}`),
      })),
    [t],
  );

  const { data: optData, loading: optLoading, error: optError } = useSutApi<OptimizationSummary>(
    (opts) => getOptimizationSummary(opts),
    {
      enabled: activeSub === "price_history",
      abortMessage: t("sections.tools.priceHistory.abortMessage"),
      errorFallback: t("sections.tools.priceHistory.errorFallback"),
    },
  );

  return (
    <div className="space-y-4">
      <div className="flex gap-2 flex-wrap">
        {billingSubs.map((sub) => (
          <Button
            key={sub.id}
            variant="secondary"
            size="compact"
            onClick={() => setActiveSub(sub.id)}
            className={cn(activeSub === sub.id && buttonActiveClass)}
          >
            <span className="text-xs font-semibold">{sub.label}</span>
          </Button>
        ))}
      </div>

      {activeSub === "validator" && <ClaimValidatorSection />}
      {activeSub === "search" && <MaterialPricingSection />}
      {activeSub === "bundled" && <BundledConsumablesSection />}
      {activeSub === "price_history" && (
        optLoading ? (
          <SutReferenceSectionSkeleton title={t("sections.tools.priceHistory.loadingTitle")} />
        ) : optError ? (
          <Surface variant="base" padding="lg" className="text-center">
            <Chip variant="danger">{optError}</Chip>
          </Surface>
        ) : optData ? (
          <TemporalPriceSection data={optData} />
        ) : (
          <Surface variant="base" padding="lg" className="text-center">
            <p className="text-sm text-[var(--text-secondary)]">
              {t("sections.tools.priceHistory.emptyState")}
            </p>
          </Surface>
        )
      )}
      {activeSub === "visits" && <VisitPricingSection />}
      {activeSub === "drugs" && <DrugCatalogSection />}
      {activeSub === "specialty" && <SpecialtyMaterialSection />}
      {activeSub === "lab_prices" && <LabPricesSection />}
    </div>
  );
}
