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
import {
  formatExemptionCategory,
  getCopayExemptionState,
  getPrimaryExemptionGround,
} from "@/lib/copayExemption";
import { getSutAlertBadgeLabel } from "@/lib/sutLabels";
import { useT } from "@/lib/i18n/useTranslations";

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
  const t = useT();
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
          label={t("optimizer.modules.exemptionEligibility")}
          value={fmtNum(exemptCount)}
          hint={t("optimizer.modules.totalPatientsHint", { count: fmtNum(totalCount) })}
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
          onClick={() => setStatus("exempt")}
          className={cn("gap-1.5", status === "exempt" && buttonActiveClass)}
        >
          {t("optimizer.filters.status.exempt")} ({fmtNum(exemptCount)})
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="compact"
          onClick={() => setStatus("not_exempt")}
          className={cn("gap-1.5", status === "not_exempt" && buttonActiveClass)}
        >
          {t("optimizer.filters.status.not_exempt")} ({fmtNum(totalCount - exemptCount)})
        </Button>
      </div>

      {loading ? (
        <SutAlertTableSkeleton />
      ) : (
        <DataTable minWidth={900}>
          <thead>
            <tr>
              <th>{t("optimizer.tables.patientId")}</th>
              <th>{t("optimizer.modules.diagnosisChapters")}</th>
              <th>{t("optimizer.modules.exemptionStatus")}</th>
              <th>
                {t("optimizer.modules.matchedDiagnoses")}
                <span className="block text-[var(--text-muted)]">{t("optimizer.modules.sourceTextTr")}</span>
              </th>
              <th>{t("optimizer.tables.recommendedAction")}</th>
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
                const copayState = p.copay_exemption ? getCopayExemptionState(p.copay_exemption) : "none";
                const primaryGround = p.copay_exemption ? getPrimaryExemptionGround(p.copay_exemption) : null;
                const qualifyingDx = p.copay_exemption?.qualifying_diagnoses ?? [];
                return (
                  <tr key={p.patient_id}>
                    <td>
                      <PatientTabLink patientId={p.patient_id} href={buildSutBillingHref(p.patient_id)} className={PATIENT_LINK_CLASS}>
                        {p.patient_id}
                      </PatientTabLink>
                    </td>
                    <td className="text-[var(--text-secondary)]">
                      {t("optimizer.modules.diagnosisCount", { count: p.n_diagnoses })} · {p.icd10_chapters?.join(", ") || "—"}
                    </td>
                    <td>
                      {copayState === "exempt" ? (
                        <Chip variant="success">
                          {!primaryGround || primaryGround === "ek1a_chronic"
                            ? t("optimizer.modules.exemptEk1a")
                            : t("optimizer.modules.exemptOnGround", {
                                basis: formatExemptionCategory(primaryGround, t),
                              })}
                        </Chip>
                      ) : copayState === "partial" ? (
                        <Chip variant="warning">{getSutAlertBadgeLabel("ek1aReportMissing")}</Chip>
                      ) : (
                        <Chip variant="neutral">{t("optimizer.modules.standardCopay")}</Chip>
                      )}
                    </td>
                    <td className="text-[var(--text-secondary)]">
                      {qualifyingDx.length > 0 ? (
                        <span lang="tr" className="font-medium text-[var(--text-primary)]">
                          {qualifyingDx.map((q) => `${q.icd10} (${q.disease})`).join(", ")}
                        </span>
                      ) : (
                        <span className="text-[var(--text-muted)]">—</span>
                      )}
                    </td>
                    <td className="text-[var(--text-secondary)]">
                      {copayState === "exempt"
                        ? t("optimizer.modules.applyExemption")
                        : copayState === "partial"
                          ? t("optimizer.modules.checkChronicReport")
                          : t("optimizer.modules.collectStandardCopay")}
                    </td>
                    <td className="text-right">
                      <PatientTabLink
                        patientId={p.patient_id}
                        href={buildSutBillingHref(p.patient_id)}
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
