"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { fmtNum, fmtPctRatio } from "../../shared";
import { Surface, Eyebrow, Stat, Chip, Button, buttonActiveClass, DataTable } from "@/components/primitives";
import { buildSutBillingHref } from "@/lib/constants";
import { getPatientAlerts } from "@/lib/api/sut";
import type { PatientAlertsResponse, PatientAlertsStatus } from "@/lib/domains/sut";
import { SutAlertTableSkeleton } from "@/components/skeletons/SutSkeletons";
import { cn } from "@/lib/cn";

export interface SurchargeComplianceProps {
  cohortPatientIds: Set<string>;
  cohortFilterActive: boolean;
}

export function SurchargeCompliance({
  cohortPatientIds,
  cohortFilterActive,
}: SurchargeComplianceProps) {
  const [status, setStatus] = useState<PatientAlertsStatus>("all");
  const [data, setData] = useState<PatientAlertsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getPatientAlerts({
      category: "surcharge",
      status,
      limit: 100,
      offset: 0,
    })
      .then((res) => {
        if (!cancelled) {
          setData(res);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setData(null);
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [status]);

  const filteredPatients = (data?.patients ?? []).filter((p) =>
    !cohortFilterActive || cohortPatientIds.has(p.patient_id),
  );

  const flaggedCount = (data?.patients ?? []).filter(
    (p) => (p.surcharge_exposure?.exposure_rate ?? 0) > 0,
  ).length;
  const totalCount = data?.patients?.length ?? 0;

  return (
    <div className="space-y-5">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Surface variant="base" padding="md" className="space-y-1">
          <Stat
            label="İlave Ücret Maruziyet Riski"
            value={fmtNum(flaggedCount)}
            hint={`Riskli hasta (Toplam ${fmtNum(totalCount)})`}
          />
        </Surface>
        <Surface variant="base" padding="md" className="space-y-1">
          <Eyebrow>SUT & Kanun Dayanağı</Eyebrow>
          <div className="flex items-center gap-2 pt-1">
            <Chip variant="danger">SUT §1.9</Chip>
            <Chip variant="neutral">5510 md. 73</Chip>
            <Chip variant="neutral">%200 Tavan Sınırı</Chip>
          </div>
          <p className="pt-2 text-xs text-[var(--text-tertiary)]">
            Acil, kanser cerrahisi, yoğun bakım, organ nakli ve ilaçlardan ilave ücret alınamaz.
          </p>
        </Surface>
        <Surface variant="base" padding="md" className="space-y-1">
          <Eyebrow>İlave Ücret Yasağı Kapsamı</Eyebrow>
          <div className="flex items-center gap-2 pt-1">
            <span className="inline-flex h-2 w-2 rounded-full bg-amber-500" />
            <span className="text-sm font-medium text-[var(--text-primary)]">
              İstisnai Sağlık Hizmetleri
            </span>
          </div>
          <p className="text-xs text-[var(--text-secondary)]">
            Tavan aşımı veya yasaklı hizmetlerde fark tahsilatı SGK idari para cezasına tabidir.
          </p>
        </Surface>
      </div>

      {/* Filter Toolbar */}
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant="secondary"
          size="compact"
          onClick={() => setStatus("all")}
          className={cn("gap-1.5", status === "all" && buttonActiveClass)}
        >
          Tümü ({fmtNum(totalCount)})
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="compact"
          onClick={() => setStatus("flagged")}
          className={cn("gap-1.5", status === "flagged" && buttonActiveClass)}
        >
          Riskli / İşaretli ({fmtNum(flaggedCount)})
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="compact"
          onClick={() => setStatus("clear")}
          className={cn("gap-1.5", status === "clear" && buttonActiveClass)}
        >
          Temiz ({fmtNum(totalCount - flaggedCount)})
        </Button>
      </div>

      {/* Patients Table */}
      {loading ? (
        <SutAlertTableSkeleton />
      ) : (
        <DataTable minWidth={900}>
          <thead>
            <tr>
              <th>Hasta ID</th>
              <th>İlave Ücret Maruziyet Oranı</th>
              <th>Uygulanabilir İşlemler</th>
              <th>En Çok Eşleşen Kurallar</th>
              <th>Uyumluluk Durumu</th>
              <th className="text-right">İncele</th>
            </tr>
          </thead>
          <tbody>
            {filteredPatients.length === 0 ? (
              <tr>
                <td colSpan={6} className="text-center py-8 text-[var(--text-tertiary)]">
                  Seçili filtre için hasta kaydı bulunamadı.
                </td>
              </tr>
            ) : (
              filteredPatients.map((p) => {
                const exposureRate = p.surcharge_exposure?.exposure_rate ?? 0;
                const isFlagged = exposureRate > 0;
                const topRules = p.surcharge_exposure?.top_rules ?? [];
                return (
                  <tr key={p.patient_id}>
                    <td>
                      <Link
                        href={buildSutBillingHref(p.patient_id)}
                        className="font-semibold text-slate-950 hover:text-[var(--gold-hover)]"
                      >
                        {p.patient_id}
                      </Link>
                    </td>
                    <td>
                      {p.surcharge_exposure?.exposure_rate != null ? (
                        <span
                          className={
                            isFlagged ? "font-semibold text-amber-500" : "text-emerald-500 font-medium"
                          }
                        >
                          {fmtPctRatio(p.surcharge_exposure.exposure_rate)}
                        </span>
                      ) : (
                        <span className="text-[var(--text-tertiary)]">Kullanılamıyor</span>
                      )}
                    </td>
                    <td className="text-[var(--text-secondary)]">
                      {p.surcharge_exposure?.n_applicable != null
                        ? `${p.surcharge_exposure.n_applicable} İşlem`
                        : "—"}
                    </td>
                    <td className="text-[var(--text-secondary)]">
                      {topRules.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {topRules.map((r, i) => (
                            <Chip key={i} variant="neutral">
                              {typeof r === "string" ? r : `${r.code} (${r.name})`}
                            </Chip>
                          ))}
                        </div>
                      ) : (
                        <span className="text-[var(--text-tertiary)]">Kural ihlali yok</span>
                      )}
                    </td>
                    <td>
                      {isFlagged ? (
                        <Chip variant="warning">İlave Ücret Riski</Chip>
                      ) : (
                        <Chip variant="success">Uyumlu</Chip>
                      )}
                    </td>
                    <td className="text-right">
                      <Link
                        href={buildSutBillingHref(p.patient_id)}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--gold)] hover:text-[var(--gold-hover)]"
                      >
                        Faturaya Git <ArrowRight className="h-3 w-3" />
                      </Link>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </DataTable>
      )}
    </div>
  );
}
