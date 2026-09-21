"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  COMPLIANCE_SUB_IDS,
  type ComplianceSubSection,
} from "@/lib/workspaceSubtabs";
import { ComplianceSubtabStrip } from "./ComplianceSubtabStrip";
import { CopayExemptionCompliance } from "./modules/CopayExemptionCompliance";
import { SurchargeCompliance } from "./modules/SurchargeCompliance";
import { CopayRateCompliance } from "./modules/CopayRateCompliance";
import { ComplianceFindingTable } from "./modules/ComplianceFindingTable";
import { getComplianceIndex, getMedulaRejectionQueue, getPatientAlerts } from "@/lib/api/sut";
import type { ComplianceIndexResponse, ComplianceIndexSurface } from "@/lib/domains/sut";
import { buildSutHomeHref } from "@/lib/constants";
import { Surface, Stat } from "@/components/primitives";
import { fmtNum, fmtTRY2 } from "../shared";
import { useT } from "@/lib/i18n/useTranslations";

const INDEX_SURFACES: readonly ComplianceIndexSurface[] = [
  "materials",
  "drug_indication",
  "lab",
  "payment_methods",
  "claim_compliance",
];
export const COMPLIANCE_INDEX_PAGE_SIZE = 100;

export interface SUTComplianceDashboardProps {
  cohortPatientIds: Set<string>;
  cohortFilterActive: boolean;
}

export function selectCurrentComplianceIndex(
  index: ComplianceIndexResponse | null,
  resultKey: string,
  requestKey: string,
) {
  return resultKey === requestKey ? index : null;
}

function isIndexSurface(subtab: ComplianceSubSection): subtab is ComplianceIndexSurface {
  return (INDEX_SURFACES as readonly string[]).includes(subtab);
}

export function complianceIndexQuery(
  surface: ComplianceIndexSurface | undefined,
  patientIds: readonly string[],
  offset = 0,
) {
  return {
    ...(surface ? { surface } : {}),
    ...(patientIds.length > 0 ? { patientId: [...patientIds] } : {}),
    limit: surface ? COMPLIANCE_INDEX_PAGE_SIZE : 1,
    offset,
  };
}

export function ComplianceIndexGroup({
  index,
  surface,
  loading,
  cohortPatientIds,
  cohortFilterActive,
  onPageChange,
}: SUTComplianceDashboardProps & {
  index: ComplianceIndexResponse | null;
  surface: ComplianceIndexSurface;
  loading: boolean;
  onPageChange?: (offset: number) => void;
}) {
  const inCohort = (row: { patient_id: string }) =>
    !cohortFilterActive || cohortPatientIds.has(row.patient_id);
  return (
    <ComplianceFindingTable
      rows={(index?.rows ?? []).filter((row) => row.surface === surface && inCohort(row))}
      loading={loading}
      unavailable={index?.artifacts_available !== true ||
        (surface === "claim_compliance" && !index?.claim_compliance)}
      claimCompliance={surface === "claim_compliance"}
      partialResults={index?.pagination?.has_more === true}
      claimComplianceSummary={surface === "claim_compliance"
        ? index?.claim_compliance
        : undefined}
      pagination={index?.pagination}
      onPageChange={onPageChange}
    />
  );
}

export function SUTComplianceDashboard({
  cohortPatientIds,
  cohortFilterActive,
}: SUTComplianceDashboardProps) {
  const t = useT();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const rawSubtab = (searchParams?.get("compTab") || searchParams?.get("subtab")) as
    | ComplianceSubSection
    | null;
  const activeSubtab: ComplianceSubSection =
    rawSubtab && (COMPLIANCE_SUB_IDS as readonly string[]).includes(rawSubtab)
      ? rawSubtab
      : "exemptions";

  const cohortIds = useMemo(
    () => cohortFilterActive ? [...cohortPatientIds].sort() : [],
    [cohortFilterActive, cohortPatientIds],
  );
  const cohortKey = cohortFilterActive ? cohortIds.join("\u0000") : "*";
  const aggregateRequestKey = `aggregate|${cohortKey}`;
  const [index, setIndex] = useState<ComplianceIndexResponse | null>(null);
  const [indexLoading, setIndexLoading] = useState(true);
  const [indexResultKey, setIndexResultKey] = useState(aggregateRequestKey);
  const [surfaceResult, setSurfaceResult] = useState<{
    key: string;
    index: ComplianceIndexResponse | null;
  }>({ key: "", index: null });
  const [pageCursor, setPageCursor] = useState({ key: "", offset: 0 });
  const [medulaTotal, setMedulaTotal] = useState<number | null>(null);
  const [alertBadges, setAlertBadges] = useState<
    Partial<Record<"exemptions" | "surcharge" | "copay_rates", number>>
  >({});

  const currentIndex = selectCurrentComplianceIndex(index, indexResultKey, aggregateRequestKey);
  const currentIndexLoading = indexLoading || indexResultKey !== aggregateRequestKey;
  const surfaceKey = isIndexSurface(activeSubtab)
    ? `${activeSubtab}|${cohortKey}`
    : `none|${cohortKey}`;
  const surfaceOffset = pageCursor.key === surfaceKey ? pageCursor.offset : 0;
  const surfaceRequestKey = `${surfaceKey}|${surfaceOffset}`;
  const emptyFilteredSurface =
    isIndexSurface(activeSubtab) && cohortFilterActive && cohortIds.length === 0;
  const emptySurfaceIndex = useMemo<ComplianceIndexResponse | null>(() => {
    if (!emptyFilteredSurface || !isIndexSurface(activeSubtab)) return null;
    return {
      artifacts_available: currentIndex?.artifacts_available === true,
      n_patients: 0,
      n_findings: 0,
      n_patients_with_findings: 0,
      billed_at_risk_try: activeSubtab === "claim_compliance" || activeSubtab === "drug_indication" ? null : 0,
      by_surface: {},
      rows: [],
      pagination: {
        total_matching: 0,
        limit: COMPLIANCE_INDEX_PAGE_SIZE,
        offset: 0,
        has_more: false,
      },
      claim_compliance: activeSubtab === "claim_compliance" && currentIndex?.claim_compliance
        ? {
            counts: { evaluated: 0, missing_inputs: 0, unavailable: 0 },
            non_evaluated_total: 0,
            details: [],
            details_truncated: false,
          }
        : activeSubtab === "claim_compliance" ? null : undefined,
    };
  }, [activeSubtab, currentIndex?.artifacts_available, currentIndex?.claim_compliance, emptyFilteredSurface]);
  const surfaceIndex = emptyFilteredSurface
    ? emptySurfaceIndex
    : surfaceResult.key === surfaceRequestKey ? surfaceResult.index : null;
  const surfaceLoading =
    isIndexSurface(activeSubtab) &&
    !emptyFilteredSurface &&
    surfaceResult.key !== surfaceRequestKey;

  useEffect(() => {
    let cancelled = false;
    getComplianceIndex(complianceIndexQuery(undefined, cohortIds))
      .then((res) => {
        if (!cancelled) {
          if (cohortFilterActive && cohortIds.length === 0 && res.artifacts_available) {
            setIndex({
              ...res,
              n_patients: 0,
              n_findings: 0,
              n_patients_with_findings: 0,
              billed_at_risk_try: 0,
              by_surface: Object.fromEntries(INDEX_SURFACES.map((surface) => [
                surface,
                {
                  n: 0,
                  billed_try: surface === "claim_compliance" || surface === "drug_indication" ? null : 0,
                  n_patients: 0,
                },
              ])),
              rows: [],
            });
          } else {
            setIndex(res);
          }
          setIndexResultKey(aggregateRequestKey);
          setIndexLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setIndex(null);
          setIndexResultKey(aggregateRequestKey);
          setIndexLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [aggregateRequestKey, cohortFilterActive, cohortIds]);

  useEffect(() => {
    if (!isIndexSurface(activeSubtab) || emptyFilteredSurface) return;
    let cancelled = false;
    getComplianceIndex(complianceIndexQuery(activeSubtab, cohortIds, surfaceOffset))
      .then((res) => {
        if (!cancelled) {
          setSurfaceResult({ key: surfaceRequestKey, index: res });
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSurfaceResult({ key: surfaceRequestKey, index: null });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [activeSubtab, cohortIds, emptyFilteredSurface, surfaceOffset, surfaceRequestKey]);

  useEffect(() => {
    let cancelled = false;
    getMedulaRejectionQueue({ page: 1, page_size: 1 })
      .then((res) => {
        if (!cancelled) setMedulaTotal(res.total);
      })
      .catch(() => {
        if (!cancelled) setMedulaTotal(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      getPatientAlerts({ category: "exemptions", status: "all", limit: 100, offset: 0 }),
      getPatientAlerts({ category: "surcharge", status: "flagged", limit: 100, offset: 0 }),
      getPatientAlerts({ category: "copay_rates", status: "flagged", limit: 100, offset: 0 }),
    ])
      .then(([exemptions, surcharge, copayRates]) => {
        if (cancelled) return;
        const inCohort = (id: string) => !cohortFilterActive || cohortPatientIds.has(id);
        setAlertBadges({
          exemptions: exemptions.patients.filter(
            (p) => inCohort(p.patient_id) && p.copay_exemption?.exempt,
          ).length,
          surcharge: surcharge.patients.filter((p) => inCohort(p.patient_id)).length,
          copay_rates: copayRates.patients.filter((p) => inCohort(p.patient_id)).length,
        });
      })
      .catch(() => {
        if (!cancelled) setAlertBadges({});
      });
    return () => {
      cancelled = true;
    };
  }, [cohortFilterActive, cohortPatientIds]);

  const indexAvailable = currentIndex?.artifacts_available === true;
  const headerFindings = indexAvailable
    ? currentIndex?.n_findings ?? 0
    : null;
  const headerPatients = indexAvailable
    ? currentIndex?.n_patients_with_findings ?? 0
    : null;
  const headerBilled = indexAvailable
    ? isIndexSurface(activeSubtab)
      ? currentIndex?.by_surface?.[activeSubtab]?.billed_try ?? null
      : currentIndex?.billed_at_risk_try ?? null
    : null;

  const badgeCounts = useMemo(() => {
    const counts: Partial<Record<ComplianceSubSection, number>> = { ...alertBadges };
    if (indexAvailable) {
      for (const surface of INDEX_SURFACES) {
        if (surface === "claim_compliance" && !currentIndex?.claim_compliance) continue;
        counts[surface] = currentIndex?.by_surface?.[surface]?.n ?? 0;
      }
    }
    return counts;
  }, [alertBadges, currentIndex?.by_surface, currentIndex?.claim_compliance, indexAvailable]);

  const handleSelectSubtab = (subtab: ComplianceSubSection) => {
    if (!pathname) return;
    const params = new URLSearchParams(searchParams?.toString() ?? "");
    params.set("compTab", subtab);
    params.set("subtab", subtab);
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  };

  const dash = t("optimizer.emDash");

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Surface variant="base" padding="md">
          <Stat
            label={t("optimizer.complianceIndex.findings")}
            value={headerFindings == null ? dash : fmtNum(headerFindings)}
          />
        </Surface>
        <Surface variant="base" padding="md">
          <Stat
            label={t("optimizer.complianceIndex.patientsWithFindings")}
            value={headerPatients == null ? dash : fmtNum(headerPatients)}
          />
        </Surface>
        <Surface variant="base" padding="md">
          <Stat
            label={t("optimizer.complianceIndex.billedAtRisk")}
            value={headerBilled == null ? dash : fmtTRY2(headerBilled)}
          />
        </Surface>
        <Surface variant="base" padding="md">
          <Link href={buildSutHomeHref("operations", searchParams)} className="block">
            <Stat
              label={t("optimizer.complianceIndex.medulaRejections")}
              value={medulaTotal == null ? dash : fmtNum(medulaTotal)}
              hint={t("optimizer.complianceIndex.medulaHint")}
            />
          </Link>
        </Surface>
      </div>

      <ComplianceSubtabStrip
        activeSubtab={activeSubtab}
        onSelectSubtab={handleSelectSubtab}
        badgeCounts={badgeCounts}
      />

      {activeSubtab === "surcharge" ? (
        <SurchargeCompliance
          cohortPatientIds={cohortPatientIds}
          cohortFilterActive={cohortFilterActive}
        />
      ) : activeSubtab === "copay_rates" ? (
        <CopayRateCompliance
          cohortPatientIds={cohortPatientIds}
          cohortFilterActive={cohortFilterActive}
        />
      ) : isIndexSurface(activeSubtab) ? (
        <ComplianceIndexGroup
          index={surfaceIndex}
          surface={activeSubtab}
          loading={surfaceLoading || currentIndexLoading}
          cohortPatientIds={cohortPatientIds}
          cohortFilterActive={cohortFilterActive}
          onPageChange={(offset) => setPageCursor({ key: surfaceKey, offset })}
        />
      ) : (
        <CopayExemptionCompliance
          cohortPatientIds={cohortPatientIds}
          cohortFilterActive={cohortFilterActive}
        />
      )}
    </div>
  );
}
