"use client";

import { getDrgPricing } from "@/lib/api/sut";
import { useSutApi } from "../useSutApi";
import { DataTable, Surface } from "@/components/primitives";
import { fmtNum } from "../shared";
import { useT } from "@/lib/i18n/useTranslations";

type DrgData = {
  chapters: { chapter: string; name: string; ek2c_group: string; median_price: number }[];
  groups: { group: string; min: number; max: number }[];
};

export function DrgPricingSection() {
  const t = useT();
  const { data, error } = useSutApi<DrgData>(
    (opts) => getDrgPricing(opts),
    { enabled: true, errorFallback: t("sections.drgPricing.errors.loadFailed") },
  );

  if (error) {
    return <p className="text-sm" style={{ color: "#B91C1C" }}>{error}</p>;
  }
  if (!data) return <div className="loading-state"><div className="loading-spinner" /></div>;
  return (
    <Surface variant="base" padding="md">
      <h4 className="text-sm font-bold mb-3" style={{ color: "#1A1A1A" }}>{t("sections.drgPricing.title")}</h4>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div>
          <DataTable className="text-[11px]">
            <thead>
              <tr>
                <th>{t("sections.drgPricing.table.chapter")}</th>
                <th>{t("sections.drgPricing.table.description")}</th>
                <th>{t("sections.drgPricing.table.group")}</th>
                <th>{t("sections.drgPricing.table.medianTl")}</th>
              </tr>
            </thead>
            <tbody>
              {data.chapters.map(c => (
                <tr key={c.chapter}>
                  <td style={{ fontWeight: 700 }}>{c.chapter}</td>
                  <td>{c.name}</td>
                  <td style={{ fontWeight: 600 }}>{c.ek2c_group}</td>
                  <td className="tabular-nums text-right">{fmtNum(c.median_price)}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        </div>
        <div>
          <h5 className="text-xs font-semibold mb-2" style={{ color: "#71717A" }}>{t("sections.drgPricing.groupPriceRanges")}</h5>
          <DataTable className="text-[11px]">
            <thead>
              <tr>
                <th>{t("sections.drgPricing.groupTable.group")}</th>
                <th>{t("sections.drgPricing.groupTable.minTl")}</th>
                <th>{t("sections.drgPricing.groupTable.maxTl")}</th>
              </tr>
            </thead>
            <tbody>
              {data.groups.map(g => (
                <tr key={g.group}>
                  <td style={{ fontWeight: 700 }}>{g.group}</td>
                  <td className="tabular-nums text-right">{fmtNum(g.min)}</td>
                  <td className="tabular-nums text-right">{fmtNum(g.max)}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        </div>
      </div>
    </Surface>
  );
}
