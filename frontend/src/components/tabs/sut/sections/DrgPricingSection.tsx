"use client";

import { getDrgPricing } from "@/lib/api/sut";
import { useSutApi } from "../useSutApi";
import { DataTable, Surface } from "@/components/primitives";

type DrgData = {
  chapters: { chapter: string; name: string; ek2c_group: string; median_price: number }[];
  groups: { group: string; min: number; max: number }[];
};

export function DrgPricingSection() {
  const { data, error } = useSutApi<DrgData>(
    (opts) => getDrgPricing(opts),
    { enabled: true, errorFallback: "Failed to load DRG pricing" },
  );

  if (error) {
    return <p className="text-sm" style={{ color: "#B91C1C" }}>{error}</p>;
  }
  if (!data) return <div className="loading-state"><div className="loading-spinner" /></div>;
  return (
    <Surface variant="base" padding="md">
      <h4 className="text-sm font-bold mb-3" style={{ color: "#1A1A1A" }}>EK-2C DRG Package Pricing by ICD-10 Chapter</h4>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div>
          <DataTable className="text-[11px]">
            <thead><tr><th>Ch.</th><th>Description</th><th>Group</th><th>Median (TL)</th></tr></thead>
            <tbody>
              {data.chapters.map(c => (
                <tr key={c.chapter}>
                  <td style={{ fontWeight: 700 }}>{c.chapter}</td>
                  <td>{c.name}</td>
                  <td style={{ fontWeight: 600 }}>{c.ek2c_group}</td>
                  <td className="tabular-nums text-right">{c.median_price.toLocaleString("tr-TR")}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        </div>
        <div>
          <h5 className="text-xs font-semibold mb-2" style={{ color: "#71717A" }}>Group Price Ranges</h5>
          <DataTable className="text-[11px]">
            <thead><tr><th>Group</th><th>Min (TL)</th><th>Max (TL)</th></tr></thead>
            <tbody>
              {data.groups.map(g => (
                <tr key={g.group}>
                  <td style={{ fontWeight: 700 }}>{g.group}</td>
                  <td className="tabular-nums text-right">{g.min.toLocaleString("tr-TR")}</td>
                  <td className="tabular-nums text-right">{g.max.toLocaleString("tr-TR")}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        </div>
      </div>
    </Surface>
  );
}
