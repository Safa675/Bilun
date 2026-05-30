"use client";

import { getLabPrices } from "@/lib/api/sut";
import { SutReferenceSectionSkeleton } from "@/components/skeletons/SutSkeletons";
import { ACCENT_LOCAL, fmtNum, fmtTRY2 } from "../shared";
import { useSutApi } from "../useSutApi";
import { DataTable, Surface } from "@/components/primitives";
import { useT } from "@/lib/i18n/useTranslations";

export function LabPricesSection() {
  const t = useT();
  const { data, error } = useSutApi(
    (opts) => getLabPrices(opts),
    { enabled: true, errorFallback: t("sections.labPrices.errors.loadFailed") },
  );

  if (error) {
    return <p className="text-sm" style={{ color: "#B91C1C" }}>{error}</p>;
  }
  if (!data) return <SutReferenceSectionSkeleton title={t("sections.labPrices.loadingTitle")} />;
  return (
    <Surface variant="base" padding="md">
      <h4 className="text-sm font-bold mb-3" style={{ color: "#1A1A1A" }}>
        {t("sections.labPrices.title", { total: fmtNum(data.total) })}
      </h4>
      <DataTable className="text-xs">
        <thead>
          <tr>
            <th>{t("sections.labPrices.table.testName")}</th>
            <th>{t("sections.labPrices.table.sutCode")}</th>
            <th>{t("sections.labPrices.table.gazettePriceTl")}</th>
          </tr>
        </thead>
        <tbody>
          {data.tests.map(test => (
            <tr key={test.test_name}>
              <td style={{ fontWeight: 600 }}>{test.test_name}</td>
              <td style={{ fontFamily: "monospace", fontSize: 11 }}>{test.sut_code}</td>
              <td className="tabular-nums text-right" style={{ fontWeight: 600, color: ACCENT_LOCAL }}>{fmtTRY2(test.price_try)}</td>
            </tr>
          ))}
        </tbody>
      </DataTable>
    </Surface>
  );
}
