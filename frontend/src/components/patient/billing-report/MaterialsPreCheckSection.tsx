"use client";

import type { BillingActionReport } from "@/lib/domains/sut";
import { useT } from "@/lib/i18n/useTranslations";
import { isExactOutput } from "@/lib/sutExactness";
import { MaterialBundlingScopeNotice } from "@/components/sut/MaterialBundlingScopeNotice";
import { SpecialtyProseScopeNotice } from "@/components/sut/SpecialtyProseScopeNotice";
import { ExactnessBlock as ExactnessNotice } from "@/components/primitives";
import { BillingSectionShell } from "./shared";
import {
  MaterialPreAuthorizationTable,
  MaterialMiatIntervalTable,
  MaterialMiatCatalogTable,
  BundledMaterialTable,
  MaterialProseViolationsTable,
  MaterialSpecialtyProseTable,
  MaterialKdvReviewTable,
  MaterialCeilingBenchmarks,
} from "./MaterialsPreCheckTables";

export function MaterialsPreCheckSection({ materialsData }: { materialsData: BillingActionReport["materials"] }) {
  const t = useT();
  const ceilingEntries = Object.entries(materialsData.gazette_ceiling_by_specialty);
  const materialsExact = isExactOutput(materialsData);
  const intervalViolations = materialsData.miat_interval_violations ?? [];
  const bundledLines = materialsData.bundled_separate_billing ?? [];
  const proseViolations = materialsData.prose_bundling_violations ?? [];
  const specialtyProseViolations = materialsData.specialty_prose_violations ?? [];
  const kdvPriceReviews = materialsData.kdv_price_reviews ?? [];
  const hasExactListData =
    materialsData.pre_auth_required.length > 0 ||
    materialsData.miat_restricted.length > 0 ||
    intervalViolations.length > 0 ||
    bundledLines.length > 0 ||
    proseViolations.length > 0 ||
    specialtyProseViolations.length > 0 ||
    kdvPriceReviews.length > 0;
  const hasAnyData = hasExactListData || ceilingEntries.length > 0;

  if (!hasAnyData && materialsExact) {
    return null;
  }

  return (
    <BillingSectionShell id="materials-pre-check" title={t("billing.materials.title")}>
      <div className="space-y-4">
        <p className="text-xs leading-relaxed text-[var(--text-secondary)]">
          {t("billing.materials.advisoryFootnote")}
        </p>
        <MaterialBundlingScopeNotice scope={materialsData.coverage_scope} compact />
        <SpecialtyProseScopeNotice scope={materialsData.specialty_coverage_scope} compact />
        {!materialsExact && (
          <ExactnessNotice block={materialsData} fallback={t("billing.materials.unavailable")} />
        )}
        {materialsData.pre_auth_required.length > 0 && <MaterialPreAuthorizationTable rows={materialsData.pre_auth_required} />}

        {intervalViolations.length > 0 && <MaterialMiatIntervalTable rows={intervalViolations} />}

        {materialsData.miat_restricted.length > 0 && <MaterialMiatCatalogTable rows={materialsData.miat_restricted} />}

        {bundledLines.length > 0 && <BundledMaterialTable rows={bundledLines} />}

        {proseViolations.length > 0 && <MaterialProseViolationsTable rows={proseViolations} />}

        {specialtyProseViolations.length > 0 && <MaterialSpecialtyProseTable rows={specialtyProseViolations} />}

        {kdvPriceReviews.length > 0 && <MaterialKdvReviewTable rows={kdvPriceReviews} />}

        {!materialsExact && ceilingEntries.length > 0 && (
          <p className="text-sm text-[var(--text-secondary)]">
            {t("billing.materials.partialBenchmarkNotice")}
          </p>
        )}

        {ceilingEntries.length > 0 && <MaterialCeilingBenchmarks entries={ceilingEntries} />}
      </div>
    </BillingSectionShell>
  );
}
