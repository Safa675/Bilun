"use client";

import { useEffect, useState, startTransition } from "react";
import { getMaterialsBySpecialty } from "@/lib/api/sut";
import { SutReferenceSectionSkeleton } from "@/components/skeletons/SutSkeletons";
import type { MaterialEntry } from "@/lib/domains/sut";
import { fmtNum, fmtTRY } from "../shared";
import { DataTable, Surface } from "@/components/primitives";
import { useT } from "@/lib/i18n/useTranslations";

export function SpecialtyMaterialSection() {
  const t = useT();
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
        setError(err instanceof Error ? err.message : t("sections.specialtyMaterial.errors.loadFailed"));
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => { controller.abort(); };
  }, [selected, reloadKey, t]);

  return (
    <Surface variant="base" padding="md">
      <h4 className="text-sm font-bold mb-3" style={{ color: "#1A1A1A" }}>
        {t("sections.specialtyMaterial.title", { total: fmtNum(total) })}
      </h4>
      <select
        value={selected}
        onChange={e => setSelected(e.target.value)}
        className="sut-input"
        style={{ marginBottom: 10, minWidth: 250 }}
      >
        <option value="">{t("sections.specialtyMaterial.allSpecialties")}</option>
        {specialties.map(s => <option key={s.label} value={s.label}>{s.label} — {s.name}</option>)}
      </select>
      {loading ? (
        <SutReferenceSectionSkeleton title={t("sections.specialtyMaterial.loadingTitle")} />
      ) : error ? (
        <div className="space-y-3">
          <p className="text-sm" style={{ color: "#B91C1C" }}>{error}</p>
          <button
            type="button"
            className="sut-section-btn sut-section-btn-active"
            style={{ padding: "6px 14px" }}
            onClick={() => setReloadKey((v) => v + 1)}
          >
            <span className="text-xs font-semibold">{t("sections.specialtyMaterial.retry")}</span>
          </button>
        </div>
      ) : materials.length > 0 ? (
        <div style={{ maxHeight: 400, overflowY: "auto" }}>
          <DataTable className="text-[11px]">
            <thead>
              <tr>
                <th>{t("sections.specialtyMaterial.table.code")}</th>
                <th>{t("sections.specialtyMaterial.table.name")}</th>
                <th>{t("sections.specialtyMaterial.table.priceTl")}</th>
                <th>{t("sections.specialtyMaterial.table.source")}</th>
              </tr>
            </thead>
            <tbody>
              {materials.map((m, i) => (
                <tr key={i}>
                  <td style={{ fontFamily: "monospace", fontSize: 10 }}>{m.sut_code}</td>
                  <td style={{ maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{m.material_name}</td>
                  <td className="tabular-nums text-right">{fmtTRY(m.price_try)}</td>
                  <td style={{ fontSize: 10 }}>{m.source}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        </div>
      ) : (
        <p className="text-sm text-[var(--text-secondary)]">{t("sections.specialtyMaterial.emptyState")}</p>
      )}
    </Surface>
  );
}
