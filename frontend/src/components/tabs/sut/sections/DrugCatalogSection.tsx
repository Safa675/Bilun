"use client";

import { useEffect, useState, startTransition } from "react";
import { getDrugCatalog } from "@/lib/api/sut";
import type { DrugEntry } from "@/lib/api/sut";
import { SutReferenceSectionSkeleton } from "@/components/skeletons/SutSkeletons";
import { fmtNum, fmtPct } from "../shared";
import { DataTable, Surface } from "@/components/primitives";
import { useT } from "@/lib/i18n/useTranslations";

export function DrugCatalogSection() {
  const t = useT();
  const [query, setQuery] = useState("");
  const [data, setData] = useState<{ drugs: DrugEntry[]; total: number; page: number; total_pages: number } | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const na = t("sections.drugCatalog.notAvailable");

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
        setError(err instanceof Error ? err.message : t("sections.drugCatalog.errors.loadFailed"));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [query, page, t]);

  return (
    <Surface variant="base" padding="md">
      <h4 className="text-sm font-bold mb-3" style={{ color: "#1A1A1A" }}>
        {data
          ? t("sections.drugCatalog.title", { total: fmtNum(data.total) })
          : t("sections.drugCatalog.titleLoading")}
      </h4>
      <input
        type="text"
        placeholder={t("sections.drugCatalog.searchPlaceholder")}
        value={query}
        onChange={e => { setQuery(e.target.value); setPage(1); }}
        className="sut-input"
        style={{ marginBottom: 10, width: "100%", maxWidth: 400 }}
      />
      {loading ? (
        <SutReferenceSectionSkeleton title={t("sections.drugCatalog.loadingTitle")} />
      ) : error ? (
        <p className="text-sm" style={{ color: "#B91C1C" }}>{error}</p>
      ) : data && data.drugs.length > 0 ? (
        <>
          <div style={{ maxHeight: 400, overflowY: "auto" }}>
            <DataTable className="text-[11px]">
              <thead>
                <tr>
                  <th>{t("sections.drugCatalog.table.drugName")}</th>
                  <th>{t("sections.drugCatalog.table.equivalence")}</th>
                  <th>{t("sections.drugCatalog.table.status")}</th>
                  <th>{t("sections.drugCatalog.table.tier1")}</th>
                  <th>{t("sections.drugCatalog.table.passivated")}</th>
                </tr>
              </thead>
              <tbody>
                {data.drugs.map((d, i) => (
                  <tr key={i}>
                    <td style={{ fontWeight: 600, maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{String(d.drug_name ?? "")}</td>
                    <td style={{ fontSize: 10 }}>{String(d.equivalence_group ?? na)}</td>
                    <td style={{ fontSize: 10 }}>{String(d.discount_status ?? na)}</td>
                    <td className="tabular-nums text-right">{d.discount_tier_1 != null ? fmtPct(Number(d.discount_tier_1) * 100, 0) : na}</td>
                    <td style={{ fontSize: 10 }}>{d.passivation_date ? String(d.passivation_date) : na}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          </div>
          {data.total_pages > 1 && (
            <div style={{ display: "flex", justifyContent: "center", gap: 10, marginTop: 8, fontSize: 11, color: "#71717A" }}>
              <button disabled={page <= 1} onClick={() => setPage(p => p - 1)} className="sut-section-btn" style={{ padding: "3px 10px" }}>{t("sections.drugCatalog.pagination.prev")}</button>
              <span>{t("sections.drugCatalog.pagination.page", { page: fmtNum(data.page), totalPages: fmtNum(data.total_pages) })}</span>
              <button disabled={page >= data.total_pages} onClick={() => setPage(p => p + 1)} className="sut-section-btn" style={{ padding: "3px 10px" }}>{t("sections.drugCatalog.pagination.next")}</button>
            </div>
          )}
        </>
      ) : (
        <p className="text-sm text-[var(--text-secondary)]">{t("sections.drugCatalog.emptyState")}</p>
      )}
    </Surface>
  );
}
