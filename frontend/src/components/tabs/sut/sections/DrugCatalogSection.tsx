"use client";

import { useEffect, useState, startTransition } from "react";
import { getDrugCatalog } from "@/lib/api/sut";
import type { DrugEntry } from "@/lib/api/sut";
import { SutReferenceSectionSkeleton } from "@/components/skeletons/SutSkeletons";
import { fmtNum, fmtPct } from "../shared";
import { DataTable, Surface } from "@/components/primitives";

export function DrugCatalogSection() {
  const [query, setQuery] = useState("");
  const [data, setData] = useState<{ drugs: DrugEntry[]; total: number; page: number; total_pages: number } | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    startTransition(() => {
      setLoading(true);
      setError(null);
    });
    getDrugCatalog({ q: query, page, per_page: 30 }, { signal: controller.signal })
      .then((d) => {
        if (!controller.signal.aborted) setData(d);
      })
      .catch((err) => {
        if (controller.signal.aborted || (err instanceof DOMException && err.name === "AbortError")) return;
        setData(null);
        setError(err instanceof Error ? err.message : "Failed to load drug catalog");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [query, page]);

  return (
    <Surface variant="base" padding="md">
      <h4 className="text-sm font-bold mb-3" style={{ color: "#1A1A1A" }}>
        EK-4A Drug Reimbursement Catalog ({data ? fmtNum(data.total) : "..."} drugs)
      </h4>
      <input
        type="text"
        placeholder="Search by drug name..."
        value={query}
        onChange={e => { setQuery(e.target.value); setPage(1); }}
        className="sut-input"
        style={{ marginBottom: 10, width: "100%", maxWidth: 400 }}
      />
      {loading ? (
        <SutReferenceSectionSkeleton title="Loading drug catalog" />
      ) : error ? (
        <p className="text-sm" style={{ color: "#B91C1C" }}>{error}</p>
      ) : data && data.drugs.length > 0 ? (
        <>
          <div style={{ maxHeight: 400, overflowY: "auto" }}>
            <DataTable className="text-[11px]">
              <thead><tr><th>Drug Name</th><th>Equivalence</th><th>Status</th><th>Tier 1</th><th>Passivated</th></tr></thead>
              <tbody>
                {data.drugs.map((d, i) => (
                  <tr key={i}>
                    <td style={{ fontWeight: 600, maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{String(d.drug_name ?? "")}</td>
                    <td style={{ fontSize: 10 }}>{String(d.equivalence_group ?? "--")}</td>
                    <td style={{ fontSize: 10 }}>{String(d.discount_status ?? "--")}</td>
                     <td className="tabular-nums text-right">{d.discount_tier_1 != null ? fmtPct(Number(d.discount_tier_1) * 100, 0) : "--"}</td>
                    <td style={{ fontSize: 10 }}>{d.passivation_date ? String(d.passivation_date) : "--"}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          </div>
          {data.total_pages > 1 && (
            <div style={{ display: "flex", justifyContent: "center", gap: 10, marginTop: 8, fontSize: 11, color: "#71717A" }}>
              <button disabled={page <= 1} onClick={() => setPage(p => p - 1)} className="sut-section-btn" style={{ padding: "3px 10px" }}>Prev</button>
               <span>Page {fmtNum(data.page)} / {fmtNum(data.total_pages)}</span>
              <button disabled={page >= data.total_pages} onClick={() => setPage(p => p + 1)} className="sut-section-btn" style={{ padding: "3px 10px" }}>Next</button>
            </div>
          )}
        </>
      ) : (
        <p className="text-sm text-[var(--text-secondary)]">No drugs found.</p>
      )}
    </Surface>
  );
}
