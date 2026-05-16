"use client";

import { getVisitPricing } from "@/lib/api/sut";
import { SutReferenceSectionSkeleton } from "@/components/skeletons/SutSkeletons";
import type { VisitPricingSpecialty } from "@/lib/domains/sut";
import { fmtTRY } from "../shared";
import { useSutApi } from "../useSutApi";

type VisitData = { specialties: VisitPricingSpecialty[] };

export function VisitPricingSection() {
  const { data, error } = useSutApi<VisitData>(
    (opts) => getVisitPricing(opts),
    { enabled: true, errorFallback: "Failed to load visit pricing" },
  );

  if (error) {
    return <p className="text-sm" style={{ color: "#B91C1C" }}>{error}</p>;
  }
  if (!data) return <SutReferenceSectionSkeleton title="Loading visit pricing" />;
  const tiers = ["A1", "A2", "B", "C", "D", "E"];
  return (
    <div className="frost-panel p-4 rounded-2xl">
      <h4 className="text-sm font-bold mb-3" style={{ color: "#1A1A1A" }}>EK-2A Outpatient Visit Pricing by Specialty</h4>
      <div style={{ maxHeight: 500, overflowY: "auto" }}>
        <table className="frost-table" style={{ fontSize: 10 }}>
          <thead>
            <tr>
              <th>Code</th><th>Specialty</th>
              {tiers.map(t => <th key={t} className="num-col">{t}</th>)}
            </tr>
          </thead>
          <tbody>
            {data.specialties.map((s, i) => {
              const prices = (s.prices_try ?? {}) as Record<string, number>;
              return (
                <tr key={i}>
                  <td style={{ fontWeight: 600, fontFamily: "monospace" }}>{String(s.code ?? "")}</td>
                  <td style={{ maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{String(s.name ?? "")}</td>
                  {tiers.map(t => <td key={t} className="num-col">{prices[t] != null ? fmtTRY(Number(prices[t])) : "--"}</td>)}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
