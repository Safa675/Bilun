"use client";

import { useEffect, useRef, useState } from "react";
import { ClipboardCheck, ShieldAlert, TrendingUp } from "lucide-react";
import Tabs from "@/components/primitives/Tabs";
import { useT } from "@/lib/i18n/useTranslations";
import type { BillingActionReport, RecommendedActionItem } from "@/lib/domains/sut";
import {
  viewActions,
  viewForSection,
  type WorkspaceViewId,
} from "@/lib/workspaceViews";
import { buildUnifiedComplianceFindings } from "@/lib/complianceFindings";
import AuditViewSection from "./AuditViewSection";
import ComplianceViewSection from "./ComplianceViewSection";
import RevenueViewSection from "./RevenueViewSection";

function CountBadge({ count }: { count: number }) {
  return (
    <span className="rounded-full bg-[var(--gold-subtle)] px-2 py-0.5 text-xs font-semibold tabular-nums text-[var(--gold-hover)]">
      {count}
    </span>
  );
}

/**
 * Three-view tab container for the patient workspace.
 *
 * The views are pure presentation groupings driven by the existing
 * `getFindingType` classification (`@/lib/workspaceViews`), which consumes
 * the backend `finding_type` field. Each trigger shows the live finding
 * count for its view.
 *
 * `sectionQuery` (the `?section=` URL parameter set when a recommended action
 * is selected) activates the owning view so the target detail section is
 * mounted before the page-level scroll runs.
 */
export default function PatientWorkspaceViews({
  billingReport,
  patientId,
  selectedActionId,
  onSelectAction,
  onOpenClause,
  sectionQuery,
  selectedFindingId,
}: {
  billingReport: BillingActionReport;
  patientId: string;
  selectedActionId?: string | null;
  onSelectAction?: (action: RecommendedActionItem) => void;
  onOpenClause?: (sectionId: string) => void;
  sectionQuery?: string | null;
  selectedFindingId?: string | null;
}) {
  const t = useT();
  const [activeView, setActiveView] = useState<WorkspaceViewId>("compliance");

  const unifiedComplianceRows = buildUnifiedComplianceFindings(billingReport, t);
  const complianceCount = unifiedComplianceRows.length;
  const revenueCount = viewActions(billingReport, "revenue").length;
  const auditCount = viewActions(billingReport, "audit").length;

  // Follow `?section=` anchors: switch to the owning view, then let the
  // section mount before scrolling to it. Depend on `sectionQuery` ONLY —
  // including `activeView` in the deps would re-apply a stale section
  // parameter whenever the user manually switches tabs, yanking the view
  // back to the section's owner (review finding: manual tab choice must win
  // once the anchor has been applied).
  const handledSectionRef = useRef<string | null>(null);
  useEffect(() => {
    if (!sectionQuery) {
      handledSectionRef.current = null;
      return;
    }
    if (handledSectionRef.current === sectionQuery) return;
    const target = viewForSection(sectionQuery);
    if (!target) return;
    handledSectionRef.current = sectionQuery;
    setActiveView((current) => (current === target ? current : target));
    requestAnimationFrame(() => {
      document.getElementById(sectionQuery)?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  }, [sectionQuery]);

  return (
    <Tabs.Root
      value={activeView}
      onValueChange={(value) => setActiveView(value as WorkspaceViewId)}
      className="space-y-5"
    >
      <Tabs.List aria-label={t("billing.views.tabListAria")}>
        <Tabs.Trigger
          value="compliance"
          leading={<ShieldAlert className="h-4 w-4" aria-hidden="true" />}
        >
          {t("billing.views.compliance.shortTitle")} <CountBadge count={complianceCount} />
        </Tabs.Trigger>
        <Tabs.Trigger
          value="revenue"
          leading={<TrendingUp className="h-4 w-4" aria-hidden="true" />}
        >
          {t("billing.views.revenue.shortTitle")} <CountBadge count={revenueCount} />
        </Tabs.Trigger>
        <Tabs.Trigger
          value="audit"
          leading={<ClipboardCheck className="h-4 w-4" aria-hidden="true" />}
        >
          {t("billing.views.audit.shortTitle")} <CountBadge count={auditCount} />
        </Tabs.Trigger>
      </Tabs.List>

      <Tabs.Content value="compliance">
        <ComplianceViewSection
          billingReport={billingReport}
          patientId={patientId}
          unifiedRows={unifiedComplianceRows}
          selectedActionId={selectedActionId}
          onSelectAction={onSelectAction}
          onOpenClause={onOpenClause}
          selectedFindingId={selectedFindingId}
        />
      </Tabs.Content>

      <Tabs.Content value="revenue">
        <RevenueViewSection
          billingReport={billingReport}
          selectedActionId={selectedActionId}
          onSelectAction={onSelectAction}
          onOpenClause={onOpenClause}
          selectedFindingId={selectedFindingId}
        />
      </Tabs.Content>

      <Tabs.Content value="audit">
        <AuditViewSection
          billingReport={billingReport}
          patientId={patientId}
          selectedActionId={selectedActionId}
          onSelectAction={onSelectAction}
          onOpenClause={onOpenClause}
        />
      </Tabs.Content>
    </Tabs.Root>
  );
}
