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

type CheckupData = {
  labs: CheckupLabEntry[];
  procedures: CheckupProcedureEntry[];
  copayment: CheckupCopaymentInfo;
  katsayi: number;
};

export function CheckupPricingSection() {
  const { data, error } = useSutApi<CheckupData>(
    (opts) => getCheckupPricing(opts),
    { enabled: true, errorFallback: "Failed to load checkup pricing" },
  );

  if (error) {
    return <p className="text-sm" style={{ color: "#B91C1C" }}>{error}</p>;
  }
  if (!data) return <SutReferenceSectionSkeleton title="Loading checkup pricing" />;
  return (
    <Surface variant="base" padding="md">
      <h4 className="text-sm font-bold mb-3" style={{ color: "#1A1A1A" }}>Checkup Package Pricing (katsayi: {fmtNum(data.katsayi)})</h4>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div>
          <h5 className="text-xs font-semibold mb-2" style={{ color: "#71717A" }}>Lab Tests ({fmtNum(data.labs.length)})</h5>
          <div style={{ maxHeight: 350, overflowY: "auto" }}>
            <DataTable className="text-[11px]">
              <thead><tr><th>Test</th><th>SUT Code</th><th>TL</th></tr></thead>
              <tbody>
                {data.labs.map((l, i) => (
                  <tr key={i}>
                    <td>{String(l.sut_adi ?? l.name ?? "")}</td>
                    <td style={{ fontFamily: "monospace", fontSize: 10 }}>{String(l.sut_kodu ?? l.code ?? "")}</td>
                    <td className="tabular-nums text-right">{l.tl != null ? fmtTRY2(Number(l.tl)) : "--"}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          </div>
        </div>
        <div>
          <h5 className="text-xs font-semibold mb-2" style={{ color: "#71717A" }}>Procedures ({fmtNum(data.procedures.length)})</h5>
          <div style={{ maxHeight: 350, overflowY: "auto" }}>
            <DataTable className="text-[11px]">
              <thead><tr><th>Procedure</th><th>SUT Code</th><th>TL</th></tr></thead>
              <tbody>
                {data.procedures.map((p, i) => (
                  <tr key={i}>
                    <td>{String(p.sut_adi ?? p.name ?? "")}</td>
                    <td style={{ fontFamily: "monospace", fontSize: 10 }}>{String(p.sut_kodu ?? p.code ?? "")}</td>
                    <td className="tabular-nums text-right">{p.tl != null ? fmtTRY2(Number(p.tl)) : "--"}</td>
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
