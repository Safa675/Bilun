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

export interface SUTComplianceDashboardProps {
  cohortPatientIds: Set<string>;
  cohortFilterActive: boolean;
}

function isIndexSurface(subtab: ComplianceSubSection): subtab is ComplianceIndexSurface {
  return (INDEX_SURFACES as readonly string[]).includes(subtab);
}

export function ComplianceIndexGroup({
  index,
  surface,
  loading,
  cohortPatientIds,
  cohortFilterActive,
}: SUTComplianceDashboardProps & {
  index: ComplianceIndexResponse | null;
  surface: ComplianceIndexSurface;
  loading: boolean;
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
      evaluations={surface === "claim_compliance"
        ? index?.claim_compliance?.evaluations.filter(inCohort)
        : undefined}
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

  const [index, setIndex] = useState<ComplianceIndexResponse | null>(null);
  const [indexLoading, setIndexLoading] = useState(true);
  const [medulaTotal, setMedulaTotal] = useState<number | null>(null);
  const [alertBadges, setAlertBadges] = useState<
    Partial<Record<"exemptions" | "surcharge" | "copay_rates", number>>
  >({});

  useEffect(() => {
    let cancelled = false;
    getComplianceIndex({ limit: 5000, offset: 0 })
      .then((res) => {
        if (!cancelled) {
          setIndex(res);
          setIndexLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setIndex(null);
          setIndexLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

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

  const filteredIndexRows = useMemo(() => {
    const rows = index?.rows ?? [];
    if (!cohortFilterActive) return rows;
    return rows.filter((row) => cohortPatientIds.has(row.patient_id));
  }, [index, cohortFilterActive, cohortPatientIds]);

  const indexAvailable = index?.artifacts_available === true;
  const headerFindings = indexAvailable
    ? filteredIndexRows.length
    : null;
  const headerPatients = indexAvailable
    ? new Set(filteredIndexRows.map((row) => row.patient_id)).size
    : null;
  const headerBilled = indexAvailable
    ? filteredIndexRows.reduce((sum, row) => sum + (row.billed_try ?? 0), 0)
    : null;

  const badgeCounts = useMemo(() => {
    const counts: Partial<Record<ComplianceSubSection, number>> = { ...alertBadges };
    if (indexAvailable) {
      for (const surface of INDEX_SURFACES) {
        if (surface === "claim_compliance" && !index?.claim_compliance) continue;
        counts[surface] = filteredIndexRows.filter((row) => row.surface === surface).length;
      }
    }
    return counts;
  }, [alertBadges, filteredIndexRows, indexAvailable, index?.claim_compliance]);

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
          index={index}
          surface={activeSubtab}
          loading={indexLoading}
          cohortPatientIds={cohortPatientIds}
          cohortFilterActive={cohortFilterActive}
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
