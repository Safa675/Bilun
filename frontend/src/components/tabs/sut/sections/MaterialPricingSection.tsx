"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getSutMaterialPricing } from "@/lib/api/sut";
import type { SutMaterialPricingResult } from "@/lib/api/sut";
import { ACCENT_LOCAL, fmtTRY2 } from "../shared";
import { Chip, DataTable, Surface, Button, inputClass } from "@/components/primitives";
import { useT } from "@/lib/i18n/useTranslations";
import { getModuleLocale } from "@/lib/i18n/localeModule";

export function MaterialPricingSection() {
  const t = useT();
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SutMaterialPricingResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const handleSearch = useCallback(async () => {
    const q = query.trim();
    if (!q) {
      setError(t("sections.materialPricing.errors.enterQuery"));
      return;
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await getSutMaterialPricing(q, { signal: controller.signal });
      if (!controller.signal.aborted) setResult(res);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      setError(err instanceof Error ? err.message : t("sections.materialPricing.errors.searchFailed"));
    } finally {
      if (abortRef.current === controller) { setLoading(false); abortRef.current = null; }
    }
  }, [query, t]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSearch();
  }, [handleSearch]);

  useEffect(() => {
    return () => { abortRef.current?.abort(); };
  }, []);

  return (
    <div className="space-y-5">
      <Surface variant="base" padding="lg">
        <h3 className="text-sm font-semibold uppercase tracking-wider mb-3" style={{ color: ACCENT_LOCAL }}>
          {t("sections.materialPricing.searchTitle")}
        </h3>
        <div className="flex gap-2">
          <input type="text" value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={handleKeyDown} className={`${inputClass} flex-1`} placeholder={t("sections.materialPricing.searchPlaceholder")} />
          <Button variant="primary" onClick={handleSearch} disabled={loading}>
            {loading ? t("sections.materialPricing.searching") : t("sections.materialPricing.search")}
          </Button>
        </div>
      </Surface>

      {error && (
        <Surface variant="soft" padding="md">
          <Chip variant="danger">{error}</Chip>
        </Surface>
      )}

      {result && (
        <Surface variant="base" padding="lg">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold uppercase tracking-wider" style={{ color: ACCENT_LOCAL }}>{t("sections.materialPricing.results")}</h3>
            <span className="text-xs font-medium" style={{ color: "#A1A1AA" }}>
              {t("sections.materialPricing.matchCount", {
                count: result.n_matches,
                query: result.query,
                ...(getModuleLocale() === "en"
                  ? { plural: result.n_matches !== 1 ? "es" : "" }
                  : {}),
              })}
            </span>
          </div>

          {result.n_matches === 0 ? (
            <p className="text-sm" style={{ color: "#71717A" }}>{t("sections.materialPricing.emptyState")}</p>
          ) : (
            <div className="max-h-[420px] overflow-y-auto">
              <DataTable>
                <thead>
                  <tr>
                    <th className="text-left">{t("sections.materialPricing.table.code")}</th>
                    <th className="text-left">{t("sections.materialPricing.table.materialName")}</th>
                    <th className="text-right tabular-nums">{t("sections.materialPricing.table.gazettePrice")}</th>
                    <th className="text-left">{t("sections.materialPricing.table.source")}</th>
                    <th className="text-left">{t("sections.materialPricing.table.description")}</th>
                  </tr>
                </thead>
                <tbody>
                  {result.materials.map((m, i) => (
                    <tr key={i}>
                      <td className="text-left text-xs font-mono" style={{ color: ACCENT_LOCAL }}>{m.material_code}</td>
                      <td className="text-left text-sm" style={{ color: "#1A1A1A" }}>{m.material_name}</td>
                      <td className="text-right text-sm font-semibold tabular-nums" style={{ color: "#1A1A1A" }}>{fmtTRY2(m.price_try)}</td>
                      <td className="text-left text-xs" style={{ color: "#A1A1AA" }}>{m.source}</td>
                      <td className="text-left text-xs" style={{ color: "#71717A" }}>{m.description}</td>
                    </tr>
                  ))}
                </tbody>
              </DataTable>
            </div>
          )}
        </Surface>
      )}
    </div>
  );
}
