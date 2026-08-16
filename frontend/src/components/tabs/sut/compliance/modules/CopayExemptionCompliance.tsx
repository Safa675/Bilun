"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Surface, Eyebrow, Stat, Chip, Button, buttonActiveClass, DataTable } from "@/components/primitives";
import { buildSutBillingHref } from "@/lib/constants";
import { getPatientAlerts } from "@/lib/api/sut";
import type { PatientAlertsResponse, PatientAlertsStatus } from "@/lib/domains/sut";
import { fmtNum } from "../../shared";
import { SutAlertTableSkeleton } from "@/components/skeletons/SutSkeletons";
import { ArrowRight } from "lucide-react";
import { cn } from "@/lib/cn";

export interface CopayExemptionComplianceProps {
  cohortPatientIds: Set<string>;
  cohortFilterActive: boolean;
}

export function CopayExemptionCompliance({
  cohortPatientIds,
  cohortFilterActive,
}: CopayExemptionComplianceProps) {
  const [data, setData] = useState<PatientAlertsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<PatientAlertsStatus>("all");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getPatientAlerts({
      category: "exemptions",
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

  const exemptCount = (data?.patients ?? []).filter((p) => p.copay_exemption?.exempt).length;
  const totalCount = data?.patients?.length ?? 0;

  return (
    <div className="space-y-5">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Surface variant="base" padding="md" className="space-y-1">
          <Stat
            label="Muafiyet Uygunluğu"
            value={fmtNum(exemptCount)}
            hint={`Toplam ${fmtNum(totalCount)} hastadan`}
          />
        </Surface>
        <Surface variant="base" padding="md" className="space-y-1">
          <Eyebrow>SUT Mevzuat Dayanağı</Eyebrow>
          <div className="flex items-center gap-2 pt-1">
            <Chip variant="neutral">SUT §1.8.5</Chip>
            <Chip variant="success">EK-1A Listesi</Chip>
            <Chip variant="neutral">Acil Muafiyet</Chip>
          </div>
          <p className="pt-2 text-xs text-[var(--text-tertiary)]">
            Kanser, kronik neoplazmlar ve acil haller katılım payından %100 muaftır.
          </p>
        </Surface>
        <Surface variant="base" padding="md" className="space-y-1">
          <Eyebrow>MEDULA Otomasyon Durumu</Eyebrow>
          <div className="flex items-center gap-2 pt-1">
            <span className="inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            <span className="text-sm font-medium text-[var(--text-primary)]">
              katilimPayindanMuaf=E
            </span>
          </div>
          <p className="text-xs text-[var(--text-secondary)]">
            Uygun tanılı hastalarda MEDULA muafiyet bayrağı teyit edilmelidir.
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
          onClick={() => setStatus("exempt")}
          className={cn("gap-1.5", status === "exempt" && buttonActiveClass)}
        >
          Muaf Olanlar ({fmtNum(exemptCount)})
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="compact"
          onClick={() => setStatus("not_exempt")}
          className={cn("gap-1.5", status === "not_exempt" && buttonActiveClass)}
        >
          Muaf Olmayanlar ({fmtNum(totalCount - exemptCount)})
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
              <th>Tanı Sayısı & ICD Bölümleri</th>
              <th>Muafiyet Durumu</th>
              <th>Eşleşen Tanılar (EK-1A / Acil)</th>
              <th>Önerilen Aksiyon</th>
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
                const isExempt = p.copay_exemption?.exempt;
                const qualifyingDx = p.copay_exemption?.qualifying_diagnoses ?? [];
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
                    <td className="text-[var(--text-secondary)]">
                      {p.n_diagnoses} Tanı · {p.icd10_chapters?.join(", ") || "—"}
                    </td>
                    <td>
                      {isExempt ? (
                        <Chip variant="success">Muaf (EK-1A)</Chip>
                      ) : (
                        <Chip variant="neutral">Standart Katılım</Chip>
                      )}
                    </td>
                    <td className="text-[var(--text-secondary)]">
                      {qualifyingDx.length > 0 ? (
                        <span className="font-medium text-[var(--text-primary)]">
                          {qualifyingDx.map((q) => `${q.icd10} (${q.disease})`).join(", ")}
                        </span>
                      ) : (
                        <span className="text-[var(--text-tertiary)]">—</span>
                      )}
                    </td>
                    <td className="text-[var(--text-secondary)]">
                      {isExempt ? (
                        <span className="text-emerald-600 font-medium">
                          Fatura öncesi muafiyet bayrağı uygulayın
                        </span>
                      ) : (
                        "Standart katılım payı tahsilatı"
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
