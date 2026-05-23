"use client";

import { getLabPrices } from "@/lib/api/sut";
import { SutReferenceSectionSkeleton } from "@/components/skeletons/SutSkeletons";
import { ACCENT_LOCAL, fmtNum, fmtTRY2 } from "../shared";
import { useSutApi } from "../useSutApi";

export function LabPricesSection() {
  const { data, error } = useSutApi(
    (opts) => getLabPrices(opts),
    { enabled: true, errorFallback: "Failed to load lab prices" },
  );

  if (error) {
    return <p className="text-sm" style={{ color: "#B91C1C" }}>{error}</p>;
  }
  if (!data) return <SutReferenceSectionSkeleton title="Loading lab prices" />;
  return (
    <div className="frost-panel p-4 rounded-2xl">
      <h4 className="text-sm font-bold mb-3" style={{ color: "#1A1A1A" }}>BILUN Lab Test → SUT Code Mapping ({fmtNum(data.total)} tests)</h4>
      <table className="frost-table" style={{ fontSize: 12 }}>
        <thead><tr><th>Test Name</th><th>SUT Code</th><th>Gazette Price (TL)</th></tr></thead>
        <tbody>
          {data.tests.map(t => (
            <tr key={t.test_name}>
              <td style={{ fontWeight: 600 }}>{t.test_name}</td>
              <td style={{ fontFamily: "monospace", fontSize: 11 }}>{t.sut_code}</td>
              <td className="num-col" style={{ fontWeight: 600, color: ACCENT_LOCAL }}>{fmtTRY2(t.price_try)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
