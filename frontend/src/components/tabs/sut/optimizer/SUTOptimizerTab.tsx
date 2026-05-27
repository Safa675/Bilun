"use client";

import { useState, useEffect, useRef, type ChangeEvent, type FormEvent } from "react";
import Link from "next/link";
import {
  BadgeDollarSign,
  ChartColumnBig,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import useStaggeredReveal from "@/hooks/useStaggeredReveal";
import { useConfig } from "@/lib/configContext";
import { theme } from "@/lib/theme";
import { ApiRequestError } from "@/lib/apiClient";
import {
  getPatientAlerts,
  getRevenueRecovery,
  getOptimizationSummary,
  searchSutPatients,
} from "@/lib/api/sut";
import type {
  PatientAlertsCategory,
  PatientAlertsStatus,
  PatientAlertsResponse,
  CohortRecoverySummary,
  OptimizationSummary,
} from "@/lib/domains/sut";
import {
  ALERT_PAGE_SIZE,
  buildPatientAlertsQuery,
  clampAlertPage,
  getAlertStatusLabel,
  getAlertStatusOptions,
  parseAlertPageInput,
} from "../../sutOptimizerHelpers";
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import PatientSearch from "@/components/ui/PatientSearch";
import {
  buildSutBillingHref,
} from "@/lib/constants";
import { SutAlertTableSkeleton } from "@/components/skeletons/SutSkeletons";
import { getUnavailableMessage, isExactOutput } from "@/lib/sutExactness";
import {
  SUT_ACTION_LABELS,
  SUT_ALERT_BADGE_LABELS,
} from "@/lib/sutLabels";
import {
  fmtLabel,
  fmtNum,
  fmtNumOrUnavailable,
  fmtPctRatio as fmtPct,
  fmtPriorityLabel,
  fmtTRY,
  fmtTRYOrUnavailable,
  fmtTRY2OrUnavailable,
  KpiCard,
} from "../shared";
import {
  Chip,
  DataTable,
  Eyebrow,
  Section,
  Stat,
  Surface,
  TabsList,
  TabsRoot,
  TabsTrigger,
} from "@/components/primitives";

/* ═══════════════════════════════════════════════════════════════════════════
   CONSTANTS
   ═══════════════════════════════════════════════════════════════════════════ */

const ACCENT = theme.accent;

const PIE_COLORS = [theme.textPrimary, theme.gold, theme.warning, theme.danger];

interface AlertQueryBarProps {
  category: PatientAlertsCategory;
  status: PatientAlertsStatus;
  search: string;
  loading: boolean;
  pagination: PatientAlertsResponse["pagination"] | null;
  onStatusChange: (status: PatientAlertsStatus) => void;
  onSearchChange: (search: string) => void;
  onPageChange: (page: number) => void;
}

function AlertQueryBar({
  category,
  status,
  search,
  loading,
  pagination,
  onStatusChange,
  onSearchChange,
  onPageChange,
}: AlertQueryBarProps) {
  const totalMatching = pagination?.total_matching ?? 0;
  const limit = pagination?.limit ?? ALERT_PAGE_SIZE;
  const offset = pagination?.offset ?? 0;
  const currentPage = Math.floor(offset / Math.max(limit, 1)) + 1;
  const totalPages = Math.max(1, Math.ceil(totalMatching / Math.max(limit, 1)));
  const hasPrev = currentPage > 1;
  const hasNext = pagination?.has_more ?? false;
  const [pageDraft, setPageDraft] = useState(() => ({ value: String(currentPage), page: currentPage }));
  const pageInput = pageDraft.page === currentPage ? pageDraft.value : String(currentPage);

  function handlePageInputChange(event: ChangeEvent<HTMLInputElement>) {
    setPageDraft({ value: event.target.value.replace(/[^\d]/g, ""), page: currentPage });
  }

  function handlePageJumpSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsedPage = parseAlertPageInput(pageInput);
    if (parsedPage === null) {
      setPageDraft({ value: String(currentPage), page: currentPage });
      return;
    }

    const nextPage = clampAlertPage(parsedPage, totalPages);
    setPageDraft({ value: String(nextPage), page: nextPage });
    if (nextPage !== currentPage) {
      onPageChange(nextPage);
    }
  }

  return (
    <Surface variant="base" padding="lg">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-2">
          <Eyebrow as="div">Search</Eyebrow>
          <input
            type="text"
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="Search patient ID..."
            className="glass app-select patient-search-input sut-filter-control"
          />
        </div>

        <div className="space-y-2">
          <Eyebrow as="div">Filter</Eyebrow>
          <TabsRoot
            value={status}
            onValueChange={(value) => onStatusChange(value as PatientAlertsStatus)}
            className="gap-0"
          >
            <TabsList density="compact" aria-label="Alert status filter">
              {getAlertStatusOptions(category).map((option) => (
                <TabsTrigger key={option} value={option} density="compact">
                  {getAlertStatusLabel(option)}
                </TabsTrigger>
              ))}
            </TabsList>
          </TabsRoot>
        </div>

        <div className="space-y-2 lg:text-right">
          <Eyebrow as="div" className="lg:text-right">Pagination</Eyebrow>
          <div className="flex flex-col gap-2 sm:items-start lg:items-end">
            <div className="flex flex-wrap items-center gap-2 lg:justify-end">
              <button
                type="button"
                className="rounded-[var(--r-md)] border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-semibold text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)] disabled:opacity-50"
                onClick={() => onPageChange(Math.max(currentPage - 1, 1))}
                disabled={!hasPrev || loading}
              >
                Prev
              </button>
              <span className="text-xs font-semibold text-[var(--text-secondary)]">
                Page {fmtNum(currentPage)} of {fmtNum(totalPages)}
              </span>
              <button
                type="button"
                className="rounded-[var(--r-md)] border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-semibold text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)] disabled:opacity-50"
                onClick={() => onPageChange(currentPage + 1)}
                disabled={!hasNext || loading}
              >
                Next
              </button>
            </div>

            <form className="flex flex-wrap items-center gap-2 lg:justify-end" onSubmit={handlePageJumpSubmit}>
              <label
                htmlFor={`${category}-page-jump`}
                className="text-[0.68rem] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]"
              >
                Jump to page
              </label>
              <input
                id={`${category}-page-jump`}
                type="text"
                inputMode="numeric"
                value={pageInput}
                onChange={handlePageInputChange}
                placeholder={String(currentPage)}
                disabled={loading || totalPages <= 1}
                className="glass app-select sut-page-jump-control"
              />
              <button
                type="submit"
                className="rounded-[var(--r-md)] border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-semibold text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)] disabled:opacity-50"
                disabled={loading || totalPages <= 1}
              >
                Go
              </button>
            </form>
          </div>
        </div>
      </div>
      <p className="mt-3 text-xs text-[var(--text-secondary)]">
        {totalMatching > 0 ? `Displaying the current ${ALERT_CATEGORY_LABELS[category]} page from ${fmtNum(totalMatching)} matching patients.` : "No matching patients for the current query."}
      </p>
    </Surface>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   SECTION NAVIGATION (Single-Tier: Compliance Alerts + Revenue Recovery)
   ═══════════════════════════════════════════════════════════════════════════ */

type SectionId = "alerts" | "revenue";

interface SectionMeta {
  id: SectionId;
  Icon: typeof ShieldAlert;
  label: string;
  description: string;
}

const SECTIONS: SectionMeta[] = [
  {
    id: "alerts",
    Icon: ShieldAlert,
    label: "Compliance Alerts",
    description: "Per-patient actionable alerts combining exact copayment exemption findings (EK-1A) with explicit unavailable states for optimization checks that still require exact claim-line inputs.",
  },
  {
    id: "revenue",
    Icon: BadgeDollarSign,
    label: "Revenue Recovery",
    description: "Cohort-level recovery review dashboard for active billing algorithms, plus availability notices for optimization checks that remain blocked on exact claim-line data.",
  },
];

/* ═══════════════════════════════════════════════════════════════════════════
   SHARED ALERT TABLE HELPERS
   ═══════════════════════════════════════════════════════════════════════════ */

function AlertBadge({ label, color }: { label: string; color: string }) {
  return (
    <span
      className="inline-block rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider"
      style={{ background: `${color}15`, color }}
    >
      {label}
    </span>
  );
}

function ActionBadge({ action }: { action: string | null }) {
  if (!action) return <span className="text-xs" style={{ color: "#A1A1AA" }}>{SUT_ACTION_LABELS.noActionNeeded}</span>;
  return (
    <span className="text-xs font-medium" style={{ color: theme.accent }}>
      {action}
    </span>
  );
}

function getAlertsErrorPresentation(error: Error): { title: string; hint: string } {
  if (error instanceof ApiRequestError) {
    if (error.isNetworkError) {
      return {
        title: error.message,
        hint: "Could not reach the API server. Start it with `python -m uvicorn src.api:app` and try again.",
      };
    }

    const backendDetail = error.detail ?? error.message;
    if (
      error.status === 503
      && /analytics build|canonical build|pipeline/i.test(backendDetail)
    ) {
      return {
        title: "SUT alerts are temporarily unavailable.",
        hint: backendDetail,
      };
    }

    return {
      title: backendDetail,
      hint: "The backend returned an error while loading patient alerts.",
    };
  }

  return {
    title: error.message || "Failed to load patient alerts",
    hint: "The backend returned an unexpected response while loading patient alerts.",
  };
}

function UnavailableBadge({ text }: { text: string }) {
  return <MethodologyBadge warn label="Unavailable" text={text} />;
}

function getAlertSummaryExactness(
  summary: PatientAlertsResponse["summary"],
  category: "surcharge" | "copay_rates",
) {
  if (category === "surcharge") {
    return {
      exactness_status: summary.surcharge_exactness_status,
      unavailable_reason: summary.surcharge_unavailable_reason,
      required_inputs_missing: summary.surcharge_required_inputs_missing,
    };
  }
  return {
    exactness_status: summary.copay_rate_exactness_status,
    unavailable_reason: summary.copay_rate_unavailable_reason,
    required_inputs_missing: summary.copay_rate_required_inputs_missing,
  };
}

/* ═══════════════════════════════════════════════════════════════════════════
   SECTION A: COPAY EXEMPTION ALERTS (EK-1A)
   ═══════════════════════════════════════════════════════════════════════════ */

function CopayExemptionAlerts({ data, loading }: { data: PatientAlertsResponse | null; loading: boolean }) {
  const { regulatory } = useConfig();

  if (loading) {
    return <SutAlertTableSkeleton />;
  }
  if (!data) {
    return null;
  }

  const { patients, summary } = data;
  const totalMatching = data.pagination?.total_matching ?? patients.length;
  const limit = data.pagination?.limit ?? ALERT_PAGE_SIZE;
  const offset = data.pagination?.offset ?? 0;
  const rangeStart = totalMatching > 0 ? offset + 1 : 0;
  const rangeEnd = patients.length > 0 ? Math.min(offset + patients.length, totalMatching) : 0;
  const currentPage = Math.floor(offset / Math.max(limit, 1)) + 1;
  const totalPages = Math.max(1, Math.ceil(totalMatching / Math.max(limit, 1)));

  const exemptRate = summary.exemption_rate;

  return (
    <div className="space-y-5">
      <MethodologyBadge text={`Cross-references patient ICD-10 diagnoses against ${regulatory.ek1a_exemption_count} chronic disease exemption ranges from gazette annex EK-1A. Official SUT gazette rule references.`} />

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard label="Total Patients" value={fmtNum(summary.n_total_patients)} />
        <KpiCard label="Exempt Patients" value={fmtNum(summary.n_exempt_patients)} valueColor={theme.accent} sub="Should have copay waived" />
        <KpiCard label="Exemption Rate" value={fmtPct(exemptRate)} valueColor={ACCENT} />
        <KpiCard label="Non-Exempt" value={fmtNum(summary.n_total_patients - summary.n_exempt_patients)} sub="Standard copay applies" />
      </div>

      <Section
        title="Patient Alerts"
        trailing={<Chip variant="outline">{getAlertStatusLabel(data.query.status)}</Chip>}
        padding="lg"
        className="[&_h2]:text-sm [&_h2]:font-semibold [&_h2]:uppercase [&_h2]:tracking-wider [&_h2]:text-[var(--gold)]"
      >
        <p className="mb-2 text-xs text-[var(--text-muted)]">
          Showing {fmtNum(rangeStart)}-{fmtNum(rangeEnd)} of {fmtNum(totalMatching)} patients on page {fmtNum(currentPage)} of {fmtNum(totalPages)}
        </p>

        <DataTable minWidth={720} className="max-h-[420px] overflow-y-auto text-xs">
          <thead>
            <tr>
              <th>Patient ID</th>
              <th className="text-center">Status</th>
              <th className="num-col">Qualifying</th>
              <th>Top Diagnosis</th>
              <th>Recommended Action</th>
            </tr>
          </thead>
          <tbody>
            {patients.map((p) => (
              <tr key={p.patient_id}>
                <td className="font-mono" style={{ color: ACCENT }}>{p.patient_id}</td>
                <td className="text-center">
                  {p.copay_exemption.exempt
                    ? <AlertBadge label={SUT_ALERT_BADGE_LABELS.exempt} color={theme.accent} />
                    : <AlertBadge label={SUT_ALERT_BADGE_LABELS.notExempt} color="#A1A1AA" />
                  }
                </td>
                <td className="num-col">{fmtNum(p.copay_exemption.n_qualifying)}</td>
                <td className="truncate max-w-[200px]" title={p.copay_exemption.qualifying_diagnoses[0]?.disease}>
                  {p.copay_exemption.qualifying_diagnoses[0]?.disease ?? "\u2014"}
                </td>
                <td><ActionBadge action={p.copay_exemption.action} /></td>
              </tr>
            ))}
            {patients.length === 0 && (
              <tr><td colSpan={5} className="text-center py-6 text-[var(--text-muted)]">No patients match this filter.</td></tr>
            )}
          </tbody>
        </DataTable>
      </Section>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   SECTION B: SURCHARGE COMPLIANCE ALERTS (EK-2G)
   ═══════════════════════════════════════════════════════════════════════════ */

function SurchargeComplianceAlerts({ data, loading }: { data: PatientAlertsResponse | null; loading: boolean }) {
  if (loading) {
    return <SutAlertTableSkeleton />;
  }
  if (!data) {
    return null;
  }

  const { patients, summary } = data;
  const summaryExactness = getAlertSummaryExactness(summary, "surcharge");
  const isUnavailable = !isExactOutput(summaryExactness);
  const unavailableMessage = getUnavailableMessage(
    summaryExactness,
    "Surcharge compliance is unavailable until exact billed procedure codes and procedure dates are present in the SUT claim inputs.",
  );
  const totalMatching = data.pagination?.total_matching ?? patients.length;
  const limit = data.pagination?.limit ?? ALERT_PAGE_SIZE;
  const offset = data.pagination?.offset ?? 0;
  const rangeStart = totalMatching > 0 ? offset + 1 : 0;
  const rangeEnd = patients.length > 0 ? Math.min(offset + patients.length, totalMatching) : 0;
  const currentPage = Math.floor(offset / Math.max(limit, 1)) + 1;
  const totalPages = Math.max(1, Math.ceil(totalMatching / Math.max(limit, 1)));

  return (
    <div className="space-y-5">
      {isUnavailable ? (
        <UnavailableBadge text={unavailableMessage} />
      ) : (
        <MethodologyBadge text="Uses exact dated procedure claim lines and explicit surcharge rule flags from the active SUT runtime inputs." />
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard label="Total Patients" value={fmtNum(summary.n_total_patients)} />
        <KpiCard
          label={isUnavailable ? "Unavailable Patients" : "Clear Patients"}
          value={
            isUnavailable
              ? fmtNum(summary.n_patients_with_surcharge_unavailable ?? summary.n_total_patients)
              : fmtNum(summary.n_total_patients - (summary.n_patients_with_surcharge_flags ?? 0))
          }
          valueColor="#B45309"
          sub={isUnavailable ? "Need exact claim lines" : "No surcharge flags"}
        />
        <KpiCard
          label="Patients Flagged"
          value={isUnavailable ? "Unavailable" : fmtNum(summary.n_patients_with_surcharge_flags ?? 0)}
          valueColor="#B45309"
          sub={isUnavailable ? "No exact surcharge findings yet" : "Exact claim-line findings"}
        />
        <KpiCard
          label="Total Flags"
          value={isUnavailable ? "Unavailable" : fmtNum(summary.total_surcharge_flags ?? 0)}
          valueColor="#B91C1C"
          sub={isUnavailable ? "Counts resume after exact inputs land" : "Exact procedure flags"}
        />
      </div>

      <Section
        title="Patient Alerts"
        trailing={<Chip variant="outline">{getAlertStatusLabel(data.query.status)}</Chip>}
        padding="lg"
        className="[&_h2]:text-sm [&_h2]:font-semibold [&_h2]:uppercase [&_h2]:tracking-wider [&_h2]:text-[var(--gold)]"
      >
        <p className="mb-2 text-xs text-[var(--text-muted)]">
          Showing {fmtNum(rangeStart)}-{fmtNum(rangeEnd)} of {fmtNum(totalMatching)} patients on page {fmtNum(currentPage)} of {fmtNum(totalPages)}
        </p>

        <DataTable minWidth={720} className="max-h-[420px] overflow-y-auto text-xs">
          <thead>
            <tr>
              <th>Patient ID</th>
              <th className="text-center">Status</th>
              <th className="num-col">No-Surcharge Rules</th>
              <th>Top Procedure</th>
              <th>Recommended Action</th>
            </tr>
          </thead>
          <tbody>
            {patients.map((p) => (
              <tr key={p.patient_id}>
                <td className="font-mono" style={{ color: ACCENT }}>{p.patient_id}</td>
                <td className="text-center">
                  {!isExactOutput(p.surcharge_exposure)
                    ? <AlertBadge label={SUT_ALERT_BADGE_LABELS.unavailable} color={theme.textMuted} />
                    : (p.surcharge_exposure.n_applicable ?? 0) > 0
                    ? <AlertBadge label={SUT_ALERT_BADGE_LABELS.flagged} color="#B45309" />
                    : <AlertBadge label={SUT_ALERT_BADGE_LABELS.clear} color={theme.accent} />
                  }
                </td>
                <td className="num-col font-bold" style={{ color: isExactOutput(p.surcharge_exposure) && (p.surcharge_exposure.n_applicable ?? 0) > 0 ? "#B45309" : "#A1A1AA" }}>
                  {p.surcharge_exposure.n_applicable !== null ? fmtNum(p.surcharge_exposure.n_applicable) : "\u2014"}
                </td>
                <td className="truncate max-w-[200px]" title={p.surcharge_exposure.top_rules[0]?.name}>
                  {p.surcharge_exposure.top_rules[0]?.name ?? (isExactOutput(p.surcharge_exposure) ? "\u2014" : "Exact procedure codes required")}
                </td>
                <td>
                  {isExactOutput(p.surcharge_exposure)
                    ? <ActionBadge action={p.surcharge_exposure.action} />
                    : <span className="text-xs text-[var(--text-muted)]">Unavailable</span>
                  }
                </td>
              </tr>
            ))}
            {patients.length === 0 && (
              <tr><td colSpan={5} className="text-center py-6 text-[var(--text-muted)]">No patients match this filter.</td></tr>
            )}
          </tbody>
        </DataTable>
      </Section>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   SECTION C: COPAY RATE COMPLIANCE ALERTS (EK-2C-1)
   ═══════════════════════════════════════════════════════════════════════════ */

function CopayRateAlerts({ data, loading }: { data: PatientAlertsResponse | null; loading: boolean }) {
  if (loading) {
    return <SutAlertTableSkeleton />;
  }
  if (!data) {
    return null;
  }

  const { patients, summary } = data;
  const summaryExactness = getAlertSummaryExactness(summary, "copay_rates");
  const isUnavailable = !isExactOutput(summaryExactness);
  const unavailableMessage = getUnavailableMessage(
    summaryExactness,
    "Copay rate compliance is unavailable until exact billed procedure codes and procedure dates are present in the SUT claim inputs.",
  );
  const totalMatching = data.pagination?.total_matching ?? patients.length;
  const limit = data.pagination?.limit ?? ALERT_PAGE_SIZE;
  const offset = data.pagination?.offset ?? 0;
  const rangeStart = totalMatching > 0 ? offset + 1 : 0;
  const rangeEnd = patients.length > 0 ? Math.min(offset + patients.length, totalMatching) : 0;
  const currentPage = Math.floor(offset / Math.max(limit, 1)) + 1;
  const totalPages = Math.max(1, Math.ceil(totalMatching / Math.max(limit, 1)));

  return (
    <div className="space-y-5">
      {isUnavailable ? (
        <UnavailableBadge text={unavailableMessage} />
      ) : (
        <MethodologyBadge text="Uses exact dated procedure claim lines, explicit copay-rate rule flags, and billed/payable amounts from the active SUT runtime inputs." />
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard label="Total Patients" value={fmtNum(summary.n_total_patients)} />
        <KpiCard
          label={isUnavailable ? "Unavailable Patients" : "Clear Patients"}
          value={
            isUnavailable
              ? fmtNum(summary.n_patients_with_copay_rate_unavailable ?? summary.n_total_patients)
              : fmtNum(summary.n_total_patients - (summary.n_patients_with_copay_rate_flags ?? 0))
          }
          valueColor="#B45309"
          sub={isUnavailable ? "Need exact claim lines" : "No copay-rate flags"}
        />
        <KpiCard
          label="Patients Flagged"
          value={isUnavailable ? "Unavailable" : fmtNum(summary.n_patients_with_copay_rate_flags ?? 0)}
          valueColor="#B45309"
          sub={isUnavailable ? "No exact rate findings yet" : "Exact claim-line findings"}
        />
        <KpiCard
          label="Total Flags"
          value={isUnavailable ? "Unavailable" : fmtNum(summary.total_copay_rate_flags ?? 0)}
          valueColor="#B91C1C"
          sub={isUnavailable ? "Counts resume after exact inputs land" : "Exact procedure flags"}
        />
      </div>

      <Section
        title="Patient Alerts"
        trailing={<Chip variant="outline">{getAlertStatusLabel(data.query.status)}</Chip>}
        padding="lg"
        className="[&_h2]:text-sm [&_h2]:font-semibold [&_h2]:uppercase [&_h2]:tracking-wider [&_h2]:text-[var(--gold)]"
      >
        <p className="mb-2 text-xs text-[var(--text-muted)]">
          Showing {fmtNum(rangeStart)}-{fmtNum(rangeEnd)} of {fmtNum(totalMatching)} patients on page {fmtNum(currentPage)} of {fmtNum(totalPages)}
        </p>

        <DataTable minWidth={720} className="max-h-[420px] overflow-y-auto text-xs">
          <thead>
            <tr>
              <th>Patient ID</th>
              <th className="text-center">Status</th>
              <th className="num-col">Rate-Capped Procs</th>
              <th className="num-col">Mean Rate</th>
              <th>Recommended Action</th>
            </tr>
          </thead>
          <tbody>
            {patients.map((p) => (
              <tr key={p.patient_id}>
                <td className="font-mono" style={{ color: ACCENT }}>{p.patient_id}</td>
                <td className="text-center">
                  {!isExactOutput(p.copay_rate_exposure)
                    ? <AlertBadge label={SUT_ALERT_BADGE_LABELS.unavailable} color={theme.textMuted} />
                    : (p.copay_rate_exposure.n_applicable ?? 0) > 0
                    ? <AlertBadge label={SUT_ALERT_BADGE_LABELS.flagged} color="#B45309" />
                    : <AlertBadge label={SUT_ALERT_BADGE_LABELS.clear} color={theme.accent} />
                  }
                </td>
                <td className="num-col font-bold" style={{ color: isExactOutput(p.copay_rate_exposure) && (p.copay_rate_exposure.n_applicable ?? 0) > 0 ? "#B45309" : "#A1A1AA" }}>
                  {p.copay_rate_exposure.n_applicable !== null ? fmtNum(p.copay_rate_exposure.n_applicable) : "\u2014"}
                </td>
                <td className="num-col">
                  {p.copay_rate_exposure.mean_rate !== null ? fmtPct(p.copay_rate_exposure.mean_rate / 100, 0) : "\u2014"}
                </td>
                <td>
                  {isExactOutput(p.copay_rate_exposure)
                    ? <ActionBadge action={p.copay_rate_exposure.action} />
                    : <span className="text-xs text-[var(--text-muted)]">Unavailable</span>
                  }
                </td>
              </tr>
            ))}
            {patients.length === 0 && (
              <tr><td colSpan={5} className="text-center py-6 text-[var(--text-muted)]">No patients match this filter.</td></tr>
            )}
          </tbody>
        </DataTable>
      </Section>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   METHODOLOGY BADGE
   ═══════════════════════════════════════════════════════════════════════════ */

function MethodologyBadge({ text, label = "100% Gazette Data", warn = false }: { text: string; label?: string; warn?: boolean }) {
  const color = warn ? "#F59E0B" : theme.accent;
  const colorLight = warn ? "rgba(245, 158, 11, 0.15)" : theme.accentAlpha(0.06);
  const borderColor = warn ? "rgba(245, 158, 11, 0.3)" : theme.accentAlpha(0.2);
  const separatorColor = warn ? "rgba(245, 158, 11, 0.4)" : theme.accentAlpha(0.35);
  return (
    <div
      className="rounded-lg px-3 py-2 text-xs leading-relaxed"
      style={{
        background: colorLight,
        border: `1px solid ${borderColor}`,
        color: theme.textMuted,
      }}
    >
      <span className="font-bold uppercase tracking-wider" style={{ color }}>
        {label}
      </span>
      <span className="mx-1.5" style={{ color: separatorColor }}>|</span>
      {text}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   SHARED UI COMPONENTS
   ═══════════════════════════════════════════════════════════════════════════ */

/* ═══════════════════════════════════════════════════════════════════════════
   COMPLIANCE ALERTS (Consolidated Sub-Tab Wrapper)
   ═══════════════════════════════════════════════════════════════════════════ */

type AlertSubId = "exemptions" | "surcharge" | "copay_rates";

const ALERT_SUBS: { id: AlertSubId; label: string; Icon: typeof ShieldCheck }[] = [
  { id: "exemptions", label: "Copay Exemptions", Icon: ShieldCheck },
  { id: "surcharge", label: "Surcharge Compliance", Icon: ShieldAlert },
  { id: "copay_rates", label: "Copay Rate Compliance", Icon: ChartColumnBig },
];

const ALERT_CATEGORY_LABELS: Record<PatientAlertsCategory, string> = {
  exemptions: "Copay Exemptions",
  surcharge: "Surcharge Compliance",
  copay_rates: "Copay Rate Compliance",
};

function ComplianceAlerts() {
  const [activeSub, setActiveSub] = useState<AlertSubId>("exemptions");
  const [status, setStatus] = useState<PatientAlertsStatus>("all");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [alertsData, setAlertsData] = useState<PatientAlertsResponse | null>(null);
  const [alertsLoading, setAlertsLoading] = useState(true);
  const [alertsError, setAlertsError] = useState<Error | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const requestSeqRef = useRef(0);

  const handleCategoryChange = (nextCategory: AlertSubId) => {
    setActiveSub(nextCategory);
    setStatus("all");
    setSearch("");
    setPage(1);
  };

  const handleStatusChange = (nextStatus: PatientAlertsStatus) => {
    setStatus(nextStatus);
    setPage(1);
  };

  const handleSearchChange = (nextSearch: string) => {
    setSearch(nextSearch);
    setPage(1);
  };

  const normalizedSearch = search.trim();

  useEffect(() => {
    const controller = new AbortController();
    const requestSeq = requestSeqRef.current + 1;
    requestSeqRef.current = requestSeq;
    abortRef.current = controller;

    const query = buildPatientAlertsQuery({
      category: activeSub,
      status,
      search: normalizedSearch,
      page,
    });

    async function load() {
      try {
        setAlertsLoading(true);
        setAlertsError(null);
        setAlertsData(null);
        const response = await getPatientAlerts(query, { signal: controller.signal });
        if (!controller.signal.aborted && requestSeqRef.current === requestSeq) {
          setAlertsData(response);
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        if (requestSeqRef.current === requestSeq) {
          setAlertsError(err instanceof Error ? err : new Error("Failed to load patient alerts"));
        }
      } finally {
        if (requestSeqRef.current === requestSeq) {
          setAlertsLoading(false);
          if (abortRef.current === controller) {
            abortRef.current = null;
          }
        }
      }
    }

    load();
    return () => {
      controller.abort();
    };
  }, [activeSub, status, normalizedSearch, page]);

  const currentData = alertsData;
  const currentLoading = alertsLoading && !currentData;
  const alertsErrorPresentation = alertsError ? getAlertsErrorPresentation(alertsError) : null;

  return (
    <div className="space-y-4">
      <TabsRoot
        value={activeSub}
        onValueChange={(value) => handleCategoryChange(value as AlertSubId)}
        className="gap-0"
      >
        <TabsList density="compact" aria-label="Compliance alert categories">
          {ALERT_SUBS.map((sub) => (
            <TabsTrigger
              key={sub.id}
              value={sub.id}
              density="compact"
              leading={<sub.Icon className="h-4 w-4 shrink-0" strokeWidth={2} aria-hidden="true" />}
            >
              {sub.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </TabsRoot>

      <AlertQueryBar
        category={activeSub}
        status={status}
        search={search}
        loading={currentLoading}
        pagination={currentData?.pagination ?? null}
        onStatusChange={handleStatusChange}
        onSearchChange={handleSearchChange}
        onPageChange={setPage}
      />

      {alertsError && (
        <Surface
          variant="base"
          padding="md"
          className="border-[color-mix(in_srgb,var(--danger)_30%,transparent)] bg-[color-mix(in_srgb,var(--danger)_4%,transparent)]"
        >
          <Chip variant="danger" className="mb-2">
            Alert load failed
          </Chip>
          <p className="text-sm font-medium text-[var(--danger)]">
            {alertsErrorPresentation?.title}
          </p>
          <p className="mt-1 text-xs text-[var(--text-muted)]">
            {alertsErrorPresentation?.hint}
          </p>
        </Surface>
      )}

      {activeSub === "exemptions" && <CopayExemptionAlerts data={currentData} loading={currentLoading} />}
      {activeSub === "surcharge" && <SurchargeComplianceAlerts data={currentData} loading={currentLoading} />}
      {activeSub === "copay_rates" && <CopayRateAlerts data={currentData} loading={currentLoading} />}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   SECTION F: REVENUE RECOVERY DASHBOARD (Cohort)
   ═══════════════════════════════════════════════════════════════════════════ */

function RevenueRecoveryDashboard() {
  const [data, setData] = useState<CohortRecoverySummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Also fetch optimization summary for DRG Unbundling + Drug Discounts
  const [optData, setOptData] = useState<OptimizationSummary | null>(null);
  const [optLoading, setOptLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      try {
        setLoading(true);
        setError(null);
        const result = await getRevenueRecovery({ signal: controller.signal });
        if (!controller.signal.aborted) setData(result);
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setError(err instanceof Error ? err.message : "Failed to load revenue recovery");
      } finally {
        setLoading(false);
      }
    })();
    // Fetch optimization summary in parallel
    (async () => {
      try {
        setOptLoading(true);
        const result = await getOptimizationSummary({ signal: controller.signal });
        if (!controller.signal.aborted) setOptData(result);
      } catch {
        // Non-critical — silently skip
      } finally {
        setOptLoading(false);
      }
    })();
    return () => { controller.abort(); };
  }, []);

  if (loading) {
    return (
      <Surface variant="base" padding="lg" className="text-center">
        <p className="animate-pulse text-sm text-[var(--text-muted)]">Loading revenue recovery data...</p>
      </Surface>
    );
  }

  if (error) {
    return (
      <Surface
        variant="base"
        padding="lg"
        className="border-[color-mix(in_srgb,var(--danger)_30%,transparent)] bg-[color-mix(in_srgb,var(--danger)_4%,transparent)]"
      >
        <Chip variant="danger" className="mb-2">
          Revenue recovery unavailable
        </Chip>
        <p className="text-sm font-medium text-[var(--danger)]">{error}</p>
        <p className="mt-1 text-xs text-[var(--text-muted)]">
          Billing reports require the full pipeline. Start the API with <code>python -m uvicorn src.api:app</code>.
        </p>
      </Surface>
    );
  }

  if (!data || data.n_patients === 0) {
    return (
      <Surface variant="base" padding="lg" className="text-center">
        <p className="text-sm text-[var(--text-muted)]">No billing data available.</p>
      </Surface>
    );
  }

  const recoveryExact = isExactOutput(data);
  const recoveryPartial = data.exactness_status === "partial_exact";
  const hasRecoveryBreakdown = recoveryExact || recoveryPartial;
  const categoryData = Object.entries(data.savings_by_category || {})
    .filter(([, v]) => hasRecoveryBreakdown && v > 0)
    .map(([key, value]) => ({ name: fmtLabel(key), value: Math.round(value) }));

  const priorityData = Object.entries(hasRecoveryBreakdown ? (data.priority_distribution || {}) : {})
    .map(([key, value]) => ({ name: fmtPriorityLabel(key), value }));

  const priorityColors: Record<string, string> = { High: "#B91C1C", Medium: "#B45309", Low: theme.accent };

  return (
    <div className="space-y-5">
      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {[
          {
            label: recoveryPartial ? "Partial rule-calculated total" : "Rule-calculated total",
            value: fmtTRYOrUnavailable(hasRecoveryBreakdown ? data.grand_total_recoverable : null),
            accent: true,
          },
          { label: "Lab Savings", value: fmtTRYOrUnavailable(hasRecoveryBreakdown ? data.total_lab_savings : null) },
          { label: "Drug Savings", value: fmtTRYOrUnavailable(hasRecoveryBreakdown ? data.total_drug_savings : null) },
          { label: "Copay Savings", value: fmtTRYOrUnavailable(hasRecoveryBreakdown ? data.total_copay_savings : null) },
          { label: "Strategy Savings", value: fmtTRYOrUnavailable(hasRecoveryBreakdown ? data.total_strategy_savings : null) },
          { label: "Patients with Actions", value: fmtNum(data.n_patients) },
        ].map((kpi, i) => (
          <Surface
            key={i}
            variant="base"
            padding="md"
            style={kpi.accent ? { borderColor: `${ACCENT}40`, background: `${ACCENT}08` } : {}}
          >
            <Stat label={kpi.label} value={kpi.value} display={kpi.accent ? "gold" : "default"} />
          </Surface>
        ))}
      </div>
      {recoveryPartial ? (
        <MethodologyBadge
          warn
          label="Partial Exact"
          text={getUnavailableMessage(
            data,
            "Revenue recovery contains exact category-level findings, but aggregate totals are mixed because some billing sections still require exact inputs.",
          )}
        />
      ) : !recoveryExact && (
        <UnavailableBadge
          text={getUnavailableMessage(
            data,
            "Revenue recovery totals remain unavailable until every billing section is exact.",
          )}
        />
      )}

      {/* Savings Breakdown + Priority Distribution */}
      {hasRecoveryBreakdown && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Donut Chart */}
          {categoryData.length > 0 && (
          <Surface variant="base" padding="lg">
            <Eyebrow tone="gold" as="h3" className="mb-3">Savings by Category</Eyebrow>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={categoryData} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={50} outerRadius={80}>
                  {categoryData.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(val) => fmtTRY(Number(val))} />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex flex-wrap gap-3 mt-2 justify-center">
              {categoryData.map((d, i) => (
                <div key={i} className="flex items-center gap-1.5 text-xs">
                  <span className="w-2.5 h-2.5 rounded-full" style={{ background: PIE_COLORS[i % PIE_COLORS.length] }} />
                  <span className="text-[var(--text-muted)]">{d.name}</span>
                </div>
              ))}
            </div>
          </Surface>
          )}

        {/* Priority Distribution */}
          <Surface variant="base" padding="lg">
            <Eyebrow tone="gold" as="h3" className="mb-3">Priority Distribution</Eyebrow>
            <div className="space-y-3 mt-4">
              {priorityData.map((pd, i) => {
                const total = priorityData.reduce((s, p) => s + p.value, 0);
                const pct = total > 0 ? Math.round((pd.value / total) * 100) : 0;
                return (
                  <div key={i}>
                    <div className="flex justify-between text-xs mb-1">
                        <span className="font-semibold" style={{ color: priorityColors[pd.name] || theme.textMuted }}>{pd.name}</span>
                        <span className="text-[var(--text-muted)]">{fmtNum(pd.value)} patients ({fmtPct(pct / 100, 0)})</span>
                    </div>
                    <div className="w-full h-2 rounded-full" style={{ background: theme.accentAlpha(0.08) }}>
                      <div className="h-2 rounded-full" style={{ width: `${pct}%`, background: priorityColors[pd.name] || ACCENT }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </Surface>
        </div>
      )}

      {/* Top Patients Table */}
      {hasRecoveryBreakdown && (data.top_patients?.length ?? 0) > 0 && (
        <Surface variant="base" padding="lg">
          <Eyebrow tone="gold" as="h3" className="mb-3">Top-10 Highest-Impact Patients</Eyebrow>
          <DataTable minWidth={640} className="text-sm">
            <thead>
              <tr>
                <th>Patient ID</th>
                <th className="num-col">Rule-calculated</th>
                <th>Priority</th>
                <th className="num-col">Actions</th>
                <th>Top Type</th>
              </tr>
            </thead>
            <tbody>
              {data.top_patients.map((p, i) => (
                <tr key={i}>
                  <td className="font-mono text-xs">
                    <Link href={buildSutBillingHref(p.patient_id)} className="patient-id-link" style={{ color: ACCENT }}>
                      {p.patient_id}
                    </Link>
                  </td>
                  <td className="num-col font-semibold text-[var(--text-primary)]">{fmtTRY(p.total_recoverable_try)}</td>
                  <td>
                    <AlertBadge label={fmtPriorityLabel(p.priority)} color={priorityColors[fmtPriorityLabel(p.priority)] || theme.textMuted} />
                  </td>
                  <td className="num-col text-[var(--text-muted)]">{fmtNum(p.action_count)}</td>
                  <td className="text-xs text-[var(--text-muted)]">{fmtLabel(p.top_action_type)}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        </Surface>
      )}

      {/* Search Any Patient */}
      <Surface variant="base" padding="lg">
        <Eyebrow tone="gold" as="h3" className="mb-3">Look Up Any Patient</Eyebrow>
        <p className="mb-3 text-xs text-[var(--text-muted)]">
          Search for any patient to view their individual billing report.
        </p>
        <div style={{ maxWidth: 400 }}>
          <PatientSearch
            selectedPatientId={null}
            onSelect={(pid) => {
              window.location.href = buildSutBillingHref(pid);
            }}
            id="revenue-patient-search"
            placeholder="Search patient ID for billing report..."
            searchFn={searchSutPatients}
          />
        </div>
      </Surface>

      {/* Methodology Badge */}
      <div className="text-xs text-center py-2" style={{ color: "#A1A1AA" }}>
        {recoveryExact
          ? "Normative analysis based on official SUT gazette rule references (EK-1A, EK-2B, EK-2C, EK-4A)"
          : recoveryPartial
          ? "Partial-exact recovery review: exact category-level savings are shown while incomplete billing sections remain explicit required-input gaps."
          : "Mixed exactness detected: recovery review totals stay unavailable until every billing section is exact."}
      </div>

      {/* ── DRG Unbundling (merged from SUT Analytics) ── */}
      {!optLoading && optData && <DrgUnbundlingInline data={optData} />}

      {/* ── Drug Discounts (merged from SUT Analytics) ── */}
      {!optLoading && optData && <DrugDiscountInline data={optData} />}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   DRG UNBUNDLING (merged from SUT Analytics)
   ═══════════════════════════════════════════════════════════════════════════ */

function DrgUnbundlingInline({ data }: { data: OptimizationSummary }) {
  const drg = data.drg_unbundling;
  if (!drg) return null;
  const isUnavailable = !isExactOutput(drg);

  return (
    <>
      {/* Section Divider */}
      <div className="flex items-center gap-3 pt-2">
        <div className="h-px flex-1" style={{ background: theme.accentAlpha(0.15) }} />
        <span className="text-xs font-bold uppercase tracking-widest" style={{ color: ACCENT }}>
          DRG Unbundling Risk
        </span>
        <div className="h-px flex-1" style={{ background: theme.accentAlpha(0.15) }} />
      </div>

      <UnavailableBadge
        text={getUnavailableMessage(
          drg,
          "DRG unbundling risk is unavailable until exact itemized billed procedure lines and package eligibility context are present in the SUT claim inputs.",
        )}
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard label="Patients in Cohort" value={drg.n_patients_checked !== null ? fmtNum(drg.n_patients_checked) : "Unavailable"} />
        <KpiCard label="Exact Risk Status" value={isUnavailable ? "Unavailable" : fmtNumOrUnavailable(drg.n_patients_with_risk)} valueColor="#B91C1C" sub="Exact-only results" />
        <KpiCard label="Potential Savings" value={isUnavailable ? "Unavailable" : fmtTRY2OrUnavailable(drg.total_potential_savings)} valueColor="#B45309" sub="Needs exact claim lines" />
        <KpiCard label="Risky Chapters" value={isUnavailable ? "Unavailable" : fmtNum(drg.top_risky_chapters.length)} sub="Requires dated package context" />
      </div>
    </>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   DRUG DISCOUNT TIERS (merged from SUT Analytics)
   ═══════════════════════════════════════════════════════════════════════════ */

function DrugDiscountInline({ data }: { data: OptimizationSummary }) {
  const drug = data.drug_discount_validation;
  if (!drug) return null;
  const isUnavailable = !isExactOutput(drug);

  return (
    <>
      {/* Section Divider */}
      <div className="flex items-center gap-3 pt-2">
        <div className="h-px flex-1" style={{ background: theme.accentAlpha(0.15) }} />
        <span className="text-xs font-bold uppercase tracking-widest" style={{ color: ACCENT }}>
          Drug Discount Audit (EK-4A)
        </span>
        <div className="h-px flex-1" style={{ background: theme.accentAlpha(0.15) }} />
      </div>

      <UnavailableBadge
        text={getUnavailableMessage(
          drug,
          "Drug discount validation is unavailable until exact dispensed-drug claim lines and billed drug amounts are present in the SUT claim inputs.",
        )}
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard label="Validation State" value={isUnavailable ? "Unavailable" : fmtNumOrUnavailable(drug.n_active_drugs)} sub="Catalog-only reference removed from active findings" />
        <KpiCard label="Drug Claims" value="Missing" valueColor="#B45309" sub="Dispensed line items required" />
        <KpiCard label="Billed Amounts" value="Missing" valueColor="#B45309" sub="Actual claim amounts required" />
        <KpiCard label="Patient Findings" value="Unavailable" sub="Exact claim inputs required" />
      </div>
    </>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   MAIN COMPONENT — SUT Optimization Engine
   ═══════════════════════════════════════════════════════════════════════════ */

export default function SUTOptimizer() {
  const [activeSection, setActiveSection] = useState<SectionId>("alerts");
  const { getRevealProps } = useStaggeredReveal(5, { baseDelayMs: 40, stepMs: 140, threshold: 0.15 });

  const r0 = getRevealProps(0);
  const r1 = getRevealProps(1);
  const r2 = getRevealProps(2);

  // Look up description for active section
  const activeDescription = SECTIONS.find((s) => s.id === activeSection)?.description ?? "";

  return (
    <div className="relative space-y-6">
      {/* (tab intro removed — description now in tab button) */}

      {/* Section Nav */}
      <div
        className={`${r0.staggerClass}`}
        style={r0.staggerStyle}
        {...r0.staggerAttrs}
      >
        <TabsRoot
          value={activeSection}
          onValueChange={(value) => setActiveSection(value as SectionId)}
          className="gap-0"
        >
          <TabsList density="comfortable" aria-label="Optimizer sections">
            {SECTIONS.map((sec) => (
              <TabsTrigger
                key={sec.id}
                value={sec.id}
                leading={<sec.Icon className="h-4 w-4 shrink-0" strokeWidth={2} aria-hidden="true" />}
              >
                {sec.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </TabsRoot>
      </div>

      {/* Section Description */}
      <p
        className={`text-sm leading-snug text-[var(--text-secondary)] ${r1.staggerClass}`}
        style={r1.staggerStyle}
        {...r1.staggerAttrs}
      >
        {activeDescription}
      </p>

      {/* Active Section */}
      <div className={r2.staggerClass} style={r2.staggerStyle} {...r2.staggerAttrs}>
        {activeSection === "alerts" && <ComplianceAlerts />}
        {activeSection === "revenue" && <RevenueRecoveryDashboard />}
      </div>
    </div>
  );
}
