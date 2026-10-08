"use client";

import { useState, useEffect } from "react";
import PatientTabLink from "@/components/shell/PatientTabLink";
import { ArrowRight } from "lucide-react";
import { fmtNum } from "../../shared";
import { Surface, Stat, Chip, Button, buttonActiveClass, DataTable } from "@/components/primitives";
import { buildSutBillingHref } from "@/lib/constants";
import { getPatientAlerts } from "@/lib/api/sut";
import type { PatientAlertsResponse, PatientAlertsStatus } from "@/lib/domains/sut";
import { SutAlertTableSkeleton } from "@/components/skeletons/SutSkeletons";
import { cn } from "@/lib/cn";
import { useT } from "@/lib/i18n/useTranslations";

export interface CopayRateComplianceProps {
  cohortPatientIds: Set<string>;
  cohortFilterActive: boolean;
}

const PATIENT_LINK_CLASS =
  "font-semibold text-[var(--text-primary)] hover:text-[var(--gold-hover)]";

function isFlagged(row: PatientAlertsResponse["patients"][number]): boolean {
  const exposure = row.copay_rate_exposure;
  if (!exposure) return false;
  if (exposure.action) return true;
  return (exposure.n_violations ?? 0) > 0;
}

export function CopayRateCompliance({
  cohortPatientIds,
  cohortFilterActive,
}: CopayRateComplianceProps) {
  const t = useT();
  const [status, setStatus] = useState<PatientAlertsStatus>("all");
  const [data, setData] = useState<PatientAlertsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getPatientAlerts({
      category: "copay_rates",
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

  const flaggedCount = (data?.patients ?? []).filter(isFlagged).length;
  const totalCount = data?.patients?.length ?? 0;

  return (
    <div className="space-y-5">
      <Surface variant="base" padding="md">
        <Stat
          label={t("optimizer.modules.copayRate")}
          value={fmtNum(flaggedCount)}
          hint={t("optimizer.modules.flaggedPatientsHint", { count: fmtNum(totalCount) })}
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
          {t("optimizer.filters.status.all")} ({fmtNum(totalCount)})
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="compact"
          onClick={() => setStatus("flagged")}
          className={cn("gap-1.5", status === "flagged" && buttonActiveClass)}
        >
          {t("optimizer.filters.status.flagged")} ({fmtNum(flaggedCount)})
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="compact"
          onClick={() => setStatus("clear")}
          className={cn("gap-1.5", status === "clear" && buttonActiveClass)}
        >
          {t("optimizer.filters.status.clear")} ({fmtNum(totalCount - flaggedCount)})
        </Button>
      </div>

      {loading ? (
        <SutAlertTableSkeleton />
      ) : (
        <DataTable minWidth={900}>
          <thead>
            <tr>
              <th>{t("optimizer.tables.patientId")}</th>
              <th>{t("optimizer.modules.meanRate")}</th>
              <th>{t("optimizer.modules.applicableProcedures")}</th>
              <th>{t("optimizer.modules.topProcedures")}</th>
              <th>{t("optimizer.tables.status")}</th>
              <th className="text-right">{t("optimizer.complianceIndex.inspect")}</th>
            </tr>
          </thead>
          <tbody>
            {filteredPatients.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-8 text-center text-[var(--text-muted)]">
                  {t("optimizer.emptyStates.noPatientsMatchFilter")}
                </td>
              </tr>
            ) : (
              filteredPatients.map((p) => {
                const flagged = isFlagged(p);
                const top = p.copay_rate_exposure?.top_procedures ?? [];
                const meanRate = p.copay_rate_exposure?.mean_rate;
                return (
                  <tr key={p.patient_id}>
                    <td>
                      <PatientTabLink patientId={p.patient_id} href={buildSutBillingHref(p.patient_id)} className={PATIENT_LINK_CLASS}>
                        {p.patient_id}
                      </PatientTabLink>
                    </td>
                    <td className="tabular-nums text-[var(--text-primary)]">
                      {meanRate != null ? `${meanRate}%` : (
                        <span className="text-[var(--text-muted)]">{t("common.unavailable")}</span>
                      )}
                    </td>
                    <td className="text-[var(--text-secondary)]">
                      {p.copay_rate_exposure?.n_applicable != null
                        ? t("optimizer.modules.procedureCount", { count: p.copay_rate_exposure.n_applicable })
                        : "—"}
                    </td>
                    <td className="text-[var(--text-secondary)]">
                      {top.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {top.map((proc, i) => (
                            <Chip key={`${proc.code}-${i}`} variant="neutral">
                              {proc.code}
                              {proc.rate_pct != null ? ` (${proc.rate_pct}%)` : ""}
                            </Chip>
                          ))}
                        </div>
                      ) : (
                        <span className="text-[var(--text-muted)]">—</span>
                      )}
                    </td>
                    <td>
                      {flagged ? (
                        <Chip variant="warning">{t("optimizer.modules.rateDifference")}</Chip>
                      ) : (
                        <Chip variant="success">{t("optimizer.modules.compliant")}</Chip>
                      )}
                    </td>
                    <td className="text-right">
                      <PatientTabLink
                        patientId={p.patient_id}
                        href={buildSutBillingHref(p.patient_id, { section: "billing-copay" })}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--gold)] hover:text-[var(--gold-hover)]"
                      >
                        {t("optimizer.complianceIndex.openBill")} <ArrowRight className="h-3 w-3" />
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
