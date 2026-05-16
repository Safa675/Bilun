"use client";

import { useCallback, useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import SutInlineAIPanel, { SUT_INLINE_CHAT_PANEL_WIDTH } from "@/components/chat/SutInlineAIPanel";
import PatientSearch from "@/components/ui/PatientSearch";
import { getPatientBillingReport, getPatientOptimization, searchSutPatients } from "@/lib/api/sut";
import type { BillingActionReport, PatientOptimization } from "@/lib/domains/sut";
import { buildSutBillingHref, buildSutHomeHref, SUT_BRAND } from "@/lib/constants";
import { SutBillingReportSkeleton } from "@/components/skeletons/SutSkeletons";
import { SUT_ALERT_BADGE_LABELS } from "@/lib/sutLabels";
import { getUnavailableMessage, isExactOutput } from "@/lib/sutExactness";
import { theme } from "@/lib/theme";
import { SyntheticDemoProvenance } from "@/components/sut/SyntheticDemoProvenance";
import {
  fmtLabel,
  fmtNum,
  fmtPriorityLabel,
  fmtRiskLabel,
  fmtTRY2,
  fmtTRY2OrUnavailable,
  KpiCard,
} from "@/components/tabs/sut/shared";
import {
  useAiDockPosition,
  useSetAiDockPosition,
  useSetSutChatSession,
  useSutChatSession,
} from "@/stores/index";

const ACCENT = theme.accent;
const PRIORITY_COLORS: Record<BillingActionReport["priority"], string> = {
  high: "#B91C1C",
  medium: "#D97706",
  low: ACCENT,
};

const WRAPPED_HEADER_STYLE = {
  whiteSpace: "normal",
  minWidth: 120,
} as const;

function StatusChip({ label, color }: { label: string; color: string }) {
  return (
    <span
      className="sut-status-chip"
      style={{ "--sut-chip-color": color } as CSSProperties}
    >
      {label}
    </span>
  );
}

type ExactnessBlock = Parameters<typeof getUnavailableMessage>[0];

function ExactnessNotice({
  block,
  fallback,
}: {
  block: ExactnessBlock;
  fallback: string;
}) {
  return (
    <div className="sut-exactness-notice">
      {getUnavailableMessage(block, fallback)}
    </div>
  );
}

function BillingSectionShell({
  title,
  total,
  children,
}: {
  title: string;
  total?: string;
  children: ReactNode;
}) {
  return (
    <div className="frost-panel sut-premium-glass p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="sut-premium-eyebrow">
          {title}
        </h2>
        {total && (
          <span className="sut-amount-accent text-sm font-bold">
            {total}
          </span>
        )}
      </div>
      {children}
    </div>
  );
}

function TableWrap({
  minWidth,
  children,
}: {
  minWidth: number;
  children: ReactNode;
}) {
  return (
    <div className="frost-table-wrap overflow-x-auto">
      <table className="frost-table w-full" style={{ fontSize: "0.82rem", minWidth }}>
        {children}
      </table>
    </div>
  );
}

export function BillingSummary({ billingReport }: { billingReport: BillingActionReport }) {
  const reportExact = isExactOutput(billingReport);
  const priorityColor = reportExact ? PRIORITY_COLORS[billingReport.priority] : "#71717A";
  const statusLabel = reportExact ? fmtPriorityLabel(billingReport.priority) : "Partial exact";

  return (
    <div className="frost-panel sut-premium-panel p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="sut-muted-label">
            {SUT_BRAND.billingTitle}
          </p>
          <h1 className="sut-patient-id-title mt-2">{billingReport.patient_id}</h1>
          <p className="sut-section-description mt-2 max-w-3xl">
            Normative SUT rule review across labs, drugs, copay eligibility, billing strategy, and materials controls.
          </p>
          <SyntheticDemoProvenance dataSource={billingReport} className="mt-4" />
        </div>
        <StatusChip label={statusLabel} color={priorityColor} />
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-3">
        <KpiCard
          label="Rule-calculated opportunity"
          value={reportExact ? fmtTRY2(billingReport.total_recoverable_try) : "Unavailable"}
          valueColor={ACCENT}
        />
        <KpiCard
          label="Recommended actions"
          value={reportExact ? fmtNum(billingReport.action_count) : "Review sections"}
        />
        <KpiCard
          label="Priority tier"
          value={reportExact ? fmtPriorityLabel(billingReport.priority) : "Unavailable"}
          valueColor={priorityColor}
        />
      </div>
      {!reportExact && (
        <div className="mt-5">
          <ExactnessNotice
            block={billingReport}
            fallback="Billing totals remain unavailable until every billing section is exact."
          />
        </div>
      )}
    </div>
  );
}

function LabOptimizationSection({ labData }: { labData: BillingActionReport["lab"] }) {
  if (!isExactOutput(labData)) {
    return (
      <BillingSectionShell title="Lab optimization">
        <ExactnessNotice
          block={labData}
          fallback="Lab optimization findings are unavailable until the billing input contract is exact."
        />
      </BillingSectionShell>
    );
  }

  if (labData.flagged_tests.length === 0) {
    return null;
  }

  const combinedSavings = labData.hemogram_bundling_savings + labData.duplicate_test_savings;

  return (
    <BillingSectionShell title="Lab optimization" total={fmtTRY2(combinedSavings)}>
      <TableWrap minWidth={820}>
        <thead>
          <tr>
            <th>Test</th>
            <th>SUT code</th>
            <th className="num-col" style={WRAPPED_HEADER_STYLE}>Gazette price</th>
            <th>Flag</th>
            <th className="num-col" style={WRAPPED_HEADER_STYLE}>Savings</th>
          </tr>
        </thead>
        <tbody>
          {labData.flagged_tests.map((test, index) => (
            <tr key={`${test.sut_code}-${index}`}>
              <td>{test.test_name}</td>
              <td className="font-mono text-xs">{test.sut_code}</td>
              <td className="num-col">{fmtTRY2(test.gazette_price)}</td>
              <td>
                <StatusChip
                  label={fmtLabel(test.flag_type)}
                  color={test.flag_type === "hemogram_unbundling" ? "#D97706" : "#B91C1C"}
                />
              </td>
              <td className="num-col font-semibold" style={{ color: ACCENT }}>
                {fmtTRY2(test.savings_try)}
              </td>
            </tr>
          ))}
        </tbody>
      </TableWrap>
    </BillingSectionShell>
  );
}

function DrugOptimizationSection({ drugData }: { drugData: BillingActionReport["drug"] }) {
  if (!isExactOutput(drugData)) {
    return (
      <BillingSectionShell title="Drug optimization">
        <ExactnessNotice
          block={drugData}
          fallback="Drug optimization savings require exact dispensed drug claim lines and billed drug amounts."
        />
      </BillingSectionShell>
    );
  }

  if (drugData.drug_recommendations.length === 0) {
    return null;
  }

  return (
    <BillingSectionShell title="Drug optimization" total={fmtTRY2(drugData.generic_substitution_savings)}>
      <TableWrap minWidth={860}>
        <thead>
          <tr>
            <th style={WRAPPED_HEADER_STYLE}>Drug</th>
            <th>Issue</th>
            <th style={WRAPPED_HEADER_STYLE}>Alternative</th>
            <th className="num-col" style={WRAPPED_HEADER_STYLE}>Savings</th>
          </tr>
        </thead>
        <tbody>
          {drugData.drug_recommendations.map((recommendation, index) => (
            <tr key={`${recommendation.drug_name}-${index}`}>
              <td title={recommendation.drug_name}>{recommendation.drug_name}</td>
              <td>
                <StatusChip
                  label={fmtLabel(recommendation.issue)}
                  color={recommendation.issue === "passivated" ? "#B91C1C" : "#D97706"}
                />
              </td>
              <td title={recommendation.alternative}>{recommendation.alternative}</td>
              <td className="num-col font-semibold" style={{ color: ACCENT }}>
                {fmtTRY2(recommendation.savings_try)}
              </td>
            </tr>
          ))}
        </tbody>
      </TableWrap>
    </BillingSectionShell>
  );
}

function CopayOptimizationSection({ copayData }: { copayData: BillingActionReport["copay"] }) {
  if (!isExactOutput(copayData)) {
    return (
      <BillingSectionShell title="Copay optimization">
        <ExactnessNotice
          block={copayData}
          fallback="Copay optimization totals remain unavailable until both visit and prescription claim inputs are exact."
        />
      </BillingSectionShell>
    );
  }

  const savingsColor = copayData.total_copay_savings_try > 0 ? ACCENT : "#71717A";

  return (
    <BillingSectionShell title="Copay optimization" total={fmtTRY2(copayData.total_copay_savings_try)}>
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <StatusChip
            label={copayData.is_exempt ? SUT_ALERT_BADGE_LABELS.exempt : SUT_ALERT_BADGE_LABELS.notExempt}
            color={copayData.is_exempt ? ACCENT : "#A1A1AA"}
          />
          {copayData.exemption_disease && (
            <span className="text-sm" style={{ color: "#71717A" }}>
              {copayData.exemption_disease} ({copayData.exemption_range})
            </span>
          )}
        </div>

        <div className="grid gap-3 md:grid-cols-3">
          <KpiCard label="Visit copay savings" value={fmtTRY2(copayData.visit_copay_savings_try)} valueColor={savingsColor} />
          <KpiCard label="Rx copay savings" value={fmtTRY2(copayData.rx_copay_savings_try)} valueColor={savingsColor} />
          <KpiCard label="Total copay savings" value={fmtTRY2(copayData.total_copay_savings_try)} valueColor={savingsColor} />
        </div>

        {copayData.rate_corrections.length > 0 && (
          <TableWrap minWidth={760}>
            <thead>
              <tr>
                <th>Procedure</th>
                <th className="num-col" style={WRAPPED_HEADER_STYLE}>Gazette rate</th>
                <th className="num-col" style={WRAPPED_HEADER_STYLE}>Correction</th>
              </tr>
            </thead>
            <tbody>
              {copayData.rate_corrections.map((correction, index) => (
                <tr key={`${correction.procedure}-${index}`}>
                  <td>{correction.procedure}</td>
                  <td className="num-col">{fmtTRY2(correction.gazette_rate)}</td>
                  <td className="num-col font-semibold" style={{ color: ACCENT }}>
                    {fmtTRY2(correction.correction_try)}
                  </td>
                </tr>
              ))}
            </tbody>
          </TableWrap>
        )}
      </div>
    </BillingSectionShell>
  );
}

function BillingStrategySection({ strategyData }: { strategyData: BillingActionReport["billing_strategy"] }) {
  const strategyExact = isExactOutput(strategyData);

  if (!strategyExact) {
    return (
      <BillingSectionShell title="Billing strategy">
        <div className="sut-exactness-notice">
          {getUnavailableMessage(
            strategyData,
            "Billing strategy recommendations require exact billed procedure lines.",
          )}
        </div>
      </BillingSectionShell>
    );
  }

  if (strategyData.recommendations.length === 0) {
    return null;
  }

  return (
    <BillingSectionShell title="Billing strategy">
      <TableWrap minWidth={980}>
        <thead>
          <tr>
            <th style={WRAPPED_HEADER_STYLE}>Chapter</th>
            <th>Group</th>
            <th>Strategy</th>
            <th className="num-col" style={WRAPPED_HEADER_STYLE}>Package price</th>
            <th className="num-col" style={WRAPPED_HEADER_STYLE}>Itemized total</th>
            <th className="num-col" style={WRAPPED_HEADER_STYLE}>Savings</th>
          </tr>
        </thead>
        <tbody>
          {strategyData.recommendations.map((item, index) => (
            <tr key={`${item.chapter}-${index}`}>
              <td>
                <div className="font-semibold text-slate-950">{item.chapter_description}</div>
                <div className="mt-1 text-xs" style={{ color: "#71717A" }}>
                  {item.chapter}
                </div>
              </td>
              <td>{item.ek2c_group}</td>
              <td>
                <StatusChip
                  label={fmtLabel(item.strategy)}
                  color={item.strategy === "package" ? ACCENT : "#2563EB"}
                />
              </td>
              <td className="num-col">{fmtTRY2(item.package_price)}</td>
              <td className="num-col">{fmtTRY2(item.itemized_estimate)}</td>
              <td className="num-col font-semibold" style={{ color: ACCENT }}>
                {fmtTRY2(item.savings_try)}
              </td>
            </tr>
          ))}
        </tbody>
      </TableWrap>
    </BillingSectionShell>
  );
}

function MaterialsPreCheckSection({ materialsData }: { materialsData: BillingActionReport["materials"] }) {
  const ceilingEntries = Object.entries(materialsData.gazette_ceiling_by_specialty);
  const materialsExact = isExactOutput(materialsData);
  const hasExactListData =
    materialsData.pre_auth_required.length > 0 ||
    materialsData.miat_restricted.length > 0;
  const hasAnyData = hasExactListData || ceilingEntries.length > 0;

  if (!hasAnyData && materialsExact) {
    return null;
  }

  return (
    <BillingSectionShell title="Materials pre-check">
      <div className="space-y-4">
        {!materialsExact && (
          <ExactnessNotice
            block={materialsData}
            fallback="Material ceiling estimates remain unavailable until this section is fully exact."
          />
        )}
        {materialsData.pre_auth_required.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-bold uppercase tracking-wider" style={{ color: "#D97706" }}>
              Pre-authorization required
            </p>
            <TableWrap minWidth={820}>
              <thead>
                <tr>
                  <th>SUT code</th>
                  <th>Material</th>
                  <th className="num-col" style={WRAPPED_HEADER_STYLE}>Gazette price</th>
                  <th style={WRAPPED_HEADER_STYLE}>Note</th>
                </tr>
              </thead>
              <tbody>
                {materialsData.pre_auth_required.map((material, index) => (
                  <tr key={`${material.sut_code}-${index}`}>
                    <td className="font-mono text-xs">{material.sut_code}</td>
                    <td>{material.material_name}</td>
                    <td className="num-col">{fmtTRY2(material.price_try)}</td>
                    <td>{material.note}</td>
                  </tr>
                ))}
              </tbody>
            </TableWrap>
          </div>
        )}

        {materialsData.miat_restricted.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-bold uppercase tracking-wider" style={{ color: "#B91C1C" }}>
              MIAT restricted
            </p>
            <TableWrap minWidth={900}>
              <thead>
                <tr>
                  <th>SUT code</th>
                  <th>Material</th>
                  <th style={WRAPPED_HEADER_STYLE}>MIAT period</th>
                  <th className="num-col" style={WRAPPED_HEADER_STYLE}>Gazette price</th>
                  <th style={WRAPPED_HEADER_STYLE}>Note</th>
                </tr>
              </thead>
              <tbody>
                {materialsData.miat_restricted.map((material, index) => (
                  <tr key={`${material.sut_code}-${index}`}>
                    <td className="font-mono text-xs">{material.sut_code}</td>
                    <td>{material.material_name}</td>
                    <td>{material.miat_period}</td>
                    <td className="num-col">{fmtTRY2(material.price_try)}</td>
                    <td>{material.note}</td>
                  </tr>
                ))}
              </tbody>
            </TableWrap>
          </div>
        )}

        {materialsExact && ceilingEntries.length > 0 && (
          <div className="rounded-2xl border p-4" style={{ borderColor: "rgba(122,139,122,0.12)" }}>
            <p className="text-xs font-bold uppercase tracking-wider" style={{ color: "#71717A" }}>
              Gazette ceiling (p90) by specialty
            </p>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              {ceilingEntries.map(([specialty, amount]) => (
                <div key={specialty} className="rounded-xl px-3 py-2" style={{ background: theme.accentAlpha(0.05) }}>
                  <div className="text-xs font-semibold uppercase tracking-wider" style={{ color: "#71717A" }}>
                    {specialty}
                  </div>
                  <div className="mt-1 text-sm font-bold text-slate-950">{fmtTRY2(amount)}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </BillingSectionShell>
  );
}

function SutOptimizationSection({ optimization }: { optimization: PatientOptimization }) {
  const surchargeExact = isExactOutput(optimization.surcharge_exposure);
  const rateExact = isExactOutput(optimization.copay_rate_exposure);
  const drgExact = isExactOutput(optimization.drg_unbundling);
  const surchargeCount = optimization.surcharge_exposure.n_applicable_procedures;
  const rateCount = optimization.copay_rate_exposure.n_applicable_procedures;
  const drgRiskLabel = optimization.drg_unbundling?.has_unbundling_risk ? fmtRiskLabel("high") : fmtRiskLabel("low");
  const drgRiskColor = optimization.drg_unbundling?.has_unbundling_risk ? "#B91C1C" : ACCENT;

  return (
    <BillingSectionShell title="SUT optimization findings">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-xl p-4" style={{ background: theme.accentAlpha(0.05) }}>
          <div className="text-xs font-bold uppercase tracking-wider" style={{ color: "#71717A" }}>
            Copay exemption
          </div>
          <div className="mt-2">
            <StatusChip
              label={optimization.copay_exemptions.exempt ? SUT_ALERT_BADGE_LABELS.exempt : SUT_ALERT_BADGE_LABELS.notExempt}
              color={optimization.copay_exemptions.exempt ? ACCENT : "#A1A1AA"}
            />
          </div>
          <p className="mt-2 text-xs" style={{ color: "#71717A" }}>
            {fmtNum(optimization.copay_exemptions.qualifying_diagnoses.length)} qualifying diagnoses
          </p>
        </div>

        <div className="rounded-xl p-4" style={{ background: surchargeExact && (surchargeCount ?? 0) > 0 ? "rgba(234,88,12,0.06)" : theme.accentAlpha(0.05) }}>
          <div className="text-xs font-bold uppercase tracking-wider" style={{ color: "#71717A" }}>
            Surcharge compliance
          </div>
          <div className="mt-2">
            <StatusChip
              label={
                surchargeExact
                  ? ((surchargeCount ?? 0) > 0 ? `${fmtNum(surchargeCount ?? 0)} flags` : SUT_ALERT_BADGE_LABELS.clear)
                  : SUT_ALERT_BADGE_LABELS.unavailable
              }
              color={surchargeExact && (surchargeCount ?? 0) > 0 ? "#EA580C" : surchargeExact ? ACCENT : "#71717A"}
            />
          </div>
          {!surchargeExact && (
            <p className="mt-2 text-xs" style={{ color: "#71717A" }}>
              {getUnavailableMessage(
                optimization.surcharge_exposure,
                "Surcharge compliance needs exact billed procedure codes and procedure dates.",
              )}
            </p>
          )}
        </div>

        <div className="rounded-xl p-4" style={{ background: theme.accentAlpha(0.05) }}>
          <div className="text-xs font-bold uppercase tracking-wider" style={{ color: "#71717A" }}>
            Copay rate compliance
          </div>
          <p className="mt-2 text-sm font-semibold text-slate-950">
            {rateExact
              ? ((rateCount ?? 0) > 0 ? `${fmtNum(rateCount ?? 0)} capped procedures` : "No rate caps applicable")
              : "Unavailable"}
          </p>
          {!rateExact && (
            <p className="mt-2 text-xs" style={{ color: "#71717A" }}>
              {getUnavailableMessage(
                optimization.copay_rate_exposure,
                "Copay rate compliance needs exact billed procedure codes and procedure dates.",
              )}
            </p>
          )}
        </div>

        {optimization.drg_unbundling && (
          <div className="rounded-xl p-4" style={{ background: drgExact && optimization.drg_unbundling.has_unbundling_risk ? "rgba(185,28,28,0.06)" : theme.accentAlpha(0.05) }}>
            <div className="text-xs font-bold uppercase tracking-wider" style={{ color: "#71717A" }}>
              DRG unbundling risk
            </div>
            <div className="mt-2">
              <StatusChip
                label={drgExact ? drgRiskLabel : SUT_ALERT_BADGE_LABELS.unavailable}
                color={drgExact ? drgRiskColor : "#71717A"}
              />
            </div>
            {drgExact ? (
              <p className="mt-2 text-xs" style={{ color: "#71717A" }}>
                Potential savings: {fmtTRY2OrUnavailable(optimization.drg_unbundling.total_potential_savings)}
              </p>
            ) : (
              <p className="mt-2 text-xs" style={{ color: "#71717A" }}>
                {getUnavailableMessage(
                  optimization.drg_unbundling,
                  "DRG unbundling risk needs exact itemized billed procedure lines and package eligibility context.",
                )}
              </p>
            )}
          </div>
        )}
      </div>
    </BillingSectionShell>
  );
}

export default function SutPatientBillingPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const patientId = params?.id ?? null;
  const requestRef = useRef<AbortController | null>(null);
  const [billingReport, setBillingReport] = useState<BillingActionReport | null>(null);
  const [optimization, setOptimization] = useState<PatientOptimization | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadNonce, setReloadNonce] = useState(0);
  const chatDock = useAiDockPosition();
  const setChatDock = useSetAiDockPosition();

  useEffect(() => {
    if (!patientId) {
      return;
    }

    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;

    async function load(): Promise<void> {
      try {
        setLoading(true);
        setError(null);
        setBillingReport(null);
        setOptimization(null);

        const [reportData, optimizationData] = await Promise.all([
          getPatientBillingReport(patientId, { signal: controller.signal }),
          getPatientOptimization(patientId, { signal: controller.signal }).catch(() => null),
        ]);

        if (!controller.signal.aborted && requestRef.current === controller) {
          setBillingReport(reportData);
          setOptimization(optimizationData);
        }
      } catch (caught) {
        if (caught instanceof DOMException && caught.name === "AbortError") {
          return;
        }
        if (!controller.signal.aborted && requestRef.current === controller) {
          setError(caught instanceof Error ? caught.message : "Failed to load billing data");
        }
      } finally {
        if (!controller.signal.aborted && requestRef.current === controller) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      controller.abort();
    };
  }, [patientId, reloadNonce]);

  const handlePatientSelect = useCallback((selectedPatientId: string) => {
    router.push(buildSutBillingHref(selectedPatientId));
  }, [router]);

  const handleRetry = useCallback(() => {
    setReloadNonce((value) => value + 1);
  }, []);
  const chatSessionKey = `billing:${patientId ?? ""}`;
  const chatState = useSutChatSession(chatSessionKey);
  const setChatSession = useSetSutChatSession();
  const chatShiftX = chatDock !== "center"
    ? (chatDock === "left" ? SUT_INLINE_CHAT_PANEL_WIDTH / 2 : -(SUT_INLINE_CHAT_PANEL_WIDTH / 2))
    : 0;

  return (
    <main id="main-content" className="sut-app-main">
      <div
        style={{
          transform: `translateX(${chatShiftX}px)`,
          transition: "transform 0.25s ease",
        }}
      >
        <section className="mx-auto max-w-7xl space-y-6">
          <header className="frost-panel sut-premium-panel sut-home-header">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <p className="sut-premium-eyebrow">
                  {SUT_BRAND.moduleLabel}
                </p>
                <h1 className="sut-app-title mt-3">{SUT_BRAND.billingTitle}</h1>
                <p className="sut-premium-subtitle mt-2 max-w-3xl">
                  {SUT_BRAND.billingDescription}
                </p>
                <nav className="sut-breadcrumb mt-4" aria-label="SUT billing breadcrumb">
                  <Link href={buildSutHomeHref("optimizer")} className="sut-breadcrumb-link">
                    Back to SUT workspace
                  </Link>
                  <span className="sut-breadcrumb-separator" aria-hidden="true">/</span>
                  <span className="sut-breadcrumb-current">
                    Patient {patientId ?? "unknown"}
                  </span>
                </nav>
              </div>

              <div className="sut-route-search-control">
                <p className="sut-muted-label mb-2">Patient search</p>
                <PatientSearch
                  selectedPatientId={patientId}
                  onSelect={handlePatientSelect}
                  searchFn={searchSutPatients}
                  id="billing-patient-search"
                  placeholder="Search patient for billing..."
                />
              </div>
            </div>
          </header>

          {chatDock === "center" && (
            <SutInlineAIPanel
              patientId={patientId}
              activeTab="SUT Billing Review"
              dock={chatDock}
              onDockChange={setChatDock}
              chatState={chatState}
              onChatStateChange={(state) => setChatSession(chatSessionKey, state)}
            />
          )}

          {error && (
            <div className="frost-panel sut-premium-error rounded-2xl p-6">
              <h2 className="sut-premium-error-title text-lg font-bold">
                Billing report error
              </h2>
              <p className="sut-premium-error-hint mt-2 text-sm">
                {error}
              </p>
              <div className="mt-4 flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={handleRetry}
                  className="sut-section-btn sut-section-btn-active"
                >
                  Retry
                </button>
                <Link href={buildSutHomeHref("analytics")} className="sut-section-btn">
                  Back to SUT workspace
                </Link>
              </div>
            </div>
          )}

          {loading && (
            <SutBillingReportSkeleton patientId={patientId} />
          )}

          {!loading && !error && billingReport && (
            <>
              <BillingSummary billingReport={billingReport} />
              <SyntheticDemoProvenance dataSources={[billingReport, optimization]} />
              <LabOptimizationSection labData={billingReport.lab} />
              <DrugOptimizationSection drugData={billingReport.drug} />
              <CopayOptimizationSection copayData={billingReport.copay} />
              <BillingStrategySection strategyData={billingReport.billing_strategy} />
              <MaterialsPreCheckSection materialsData={billingReport.materials} />
              {optimization && <SutOptimizationSection optimization={optimization} />}

              <div className="sut-note-muted py-2 text-center text-xs">
                Normative analysis based on official SUT gazette rule references (EK-1A, EK-2B, EK-2C, EK-4A)
              </div>
            </>
          )}

          {!loading && !error && !billingReport && (
            <div className="frost-panel rounded-2xl p-6 text-center">
              <p className="sut-section-description text-sm">
                No billing data available for patient {patientId ?? "unknown"}.
              </p>
            </div>
          )}
        </section>
      </div>
      {chatDock !== "center" && (
        <SutInlineAIPanel
          patientId={patientId}
          activeTab="SUT Billing Review"
          dock={chatDock}
          onDockChange={setChatDock}
          chatState={chatState}
          onChatStateChange={(state) => setChatSession(chatSessionKey, state)}
        />
      )}
    </main>
  );
}
