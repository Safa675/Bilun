"use client";

import { getCheckupPricing } from "@/lib/api/sut";
import { SutReferenceSectionSkeleton } from "@/components/skeletons/SutSkeletons";
import type {
  CheckupLabEntry,
  CheckupProcedureEntry,
  CheckupCopaymentInfo,
} from "@/lib/domains/sut";
import { fmtNum, fmtTRY2 } from "../shared";
import { useSutApi } from "../useSutApi";
import { DataTable, Surface } from "@/components/primitives";
import { useT } from "@/lib/i18n/useTranslations";

type CheckupData = {
  labs: CheckupLabEntry[];
  procedures: CheckupProcedureEntry[];
  copayment: CheckupCopaymentInfo;
  katsayi: number;
};

export function CheckupPricingSection() {
  const t = useT();
  const na = t("sections.checkupPricing.notAvailable");
  const { data, error } = useSutApi<CheckupData>(
    (opts) => getCheckupPricing(opts),
    { enabled: true, errorFallback: t("sections.checkupPricing.errors.loadFailed") },
  );

  if (error) {
    return <p className="text-sm" style={{ color: "#B91C1C" }}>{error}</p>;
  }
  if (!data) return <SutReferenceSectionSkeleton title={t("sections.checkupPricing.loadingTitle")} />;
  return (
    <Surface variant="base" padding="md">
      <h4 className="text-sm font-bold mb-3" style={{ color: "#1A1A1A" }}>
        {t("sections.checkupPricing.title", { katsayi: fmtNum(data.katsayi) })}
      </h4>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div>
          <h5 className="text-xs font-semibold mb-2" style={{ color: "#71717A" }}>
            {t("sections.checkupPricing.labTests", { count: fmtNum(data.labs.length) })}
          </h5>
          <div style={{ maxHeight: 350, overflowY: "auto" }}>
            <DataTable className="text-[11px]">
              <thead>
                <tr>
                  <th>{t("sections.checkupPricing.labTable.test")}</th>
                  <th>{t("sections.checkupPricing.labTable.sutCode")}</th>
                  <th>{t("sections.checkupPricing.labTable.tl")}</th>
                </tr>
              </thead>
              <tbody>
                {data.labs.map((l, i) => (
                  <tr key={i}>
                    <td>{String(l.sut_adi ?? l.name ?? "")}</td>
                    <td style={{ fontFamily: "monospace", fontSize: 10 }}>{String(l.sut_kodu ?? l.code ?? "")}</td>
                    <td className="tabular-nums text-right">{l.tl != null ? fmtTRY2(Number(l.tl)) : na}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          </div>
        </div>
        <div>
          <h5 className="text-xs font-semibold mb-2" style={{ color: "#71717A" }}>
            {t("sections.checkupPricing.procedures", { count: fmtNum(data.procedures.length) })}
          </h5>
          <div style={{ maxHeight: 350, overflowY: "auto" }}>
            <DataTable className="text-[11px]">
              <thead>
                <tr>
                  <th>{t("sections.checkupPricing.procedureTable.procedure")}</th>
                  <th>{t("sections.checkupPricing.procedureTable.sutCode")}</th>
                  <th>{t("sections.checkupPricing.procedureTable.tl")}</th>
                </tr>
              </thead>
              <tbody>
                {data.procedures.map((p, i) => (
                  <tr key={i}>
                    <td>{String(p.sut_adi ?? p.name ?? "")}</td>
                    <td style={{ fontFamily: "monospace", fontSize: 10 }}>{String(p.sut_kodu ?? p.code ?? "")}</td>
                    <td className="tabular-nums text-right">{p.tl != null ? fmtTRY2(Number(p.tl)) : na}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          </div>
        </div>
      </div>
    </Surface>
  );
}
