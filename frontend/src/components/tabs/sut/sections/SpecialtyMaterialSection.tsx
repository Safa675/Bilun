"use client";

import { useEffect, useState, startTransition } from "react";
import { getMaterialsBySpecialty } from "@/lib/api/sut";
import { SutReferenceSectionSkeleton } from "@/components/skeletons/SutSkeletons";
import type { MaterialEntry } from "@/lib/domains/sut";
import { fmtNum, fmtTRY } from "../shared";

export function SpecialtyMaterialSection() {
  const [specialties, setSpecialties] = useState<{ label: string; name: string }[]>([]);
  const [selected, setSelected] = useState("");
  const [materials, setMaterials] = useState<MaterialEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    startTransition(() => {
      setLoading(true);
      setError(null);
    });

    getMaterialsBySpecialty(selected || undefined, { signal: controller.signal })
      .then((d) => {
        if (controller.signal.aborted) return;
        setSpecialties(d.specialties);
        setMaterials(d.materials);
        setTotal(d.total);
      })
      .catch((err) => {
        if (controller.signal.aborted || (err instanceof DOMException && err.name === "AbortError")) return;
        setError(err instanceof Error ? err.message : "Failed to load specialty materials.");
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => { controller.abort(); };
  }, [selected, reloadKey]);

  return (
    <div className="frost-panel p-4 rounded-2xl">
      <h4 className="text-sm font-bold mb-3" style={{ color: "#1A1A1A" }}>EK-3 Materials by Specialty ({fmtNum(total)} items)</h4>
      <select
        value={selected}
        onChange={e => setSelected(e.target.value)}
        className="sut-input"
        style={{ marginBottom: 10, minWidth: 250 }}
      >
        <option value="">All Specialties</option>
        {specialties.map(s => <option key={s.label} value={s.label}>{s.label} — {s.name}</option>)}
      </select>
      {loading ? (
        <SutReferenceSectionSkeleton title="Loading specialty materials" />
      ) : error ? (
        <div className="space-y-3">
          <p className="text-sm" style={{ color: "#B91C1C" }}>{error}</p>
          <button
            type="button"
            className="sut-section-btn sut-section-btn-active"
            style={{ padding: "6px 14px" }}
            onClick={() => setReloadKey((v) => v + 1)}
          >
            <span className="text-xs font-semibold">Retry</span>
          </button>
        </div>
      ) : materials.length > 0 ? (
        <div style={{ maxHeight: 400, overflowY: "auto" }}>
          <table className="frost-table" style={{ fontSize: 11 }}>
            <thead><tr><th>Code</th><th>Name</th><th>Price (TL)</th><th>Source</th></tr></thead>
            <tbody>
              {materials.map((m, i) => (
                <tr key={i}>
                  <td style={{ fontFamily: "monospace", fontSize: 10 }}>{m.sut_code}</td>
                  <td style={{ maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{m.material_name}</td>
                  <td className="num-col">{fmtTRY(m.price_try)}</td>
                  <td style={{ fontSize: 10 }}>{m.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-sm" style={{ color: "#A1A1AA" }}>No materials found for this specialty.</p>
      )}
    </div>
  );
}
