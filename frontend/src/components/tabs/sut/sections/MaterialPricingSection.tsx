"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getSutMaterialPricing } from "@/lib/api/sut";
import type { SutMaterialPricingResult } from "@/lib/api/sut";
import { ACCENT_LOCAL, fmtTRY2 } from "../shared";

export function MaterialPricingSection() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SutMaterialPricingResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const handleSearch = useCallback(async () => {
    const q = query.trim();
    if (!q) { setError("Enter a material code or name to search."); return; }

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
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      if (abortRef.current === controller) { setLoading(false); abortRef.current = null; }
    }
  }, [query]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSearch();
  }, [handleSearch]);

  useEffect(() => {
    return () => { abortRef.current?.abort(); };
  }, []);

  return (
    <div className="space-y-5">
      <div className="frost-panel p-5 rounded-2xl">
        <h3 className="text-sm font-semibold uppercase tracking-wider mb-3" style={{ color: ACCENT_LOCAL }}>
          Search Gazette Prices (4,407+ Materials)
        </h3>
        <div className="flex gap-2">
          <input type="text" value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={handleKeyDown} className="sut-input flex-1" placeholder="e.g. stent, protez, pacemaker, 090301" />
          <button type="button" onClick={handleSearch} disabled={loading} className="sut-btn-primary">
            {loading ? "Searching..." : "Search"}
          </button>
        </div>
      </div>

      {error && (
        <div className="frost-panel p-4 rounded-2xl" style={{ borderColor: "rgba(185, 28, 28, 0.3)", background: "rgba(185, 28, 28, 0.04)" }}>
          <p className="text-sm font-medium" style={{ color: "#B91C1C" }}>{error}</p>
        </div>
      )}

      {result && (
        <div className="frost-panel p-5 rounded-2xl">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold uppercase tracking-wider" style={{ color: ACCENT_LOCAL }}>Results</h3>
            <span className="text-xs font-medium" style={{ color: "#A1A1AA" }}>
              {result.n_matches} match{result.n_matches !== 1 ? "es" : ""} for &ldquo;{result.query}&rdquo;
            </span>
          </div>

          {result.n_matches === 0 ? (
            <p className="text-sm" style={{ color: "#71717A" }}>No gazette entries found. Try a different code or partial name.</p>
          ) : (
            <div className="overflow-x-auto max-h-[420px] overflow-y-auto">
              <table className="frost-table w-full">
                <thead className="sticky top-0">
                  <tr>
                    <th className="text-left">Code</th>
                    <th className="text-left">Material Name</th>
                    <th className="text-right">Gazette Price</th>
                    <th className="text-left">Source</th>
                    <th className="text-left">Description</th>
                  </tr>
                </thead>
                <tbody>
                  {result.materials.map((m, i) => (
                    <tr key={i}>
                      <td className="text-left text-xs font-mono" style={{ color: ACCENT_LOCAL }}>{m.material_code}</td>
                      <td className="text-left text-sm" style={{ color: "#1A1A1A" }}>{m.material_name}</td>
                      <td className="text-right text-sm font-semibold" style={{ color: "#1A1A1A" }}>{fmtTRY2(m.price_try)}</td>
                      <td className="text-left text-xs" style={{ color: "#A1A1AA" }}>{m.source}</td>
                      <td className="text-left text-xs" style={{ color: "#71717A" }}>{m.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
