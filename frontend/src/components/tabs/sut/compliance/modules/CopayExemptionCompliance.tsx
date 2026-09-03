"use client";

import { useState, useEffect } from "react";
import PatientTabLink from "@/components/shell/PatientTabLink";
import { ArrowRight } from "lucide-react";
import { Surface, Stat, Chip, Button, buttonActiveClass, DataTable } from "@/components/primitives";
import { buildSutBillingHref } from "@/lib/constants";
import { getPatientAlerts } from "@/lib/api/sut";
import type { PatientAlertsResponse, PatientAlertsStatus } from "@/lib/domains/sut";
import { fmtNum } from "../../shared";
import { SutAlertTableSkeleton } from "@/components/skeletons/SutSkeletons";
import { cn } from "@/lib/cn";

export interface CopayExemptionComplianceProps {
  cohortPatientIds: Set<string>;
  cohortFilterActive: boolean;
}

const PATIENT_LINK_CLASS =
  "font-semibold text-[var(--text-primary)] hover:text-[var(--gold-hover)]";

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

  const filteredPatients = (data?.patients ?? []).filter(
    (p) => !cohortFilterActive || cohortPatientIds.has(p.patient_id),
  );

  const exemptCount = (data?.patients ?? []).filter((p) => p.copay_exemption?.exempt).length;
  const totalCount = data?.patients?.length ?? 0;

  return (
    <div className="space-y-5">
      <Surface variant="base" padding="md">
        <Stat
          label="Muafiyet uygunluğu"
          value={fmtNum(exemptCount)}
          hint={`Toplam ${fmtNum(totalCount)} hastadan`}
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
          onClick={() => setStatus("exempt")}
          className={cn("gap-1.5", status === "exempt" && buttonActiveClass)}
        >
          Muaf olanlar ({fmtNum(exemptCount)})
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="compact"
          onClick={() => setStatus("not_exempt")}
          className={cn("gap-1.5", status === "not_exempt" && buttonActiveClass)}
        >
          Muaf olmayanlar ({fmtNum(totalCount - exemptCount)})
        </Button>
      </div>

      {loading ? (
        <SutAlertTableSkeleton />
      ) : (
        <DataTable minWidth={900}>
          <thead>
            <tr>
              <th>Hasta ID</th>
              <th>Tanı sayısı & ICD bölümleri</th>
              <th>Muafiyet durumu</th>
              <th>Eşleşen tanılar (EK-1A / acil)</th>
              <th>Önerilen aksiyon</th>
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
                const isExempt = p.copay_exemption?.exempt;
                const qualifyingDx = p.copay_exemption?.qualifying_diagnoses ?? [];
                return (
                  <tr key={p.patient_id}>
                    <td>
                      <PatientTabLink patientId={p.patient_id} href={buildSutBillingHref(p.patient_id)} className={PATIENT_LINK_CLASS}>
                        {p.patient_id}
                      </PatientTabLink>
                    </td>
                    <td className="text-[var(--text-secondary)]">
                      {p.n_diagnoses} tanı · {p.icd10_chapters?.join(", ") || "—"}
                    </td>
                    <td>
                      {isExempt ? (
                        <Chip variant="success">Muaf (EK-1A)</Chip>
                      ) : (
                        <Chip variant="neutral">Standart katılım</Chip>
                      )}
                    </td>
                    <td className="text-[var(--text-secondary)]">
                      {qualifyingDx.length > 0 ? (
                        <span className="font-medium text-[var(--text-primary)]">
                          {qualifyingDx.map((q) => `${q.icd10} (${q.disease})`).join(", ")}
                        </span>
                      ) : (
                        <span className="text-[var(--text-muted)]">—</span>
                      )}
                    </td>
                    <td className="text-[var(--text-secondary)]">
                      {isExempt
                        ? "Fatura öncesi muafiyet bayrağı uygulayın"
                        : "Standart katılım payı tahsilatı"}
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
