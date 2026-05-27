"use client";

import { useMemo, useState } from "react";
import { getSutBundledConsumables } from "@/lib/api/sut";
import type { SutBundledConsumablesResult } from "@/lib/api/sut";
import { SutReferenceSectionSkeleton } from "@/components/skeletons/SutSkeletons";
import { ACCENT_LOCAL, fmtNum, KpiCard } from "../shared";
import { useSutApi } from "../useSutApi";
import { Chip, DataTable, Surface } from "@/components/primitives";

export function BundledConsumablesSection() {
  const { data, loading, error } = useSutApi<SutBundledConsumablesResult>(
    (opts) => getSutBundledConsumables(opts),
    { enabled: true, errorFallback: "Failed to load bundled consumables" },
  );
  const [filterText, setFilterText] = useState("");

  const filteredBundled = useMemo(() => {
    if (!data) return [];
    const lc = filterText.toLowerCase();
    if (!lc) return data.bundled_consumables.items;
    return data.bundled_consumables.items.filter(
      (item) =>
        item.item_name.toLowerCase().includes(lc) ||
        item.description.toLowerCase().includes(lc) ||
        item.bundled_in.toLowerCase().includes(lc)
    );
  }, [data, filterText]);

  if (loading && !data) return <SutReferenceSectionSkeleton title="Loading bundled consumables" />;

  if (error) {
    return (
      <Surface variant="soft" padding="md">
        <Chip variant="danger">{error}</Chip>
      </Surface>
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3">
        <KpiCard label="Bundled Items" value={fmtNum(data.bundled_consumables.count)} valueColor={ACCENT_LOCAL} />
        <KpiCard label="Exclusion Categories" value={fmtNum(data.exclusion_categories.count)} valueColor="#B45309" />
      </div>

      <Surface variant="base" padding="lg">
        <div className="flex items-center justify-between gap-3 mb-3">
          <h3 className="text-sm font-semibold uppercase tracking-wider" style={{ color: ACCENT_LOCAL }}>EK-3B-1 Bundled Consumables</h3>
          <input type="text" value={filterText} onChange={(e) => setFilterText(e.target.value)} className="sut-input max-w-[240px]" placeholder="Filter items..." />
        </div>
        <div className="text-xs mb-2" style={{ color: "#A1A1AA" }}>{fmtNum(filteredBundled.length)} of {fmtNum(data.bundled_consumables.count)} items</div>
        <div className="max-h-[360px] overflow-y-auto">
          <DataTable>
            <thead>
              <tr>
                <th className="text-left">#</th>
                <th className="text-left">Item Name</th>
                <th className="text-left">Category</th>
                <th className="text-left">Effective Date</th>
              </tr>
            </thead>
            <tbody>
              {filteredBundled.map((item, i) => (
                <tr key={i}>
                  <td className="text-left text-xs tabular-nums" style={{ color: "#A1A1AA" }}>{fmtNum(i + 1)}</td>
                  <td className="text-left text-sm" style={{ color: "#1A1A1A" }}>{item.item_name}</td>
                  <td className="text-left text-xs" style={{ color: "#71717A" }}>{item.bundled_in}</td>
                  <td className="text-left text-xs font-mono" style={{ color: "#A1A1AA" }}>{item.effective_date}</td>
                </tr>
              ))}
              {filteredBundled.length === 0 && (
                <tr><td colSpan={4} className="text-center text-sm py-6" style={{ color: "#A1A1AA" }}>No items match the filter.</td></tr>
              )}
            </tbody>
          </DataTable>
        </div>
      </Surface>

      <Surface variant="base" padding="lg">
        <h3 className="text-sm font-semibold uppercase tracking-wider mb-3" style={{ color: ACCENT_LOCAL }}>EK-3B Non-Reimbursable Exclusion Categories</h3>
        <div className="space-y-2">
          {data.exclusion_categories.categories.map((cat, i) => (
            <div key={i} className="rounded-xl p-3" style={{ background: "rgba(180, 83, 9, 0.06)", border: "1px solid rgba(180, 83, 9, 0.18)" }}>
              <div className="text-sm font-semibold" style={{ color: "#1A1A1A" }}>{cat.material_name}</div>
              <div className="text-xs mt-0.5" style={{ color: "#71717A" }}>{cat.section} &middot; {cat.description}</div>
            </div>
          ))}
        </div>
      </Surface>
    </div>
  );
}
