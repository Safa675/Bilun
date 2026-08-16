"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  COMPLIANCE_SUB_IDS,
  type ComplianceSubSection,
} from "@/lib/workspaceSubtabs";
import { ComplianceSubtabStrip } from "./ComplianceSubtabStrip";
import { CopayExemptionCompliance } from "./modules/CopayExemptionCompliance";
import { SurchargeCompliance } from "./modules/SurchargeCompliance";

export interface SUTComplianceDashboardProps {
  cohortPatientIds: Set<string>;
  cohortFilterActive: boolean;
}

export function SUTComplianceDashboard({
  cohortPatientIds,
  cohortFilterActive,
}: SUTComplianceDashboardProps) {
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

  const handleSelectSubtab = (subtab: ComplianceSubSection) => {
    if (!pathname) return;
    const params = new URLSearchParams(searchParams?.toString() ?? "");
    params.set("compTab", subtab);
    params.set("subtab", subtab);
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  };

  return (
    <div className="space-y-6">
      <ComplianceSubtabStrip
        activeSubtab={activeSubtab}
        onSelectSubtab={handleSelectSubtab}
      />

      {activeSubtab === "surcharge" ? (
        <SurchargeCompliance
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
