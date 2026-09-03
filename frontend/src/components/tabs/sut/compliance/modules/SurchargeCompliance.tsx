"use client";

import { useState, useEffect } from "react";
import PatientTabLink from "@/components/shell/PatientTabLink";
import { ArrowRight } from "lucide-react";
import { fmtNum, fmtPctRatio } from "../../shared";
import { Surface, Stat, Chip, Button, buttonActiveClass, DataTable } from "@/components/primitives";
import { buildSutBillingHref } from "@/lib/constants";
import { getPatientAlerts } from "@/lib/api/sut";
import type { PatientAlertsResponse, PatientAlertsStatus } from "@/lib/domains/sut";
import { SutAlertTableSkeleton } from "@/components/skeletons/SutSkeletons";
import { cn } from "@/lib/cn";

export interface SurchargeComplianceProps {
  cohortPatientIds: Set<string>;
  cohortFilterActive: boolean;
}

const PATIENT_LINK_CLASS =
  "font-semibold text-[var(--text-primary)] hover:text-[var(--gold-hover)]";

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

  const filteredPatients = (data?.patients ?? []).filter(
    (p) => !cohortFilterActive || cohortPatientIds.has(p.patient_id),
  );

  const flaggedCount = (data?.patients ?? []).filter(
    (p) => (p.surcharge_exposure?.exposure_rate ?? 0) > 0,
  ).length;
  const totalCount = data?.patients?.length ?? 0;

  return (
    <div className="space-y-5">
      <Surface variant="base" padding="md">
        <Stat
          label="İlave ücret maruziyet riski"
          value={fmtNum(flaggedCount)}
          hint={`Riskli hasta (toplam ${fmtNum(totalCount)})`}
        />
      </Surface>

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
          Riskli / işaretli ({fmtNum(flaggedCount)})
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

      {loading ? (
        <SutAlertTableSkeleton />
      ) : (
        <DataTable minWidth={900}>
          <thead>
            <tr>
              <th>Hasta ID</th>
              <th>İlave ücret maruziyet oranı</th>
              <th>Uygulanabilir işlemler</th>
              <th>En çok eşleşen kurallar</th>
              <th>Uyumluluk durumu</th>
              <th className="text-right">İncele</th>
            </tr>
          </thead>
          <tbody>
            {filteredPatients.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-8 text-center text-[var(--text-muted)]">
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
                      <PatientTabLink patientId={p.patient_id} href={buildSutBillingHref(p.patient_id)} className={PATIENT_LINK_CLASS}>
                        {p.patient_id}
                      </PatientTabLink>
                    </td>
                    <td className="tabular-nums text-[var(--text-primary)]">
                      {p.surcharge_exposure?.exposure_rate != null ? (
                        fmtPctRatio(p.surcharge_exposure.exposure_rate)
                      ) : (
                        <span className="text-[var(--text-muted)]">Kullanılamıyor</span>
                      )}
                    </td>
                    <td className="text-[var(--text-secondary)]">
                      {p.surcharge_exposure?.n_applicable != null
                        ? `${p.surcharge_exposure.n_applicable} işlem`
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
                        <span className="text-[var(--text-muted)]">Kural ihlali yok</span>
                      )}
                    </td>
                    <td>
                      {isFlagged ? (
                        <Chip variant="warning">İlave ücret riski</Chip>
                      ) : (
                        <Chip variant="success">Uyumlu</Chip>
                      )}
                    </td>
                    <td className="text-right">
                      <PatientTabLink
                        patientId={p.patient_id}
                        href={buildSutBillingHref(p.patient_id)}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--gold)] hover:text-[var(--gold-hover)]"
                      >
                        Faturaya git <ArrowRight className="h-3 w-3" />
                      </PatientTabLink>
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
