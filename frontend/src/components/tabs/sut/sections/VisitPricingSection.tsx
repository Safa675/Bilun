"use client";

import { getVisitPricing } from "@/lib/api/sut";
import { SutReferenceSectionSkeleton } from "@/components/skeletons/SutSkeletons";
import type { VisitPricingSpecialty } from "@/lib/domains/sut";
import { fmtTRY } from "../shared";
import { useSutApi } from "../useSutApi";
import { DataTable, Surface } from "@/components/primitives";
import { useT } from "@/lib/i18n/useTranslations";

type VisitData = { specialties: VisitPricingSpecialty[] };

export function VisitPricingSection() {
  const t = useT();
  const na = t("sections.visitPricing.notAvailable");
  const { data, error } = useSutApi<VisitData>(
    (opts) => getVisitPricing(opts),
    { enabled: true, errorFallback: t("sections.visitPricing.errors.loadFailed") },
  );

  if (error) {
    return <p className="text-sm" style={{ color: "#B91C1C" }}>{error}</p>;
  }
  if (!data) return <SutReferenceSectionSkeleton title={t("sections.visitPricing.loadingTitle")} />;
  const tiers = [
    { key: "A1", label: t("sections.visitPricing.table.tierA1") },
    { key: "A2", label: t("sections.visitPricing.table.tierA2") },
    { key: "B", label: t("sections.visitPricing.table.tierB") },
    { key: "C", label: t("sections.visitPricing.table.tierC") },
    { key: "D", label: t("sections.visitPricing.table.tierD") },
    { key: "E", label: t("sections.visitPricing.table.tierE") },
  ];
  return (
    <Surface variant="base" padding="md">
      <h4 className="text-sm font-bold mb-3" style={{ color: "#1A1A1A" }}>{t("sections.visitPricing.title")}</h4>
      <div style={{ maxHeight: 500, overflowY: "auto" }}>
        <DataTable className="text-[10px]">
          <thead>
            <tr>
              <th>{t("sections.visitPricing.table.code")}</th>
              <th>{t("sections.visitPricing.table.specialty")}</th>
              {tiers.map(tier => <th key={tier.key} className="tabular-nums text-right">{tier.label}</th>)}
            </tr>
          </thead>
          <tbody>
            {data.specialties.map((s, i) => {
              const prices = (s.prices_try ?? {}) as Record<string, number>;
              return (
                <tr key={i}>
                  <td style={{ fontWeight: 600, fontFamily: "monospace" }}>{String(s.code ?? "")}</td>
                  <td style={{ maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{String(s.name ?? "")}</td>
                  {tiers.map(tier => <td key={tier.key} className="tabular-nums text-right">{prices[tier.key] != null ? fmtTRY(Number(prices[tier.key])) : na}</td>)}
                </tr>
              );
            })}
          </tbody>
        </DataTable>
      </div>
    </Surface>
  );
}
