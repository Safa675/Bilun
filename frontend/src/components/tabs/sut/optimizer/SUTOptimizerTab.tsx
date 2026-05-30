"use client";

import { useState, useEffect, useRef, type ChangeEvent, type FormEvent } from "react";
import Link from "next/link";
import {
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
} from "@/lib/api/sut";
import { formatExemptionCategory } from "@/lib/copayExemption";
import { ExemptionBasisChips } from "@/components/sut/ExemptionBasisChips";
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
import {
  buildSutBillingHref,
} from "@/lib/constants";
import { useCohortFilter } from "@/hooks/useCohortFilter";
import { SutAlertTableSkeleton } from "@/components/skeletons/SutSkeletons";
import { getUnavailableMessage, isExactOutput } from "@/lib/sutExactness";
import {
  getSutActionLabel,
  getSutAlertBadgeLabel,
} from "@/lib/sutLabels";
import { useT } from "@/lib/i18n/useTranslations";
import { translate } from "@/lib/i18n/translate";
import { getModuleLocale } from "@/lib/i18n/localeModule";
import enMessages from "@/messages/en/index";
import trMessages from "@/messages/tr/index";
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

function optimizerT(
  key: string,
  params?: Record<string, string | number | undefined | null>,
): string {
  const messages = getModuleLocale() === "tr" ? trMessages : enMessages;
  return translate(messages, key, params);
}

function getCategoryLabel(category: PatientAlertsCategory): string {
  return optimizerT(`optimizer.categories.${category}`);
}

interface AlertQueryBarProps {
  category: PatientAlertsCategory;
  status: PatientAlertsStatus;
  loading: boolean;
  pagination: PatientAlertsResponse["pagination"] | null;
  onStatusChange: (status: PatientAlertsStatus) => void;
  onPageChange: (page: number) => void;
}

function AlertQueryBar({
  category,
  status,
  loading,
  pagination,
  onStatusChange,
  onPageChange,
}: AlertQueryBarProps) {
  const t = useT();
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
          <Eyebrow as="div">{t("optimizer.filters.statusEyebrow")}</Eyebrow>
          <TabsRoot
            value={status}
            onValueChange={(value) => onStatusChange(value as PatientAlertsStatus)}
            className="gap-0"
          >
            <TabsList density="compact" aria-label={t("optimizer.filters.statusAria")}>
              {getAlertStatusOptions(category).map((option) => (
                <TabsTrigger key={option} value={option} density="compact">
                  {getAlertStatusLabel(option)}
                </TabsTrigger>
              ))}
            </TabsList>
          </TabsRoot>
        </div>

        <div className="space-y-2 lg:text-right">
          <Eyebrow as="div" className="lg:text-right">{t("optimizer.pagination.eyebrow")}</Eyebrow>
          <div className="flex flex-col gap-2 sm:items-start lg:items-end">
            <div className="flex flex-wrap items-center gap-2 lg:justify-end">
              <button
                type="button"
                className="rounded-[var(--r-md)] border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-semibold text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)] disabled:opacity-50"
                onClick={() => onPageChange(Math.max(currentPage - 1, 1))}
                disabled={!hasPrev || loading}
              >
                {t("optimizer.pagination.prev")}
              </button>
              <span className="text-xs font-semibold text-[var(--text-secondary)]">
                {t("optimizer.pagination.pageOf", { current: fmtNum(currentPage), total: fmtNum(totalPages) })}
              </span>
              <button
                type="button"
                className="rounded-[var(--r-md)] border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-semibold text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)] disabled:opacity-50"
                onClick={() => onPageChange(currentPage + 1)}
                disabled={!hasNext || loading}
              >
                {t("optimizer.pagination.next")}
              </button>
            </div>

            <form className="flex flex-wrap items-center gap-2 lg:justify-end" onSubmit={handlePageJumpSubmit}>
              <label
                htmlFor={`${category}-page-jump`}
                className="text-[0.68rem] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]"
              >
                {t("optimizer.pagination.jumpToPage")}
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
                {t("optimizer.pagination.go")}
              </button>
            </form>
          </div>
        </div>
      </div>
      <p className="mt-3 text-xs text-[var(--text-secondary)]">
        {totalMatching > 0
          ? t("optimizer.pagination.displayingPage", {
              category: getCategoryLabel(category),
              total: fmtNum(totalMatching),
            })
          : t("optimizer.pagination.noMatching")}
      </p>
    </Surface>
  );
}

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
  if (!action) return <span className="text-xs" style={{ color: "#A1A1AA" }}>{getSutActionLabel("noActionNeeded")}</span>;
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
        hint: optimizerT("optimizer.errors.networkHint"),
      };
    }

    const backendDetail = error.detail ?? error.message;
    if (
      error.status === 503
      && /analytics build|canonical build|pipeline/i.test(backendDetail)
    ) {
      return {
        title: optimizerT("optimizer.errors.alertsTemporarilyUnavailable"),
        hint: backendDetail,
      };
    }

    return {
      title: backendDetail,
      hint: optimizerT("optimizer.errors.loadAlertsBackend"),
    };
  }

  return {
    title: error.message || optimizerT("optimizer.errors.loadAlerts"),
    hint: optimizerT("optimizer.errors.loadAlertsUnexpected"),
  };
}

function UnavailableBadge({ text }: { text: string }) {
  return <MethodologyBadge warn label={optimizerT("optimizer.unavailable.badge")} text={text} />;
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

function CopayExemptionAlerts({
  data,
  loading,
  cohortCopay,
}: {
  data: PatientAlertsResponse | null;
  loading: boolean;
  cohortCopay: OptimizationSummary["copay_exemptions"] | null;
}) {
  const t = useT();
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
  const ek1aExemptCount =
    cohortCopay?.n_exempt_ek1a_patients ?? summary.n_exempt_patients;
  const anyGroundExemptCount = summary.n_exempt_patients;
  const statusOnlyCount = cohortCopay?.n_exempt_status_only_patients;

  return (
    <div className="space-y-5">
      <MethodologyBadge
        text={
          cohortCopay?.exemption_by_category?.length
            ? t("optimizer.methodology.copayComposableWithProfiles", {
                ek1aCount: regulatory.ek1a_exemption_count,
              })
            : t("optimizer.methodology.copayEk1aOnly", {
                ek1aCount: regulatory.ek1a_exemption_count,
              })
        }
      />

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3">
        <KpiCard label={t("optimizer.kpis.totalPatients")} value={fmtNum(summary.n_total_patients)} />
        <KpiCard
          label={t("optimizer.kpis.exemptAnyGround")}
          value={fmtNum(anyGroundExemptCount)}
          valueColor={theme.accent}
          sub={t("optimizer.kpis.exemptAnyGroundSub")}
        />
        <KpiCard
          label={t("optimizer.kpis.ek1aExempt")}
          value={fmtNum(ek1aExemptCount)}
          valueColor={ACCENT}
          sub={t("optimizer.kpis.ek1aExemptSub")}
        />
        {typeof statusOnlyCount === "number" && (
          <KpiCard
            label={t("optimizer.kpis.statusVisitOnly")}
            value={fmtNum(statusOnlyCount)}
            sub={t("optimizer.kpis.statusVisitOnlySub")}
          />
        )}
        <KpiCard label={t("optimizer.kpis.exemptionRate")} value={fmtPct(exemptRate)} valueColor={ACCENT} />
        <KpiCard
          label={t("optimizer.kpis.nonExempt")}
          value={fmtNum(summary.n_total_patients - summary.n_exempt_patients)}
          sub={t("optimizer.kpis.nonExemptSub")}
        />
      </div>

      {cohortCopay?.exemption_by_category && cohortCopay.exemption_by_category.length > 0 && (
        <Surface variant="soft" padding="md" className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--gold)]">
            {t("optimizer.sections.exemptionByCategory")}
          </p>
          <div className="flex flex-wrap gap-2">
            {cohortCopay.exemption_by_category.map((row) => (
              <Chip key={row.category} variant="outline" className="text-xs">
                {formatExemptionCategory(row.category)} ({fmtNum(row.count)})
              </Chip>
            ))}
          </div>
        </Surface>
      )}

      <Section
        title={t("optimizer.sections.patientAlerts")}
        trailing={<Chip variant="outline">{getAlertStatusLabel(data.query.status)}</Chip>}
        padding="lg"
        className="[&_h2]:text-sm [&_h2]:font-semibold [&_h2]:uppercase [&_h2]:tracking-wider [&_h2]:text-[var(--gold)]"
      >
        <p className="mb-2 text-xs text-[var(--text-muted)]">
          {t("optimizer.tables.showingRange", {
            start: fmtNum(rangeStart),
            end: fmtNum(rangeEnd),
            total: fmtNum(totalMatching),
            page: fmtNum(currentPage),
            totalPages: fmtNum(totalPages),
          })}
        </p>

        <DataTable minWidth={860} className="max-h-[420px] overflow-y-auto text-xs">
          <thead>
            <tr>
              <th>{t("optimizer.tables.patientId")}</th>
              <th className="text-center">{t("optimizer.tables.status")}</th>
              <th>{t("optimizer.tables.exemptionBasis")}</th>
              <th className="num-col">{t("optimizer.tables.ek1aDx")}</th>
              <th>{t("optimizer.tables.topEk1aDiagnosis")}</th>
              <th>{t("optimizer.tables.recommendedAction")}</th>
            </tr>
          </thead>
          <tbody>
            {patients.map((p) => (
              <tr key={p.patient_id}>
                <td className="font-mono" style={{ color: ACCENT }}>{p.patient_id}</td>
                <td className="text-center">
                  {p.copay_exemption.exempt
                    ? <AlertBadge label={getSutAlertBadgeLabel("exempt")} color={theme.accent} />
                    : <AlertBadge label={getSutAlertBadgeLabel("notExempt")} color="#A1A1AA" />
                  }
                </td>
                <td>
                  {p.copay_exemption.exempt ? (
                    <ExemptionBasisChips copay={p.copay_exemption} max={3} />
                  ) : (
                    <span className="text-[var(--text-muted)]">{t("optimizer.emDash")}</span>
                  )}
                </td>
                <td className="num-col">{fmtNum(p.copay_exemption.n_qualifying)}</td>
                <td className="truncate max-w-[200px]" title={p.copay_exemption.qualifying_diagnoses[0]?.disease}>
                  {p.copay_exemption.qualifying_diagnoses[0]?.disease ?? t("optimizer.emDash")}
                </td>
                <td><ActionBadge action={p.copay_exemption.action} /></td>
              </tr>
            ))}
            {patients.length === 0 && (
              <tr><td colSpan={6} className="text-center py-6 text-[var(--text-muted)]">{t("optimizer.emptyStates.noPatientsMatchFilter")}</td></tr>
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
  const t = useT();
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
    t("optimizer.unavailable.surchargeCompliance"),
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
        <MethodologyBadge text={t("optimizer.methodology.surchargeExact")} />
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard label={t("optimizer.kpis.totalPatients")} value={fmtNum(summary.n_total_patients)} />
        <KpiCard
          label={isUnavailable ? t("optimizer.kpis.unavailablePatients") : t("optimizer.kpis.clearPatients")}
          value={
            isUnavailable
              ? fmtNum(summary.n_patients_with_surcharge_unavailable ?? summary.n_total_patients)
              : fmtNum(summary.n_total_patients - (summary.n_patients_with_surcharge_flags ?? 0))
          }
          valueColor="#B45309"
          sub={isUnavailable ? t("optimizer.kpis.needExactClaimLines") : t("optimizer.kpis.noSurchargeFlags")}
        />
        <KpiCard
          label={t("optimizer.kpis.patientsFlagged")}
          value={isUnavailable ? t("optimizer.unavailable.badge") : fmtNum(summary.n_patients_with_surcharge_flags ?? 0)}
          valueColor="#B45309"
          sub={isUnavailable ? t("optimizer.kpis.noExactSurchargeFindings") : t("optimizer.kpis.exactClaimLineFindings")}
        />
        <KpiCard
          label={t("optimizer.kpis.totalFlags")}
          value={isUnavailable ? t("optimizer.unavailable.badge") : fmtNum(summary.total_surcharge_flags ?? 0)}
          valueColor="#B91C1C"
          sub={isUnavailable ? t("optimizer.kpis.countsResumeAfterInputs") : t("optimizer.kpis.exactProcedureFlags")}
        />
      </div>

      <Section
        title={t("optimizer.sections.patientAlerts")}
        trailing={<Chip variant="outline">{getAlertStatusLabel(data.query.status)}</Chip>}
        padding="lg"
        className="[&_h2]:text-sm [&_h2]:font-semibold [&_h2]:uppercase [&_h2]:tracking-wider [&_h2]:text-[var(--gold)]"
      >
        <p className="mb-2 text-xs text-[var(--text-muted)]">
          {t("optimizer.tables.showingRange", {
            start: fmtNum(rangeStart),
            end: fmtNum(rangeEnd),
            total: fmtNum(totalMatching),
            page: fmtNum(currentPage),
            totalPages: fmtNum(totalPages),
          })}
        </p>

        <DataTable minWidth={720} className="max-h-[420px] overflow-y-auto text-xs">
          <thead>
            <tr>
              <th>{t("optimizer.tables.patientId")}</th>
              <th className="text-center">{t("optimizer.tables.status")}</th>
              <th className="num-col">{t("optimizer.tables.noSurchargeRules")}</th>
              <th>{t("optimizer.tables.topProcedure")}</th>
              <th>{t("optimizer.tables.recommendedAction")}</th>
            </tr>
          </thead>
          <tbody>
            {patients.map((p) => (
              <tr key={p.patient_id}>
                <td className="font-mono" style={{ color: ACCENT }}>{p.patient_id}</td>
                <td className="text-center">
                  {!isExactOutput(p.surcharge_exposure)
                    ? <AlertBadge label={getSutAlertBadgeLabel("unavailable")} color={theme.textMuted} />
                    : (p.surcharge_exposure.n_applicable ?? 0) > 0
                    ? <AlertBadge label={getSutAlertBadgeLabel("flagged")} color="#B45309" />
                    : <AlertBadge label={getSutAlertBadgeLabel("clear")} color={theme.accent} />
                  }
                </td>
                <td className="num-col font-bold" style={{ color: isExactOutput(p.surcharge_exposure) && (p.surcharge_exposure.n_applicable ?? 0) > 0 ? "#B45309" : "#A1A1AA" }}>
                  {p.surcharge_exposure.n_applicable !== null ? fmtNum(p.surcharge_exposure.n_applicable) : t("optimizer.emDash")}
                </td>
                <td className="truncate max-w-[200px]" title={p.surcharge_exposure.top_rules[0]?.name}>
                  {p.surcharge_exposure.top_rules[0]?.name ?? (isExactOutput(p.surcharge_exposure) ? t("optimizer.emDash") : t("optimizer.unavailable.exactProcedureCodesRequired"))}
                </td>
                <td>
                  {isExactOutput(p.surcharge_exposure)
                    ? <ActionBadge action={p.surcharge_exposure.action} />
                    : <span className="text-xs text-[var(--text-muted)]">{t("optimizer.unavailable.badge")}</span>
                  }
                </td>
              </tr>
            ))}
            {patients.length === 0 && (
              <tr><td colSpan={5} className="text-center py-6 text-[var(--text-muted)]">{t("optimizer.emptyStates.noPatientsMatchFilter")}</td></tr>
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
  const t = useT();
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
    t("optimizer.unavailable.copayRateCompliance"),
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
        <MethodologyBadge text={t("optimizer.methodology.copayRateExact")} />
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard label={t("optimizer.kpis.totalPatients")} value={fmtNum(summary.n_total_patients)} />
        <KpiCard
          label={isUnavailable ? t("optimizer.kpis.unavailablePatients") : t("optimizer.kpis.clearPatients")}
          value={
            isUnavailable
              ? fmtNum(summary.n_patients_with_copay_rate_unavailable ?? summary.n_total_patients)
              : fmtNum(summary.n_total_patients - (summary.n_patients_with_copay_rate_flags ?? 0))
          }
          valueColor="#B45309"
          sub={isUnavailable ? t("optimizer.kpis.needExactClaimLines") : t("optimizer.kpis.noCopayRateFlags")}
        />
        <KpiCard
          label={t("optimizer.kpis.patientsFlagged")}
          value={isUnavailable ? t("optimizer.unavailable.badge") : fmtNum(summary.n_patients_with_copay_rate_flags ?? 0)}
          valueColor="#B45309"
          sub={isUnavailable ? t("optimizer.kpis.noExactRateFindings") : t("optimizer.kpis.exactClaimLineFindings")}
        />
        <KpiCard
          label={t("optimizer.kpis.totalFlags")}
          value={isUnavailable ? t("optimizer.unavailable.badge") : fmtNum(summary.total_copay_rate_flags ?? 0)}
          valueColor="#B91C1C"
          sub={isUnavailable ? t("optimizer.kpis.countsResumeAfterInputs") : t("optimizer.kpis.exactProcedureFlags")}
        />
      </div>

      <Section
        title={t("optimizer.sections.patientAlerts")}
        trailing={<Chip variant="outline">{getAlertStatusLabel(data.query.status)}</Chip>}
        padding="lg"
        className="[&_h2]:text-sm [&_h2]:font-semibold [&_h2]:uppercase [&_h2]:tracking-wider [&_h2]:text-[var(--gold)]"
      >
        <p className="mb-2 text-xs text-[var(--text-muted)]">
          {t("optimizer.tables.showingRange", {
            start: fmtNum(rangeStart),
            end: fmtNum(rangeEnd),
            total: fmtNum(totalMatching),
            page: fmtNum(currentPage),
            totalPages: fmtNum(totalPages),
          })}
        </p>

        <DataTable minWidth={720} className="max-h-[420px] overflow-y-auto text-xs">
          <thead>
            <tr>
              <th>{t("optimizer.tables.patientId")}</th>
              <th className="text-center">{t("optimizer.tables.status")}</th>
              <th className="num-col">{t("optimizer.tables.rateCappedProcs")}</th>
              <th className="num-col">{t("optimizer.tables.meanRate")}</th>
              <th>{t("optimizer.tables.recommendedAction")}</th>
            </tr>
          </thead>
          <tbody>
            {patients.map((p) => (
              <tr key={p.patient_id}>
                <td className="font-mono" style={{ color: ACCENT }}>{p.patient_id}</td>
                <td className="text-center">
                  {!isExactOutput(p.copay_rate_exposure)
                    ? <AlertBadge label={getSutAlertBadgeLabel("unavailable")} color={theme.textMuted} />
                    : (p.copay_rate_exposure.n_applicable ?? 0) > 0
                    ? <AlertBadge label={getSutAlertBadgeLabel("flagged")} color="#B45309" />
                    : <AlertBadge label={getSutAlertBadgeLabel("clear")} color={theme.accent} />
                  }
                </td>
                <td className="num-col font-bold" style={{ color: isExactOutput(p.copay_rate_exposure) && (p.copay_rate_exposure.n_applicable ?? 0) > 0 ? "#B45309" : "#A1A1AA" }}>
                  {p.copay_rate_exposure.n_applicable !== null ? fmtNum(p.copay_rate_exposure.n_applicable) : t("optimizer.emDash")}
                </td>
                <td className="num-col">
                  {p.copay_rate_exposure.mean_rate !== null ? fmtPct(p.copay_rate_exposure.mean_rate / 100, 0) : t("optimizer.emDash")}
                </td>
                <td>
                  {isExactOutput(p.copay_rate_exposure)
                    ? <ActionBadge action={p.copay_rate_exposure.action} />
                    : <span className="text-xs text-[var(--text-muted)]">{t("optimizer.unavailable.badge")}</span>
                  }
                </td>
              </tr>
            ))}
            {patients.length === 0 && (
              <tr><td colSpan={5} className="text-center py-6 text-[var(--text-muted)]">{t("optimizer.emptyStates.noPatientsMatchFilter")}</td></tr>
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

function MethodologyBadge({
  text,
  label,
  warn = false,
}: {
  text: string;
  label?: string;
  warn?: boolean;
}) {
  const t = useT();
  const badgeLabel = label ?? t("optimizer.methodology.gazetteData");
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
        {badgeLabel}
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

function filterAlertsByCohort(
  data: PatientAlertsResponse | null,
  cohortPatientIds: Set<string>,
  cohortFilterActive: boolean,
): PatientAlertsResponse | null {
  if (!data || !cohortFilterActive) return data;
  const patients = data.patients.filter((patient) => cohortPatientIds.has(patient.patient_id));
  return {
    ...data,
    patients,
    pagination: {
      ...data.pagination,
      total_matching: patients.length,
      has_more: false,
      offset: 0,
    },
  };
}

function ComplianceAlerts({
  cohortPatientIds,
  cohortFilterActive,
}: {
  cohortPatientIds: Set<string>;
  cohortFilterActive: boolean;
}) {
  const t = useT();
  const [activeSub, setActiveSub] = useState<AlertSubId>("exemptions");
  const [status, setStatus] = useState<PatientAlertsStatus>("all");
  const [page, setPage] = useState(1);
  const { filter: cohortFilter } = useCohortFilter();
  const [alertsData, setAlertsData] = useState<PatientAlertsResponse | null>(null);
  const [alertsLoading, setAlertsLoading] = useState(true);
  const [alertsError, setAlertsError] = useState<Error | null>(null);
  const [cohortCopay, setCohortCopay] = useState<
    OptimizationSummary["copay_exemptions"] | null
  >(null);
  const abortRef = useRef<AbortController | null>(null);
  const requestSeqRef = useRef(0);

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      try {
        const summary = await getOptimizationSummary({ signal: controller.signal });
        if (!controller.signal.aborted) {
          setCohortCopay(summary.copay_exemptions);
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
      }
    })();
    return () => controller.abort();
  }, []);

  const handleCategoryChange = (nextCategory: AlertSubId) => {
    setActiveSub(nextCategory);
    setStatus("all");
    setPage(1);
  };

  const handleStatusChange = (nextStatus: PatientAlertsStatus) => {
    setStatus(nextStatus);
    setPage(1);
  };

  const normalizedSearch = cohortFilter.q.trim();

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
          setAlertsError(err instanceof Error ? err : new Error(optimizerT("optimizer.errors.loadAlerts")));
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

  const currentData = filterAlertsByCohort(
    alertsData,
    cohortPatientIds,
    cohortFilterActive,
  );
  const currentLoading = alertsLoading && !currentData;
  const alertsErrorPresentation = alertsError ? getAlertsErrorPresentation(alertsError) : null;

  const alertSubs = [
    { id: "exemptions" as const, label: t("optimizer.tabs.exemptions"), Icon: ShieldCheck },
    { id: "surcharge" as const, label: t("optimizer.tabs.surcharge"), Icon: ShieldAlert },
    { id: "copay_rates" as const, label: t("optimizer.tabs.copayRates"), Icon: ChartColumnBig },
  ];

  return (
    <div className="space-y-4">
      {cohortFilterActive && (
        <MethodologyBadge
          warn
          label={t("optimizer.methodology.activeFilters")}
          text={t("optimizer.methodology.cohortFilterAlertsHint")}
        />
      )}
      <TabsRoot
        value={activeSub}
        onValueChange={(value) => handleCategoryChange(value as AlertSubId)}
        className="gap-0"
      >
        <TabsList density="compact" aria-label={t("optimizer.tabs.categoriesAria")}>
          {alertSubs.map((sub) => (
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
        loading={currentLoading}
        pagination={currentData?.pagination ?? null}
        onStatusChange={handleStatusChange}
        onPageChange={setPage}
      />

      {alertsError && (
        <Surface
          variant="base"
          padding="md"
          className="border-[color-mix(in_srgb,var(--danger)_30%,transparent)] bg-[color-mix(in_srgb,var(--danger)_4%,transparent)]"
        >
          <Chip variant="danger" className="mb-2">
            {t("optimizer.errors.alertLoadFailed")}
          </Chip>
          <p className="text-sm font-medium text-[var(--danger)]">
            {alertsErrorPresentation?.title}
          </p>
          <p className="mt-1 text-xs text-[var(--text-muted)]">
            {alertsErrorPresentation?.hint}
          </p>
        </Surface>
      )}

      {activeSub === "exemptions" && (
        <CopayExemptionAlerts
          data={currentData}
          loading={currentLoading}
          cohortCopay={cohortCopay}
        />
      )}
      {activeSub === "surcharge" && <SurchargeComplianceAlerts data={currentData} loading={currentLoading} />}
      {activeSub === "copay_rates" && <CopayRateAlerts data={currentData} loading={currentLoading} />}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   SECTION F: REVENUE RECOVERY DASHBOARD (Cohort)
   ═══════════════════════════════════════════════════════════════════════════ */

function RevenueRecoveryDashboard({
  cohortPatientIds,
  cohortFilterActive,
}: {
  cohortPatientIds: Set<string>;
  cohortFilterActive: boolean;
}) {
  const t = useT();
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
        setError(err instanceof Error ? err.message : optimizerT("optimizer.errors.loadRevenueRecovery"));
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
        <p className="animate-pulse text-sm text-[var(--text-muted)]">{t("optimizer.loading.revenueRecovery")}</p>
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
          {t("optimizer.errors.revenueRecoveryUnavailable")}
        </Chip>
        <p className="text-sm font-medium text-[var(--danger)]">{error}</p>
        <p className="mt-1 text-xs text-[var(--text-muted)]">
          {t("optimizer.errors.revenueRecoveryApiHint")}
        </p>
      </Surface>
    );
  }

  if (!data || data.n_patients === 0) {
    return (
      <Surface variant="base" padding="lg" className="text-center">
        <p className="text-sm text-[var(--text-muted)]">{t("optimizer.emptyStates.noBillingData")}</p>
      </Surface>
    );
  }

  const summarySource = (data.patient_summaries?.length
    ? data.patient_summaries
    : data.top_patients ?? []
  ).filter(
    (patient) => !cohortFilterActive || cohortPatientIds.has(patient.patient_id),
  );

  const filteredGrandTotal = summarySource.reduce(
    (sum, patient) => sum + (patient.total_recoverable_try ?? 0),
    0,
  );

  const displayData = cohortFilterActive
    ? {
        ...data,
        n_patients: summarySource.length,
        grand_total_recoverable: filteredGrandTotal,
        top_patients: [...summarySource]
          .sort((a, b) => b.total_recoverable_try - a.total_recoverable_try)
          .slice(0, 10),
      }
    : data;

  if (cohortFilterActive && summarySource.length === 0) {
    return (
      <Surface variant="base" padding="lg" className="text-center">
        <p className="text-sm text-[var(--text-muted)]">{t("optimizer.emptyStates.noBillingDataInFilter")}</p>
      </Surface>
    );
  }

  const recoveryExact = isExactOutput(displayData);
  const recoveryPartial = displayData.exactness_status === "partial_exact";
  const hasRecoveryBreakdown = recoveryExact || recoveryPartial;
  const categoryData = Object.entries(displayData.savings_by_category || {})
    .filter(([, v]) => hasRecoveryBreakdown && v > 0)
    .map(([key, value]) => ({ name: fmtLabel(key), value: Math.round(value) }));

  const priorityData = Object.entries(hasRecoveryBreakdown ? (displayData.priority_distribution || {}) : {})
    .map(([key, value]) => ({ name: fmtPriorityLabel(key), value }));

  const priorityColors: Record<string, string> = { High: "#B91C1C", Medium: "#B45309", Low: theme.accent };

  return (
    <div className="space-y-5">
      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {[
          {
            label: recoveryPartial ? t("optimizer.kpis.partialRuleCalculatedTotal") : t("optimizer.kpis.ruleCalculatedTotal"),
            value: fmtTRYOrUnavailable(hasRecoveryBreakdown ? displayData.grand_total_recoverable : null),
            accent: true,
          },
          { label: t("optimizer.kpis.labSavings"), value: fmtTRYOrUnavailable(hasRecoveryBreakdown ? displayData.total_lab_savings : null) },
          { label: t("optimizer.kpis.drugSavings"), value: fmtTRYOrUnavailable(hasRecoveryBreakdown ? displayData.total_drug_savings : null) },
          { label: t("optimizer.kpis.copaySavings"), value: fmtTRYOrUnavailable(hasRecoveryBreakdown ? displayData.total_copay_savings : null) },
          { label: t("optimizer.kpis.strategySavings"), value: fmtTRYOrUnavailable(hasRecoveryBreakdown ? displayData.total_strategy_savings : null) },
          { label: t("optimizer.kpis.patientsWithActions"), value: fmtNum(displayData.n_patients) },
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
          label={t("optimizer.methodology.partialExact")}
          text={getUnavailableMessage(displayData, t("optimizer.methodology.revenuePartialExact"))}
        />
      ) : !recoveryExact && (
        <UnavailableBadge
          text={getUnavailableMessage(displayData, t("optimizer.methodology.revenueUnavailable"))}
        />
      )}

      {cohortFilterActive && (
        <MethodologyBadge
          warn
          label={t("optimizer.methodology.activeFilters")}
          text={t("optimizer.methodology.cohortFilterRevenueHint")}
        />
      )}

      {/* Savings Breakdown + Priority Distribution */}
      {hasRecoveryBreakdown && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Donut Chart */}
          {categoryData.length > 0 && (
          <Surface variant="base" padding="lg">
            <Eyebrow tone="gold" as="h3" className="mb-3">{t("optimizer.sections.savingsByCategory")}</Eyebrow>
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
            <Eyebrow tone="gold" as="h3" className="mb-3">{t("optimizer.sections.priorityDistribution")}</Eyebrow>
            <div className="space-y-3 mt-4">
              {priorityData.map((pd, i) => {
                const total = priorityData.reduce((s, p) => s + p.value, 0);
                const pct = total > 0 ? Math.round((pd.value / total) * 100) : 0;
                return (
                  <div key={i}>
                    <div className="flex justify-between text-xs mb-1">
                        <span className="font-semibold" style={{ color: priorityColors[pd.name] || theme.textMuted }}>{pd.name}</span>
                        <span className="text-[var(--text-muted)]">
                          {t("optimizer.tables.patientsWithPct", {
                            count: fmtNum(pd.value),
                            pct: fmtPct(pct / 100, 0),
                          })}
                        </span>
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
      {hasRecoveryBreakdown && (displayData.top_patients?.length ?? 0) > 0 && (
        <Surface variant="base" padding="lg">
          <Eyebrow tone="gold" as="h3" className="mb-3">
            {cohortFilterActive ? t("optimizer.sections.topPatientsFiltered") : t("optimizer.sections.topPatientsDefault")}
          </Eyebrow>
          <DataTable minWidth={640} className="text-sm">
            <thead>
              <tr>
                <th>{t("optimizer.tables.patientId")}</th>
                <th className="num-col">{t("optimizer.tables.ruleCalculated")}</th>
                <th>{t("optimizer.tables.priority")}</th>
                <th className="num-col">{t("optimizer.tables.actions")}</th>
                <th>{t("optimizer.tables.topType")}</th>
              </tr>
            </thead>
            <tbody>
              {displayData.top_patients.map((p, i) => (
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

      {/* Methodology Badge */}
      <div className="text-xs text-center py-2" style={{ color: "#A1A1AA" }}>
        {recoveryExact
          ? t("optimizer.methodology.revenueFooterExact")
          : recoveryPartial
          ? t("optimizer.methodology.revenueFooterPartial")
          : t("optimizer.methodology.revenueFooterMixed")}
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

export function DrgUnbundlingInline({ data }: { data: OptimizationSummary }) {
  const t = useT();
  const drg = data.drg_unbundling;
  if (!drg) return null;
  const isUnavailable = !isExactOutput(drg);
  const unavailableMessage = getUnavailableMessage(
    drg,
    t("optimizer.unavailable.drgUnbundling"),
  );
  const unavailableLabel = t("common.unavailable");

  return (
    <>
      {/* Section Divider */}
      <div className="flex items-center gap-3 pt-2">
        <div className="h-px flex-1" style={{ background: theme.accentAlpha(0.15) }} />
        <span className="text-xs font-bold uppercase tracking-widest" style={{ color: ACCENT }}>
          {t("optimizer.sections.drgUnbundlingRisk")}
        </span>
        <div className="h-px flex-1" style={{ background: theme.accentAlpha(0.15) }} />
      </div>

      {isUnavailable ? (
        <UnavailableBadge text={unavailableMessage} />
      ) : (
        <MethodologyBadge text={drg.methodology} />
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard
          label={t("optimizer.kpis.patientsInCohort")}
          value={drg.n_patients_checked !== null ? fmtNum(drg.n_patients_checked) : unavailableLabel}
          sub={isUnavailable ? t("optimizer.kpis.cohortSizeUntilInputs") : t("optimizer.kpis.checkedOnExactClaimLines")}
        />
        <KpiCard
          label={t("optimizer.kpis.patientsWithRisk")}
          value={isUnavailable ? unavailableLabel : fmtNumOrUnavailable(drg.n_patients_with_risk)}
          valueColor="#B91C1C"
          sub={isUnavailable ? t("optimizer.kpis.needExactClaimLines") : t("optimizer.kpis.exactUnbundlingFindings")}
        />
        <KpiCard
          label={t("optimizer.kpis.potentialSavings")}
          value={isUnavailable ? unavailableLabel : fmtTRY2OrUnavailable(drg.total_potential_savings)}
          valueColor="#B45309"
          sub={isUnavailable ? t("optimizer.kpis.amountsResumeAfterInputs") : t("optimizer.kpis.fromExactClaimLineAnalysis")}
        />
        <KpiCard
          label={t("optimizer.kpis.riskyChapters")}
          value={isUnavailable ? unavailableLabel : fmtNum(drg.top_risky_chapters.length)}
          sub={isUnavailable ? t("optimizer.kpis.requiresDatedPackageContext") : t("optimizer.kpis.icd10ChaptersWithRepeatedRisk")}
        />
      </div>
    </>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   DRUG DISCOUNT TIERS (merged from SUT Analytics)
   ═══════════════════════════════════════════════════════════════════════════ */

export function DrugDiscountInline({ data }: { data: OptimizationSummary }) {
  const t = useT();
  const drug = data.drug_discount_validation;
  if (!drug) return null;
  const isUnavailable = !isExactOutput(drug);
  const unavailableMessage = getUnavailableMessage(
    drug,
    t("optimizer.unavailable.drugDiscount"),
  );
  const tierMismatches = drug.n_tier_mismatches ?? null;
  const unavailableLabel = t("common.unavailable");

  return (
    <>
      {/* Section Divider */}
      <div className="flex items-center gap-3 pt-2">
        <div className="h-px flex-1" style={{ background: theme.accentAlpha(0.15) }} />
        <span className="text-xs font-bold uppercase tracking-widest" style={{ color: ACCENT }}>
          {t("optimizer.sections.drugDiscountAudit")}
        </span>
        <div className="h-px flex-1" style={{ background: theme.accentAlpha(0.15) }} />
      </div>

      {isUnavailable ? (
        <UnavailableBadge text={unavailableMessage} />
      ) : (
        <MethodologyBadge text={drug.methodology} />
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard
          label={t("optimizer.kpis.uniqueDrugCodes")}
          value={isUnavailable ? unavailableLabel : fmtNumOrUnavailable(drug.n_active_drugs)}
          sub={isUnavailable ? t("optimizer.kpis.catalogOnlyUntilClaimLines") : t("optimizer.kpis.distinctEk4aCodes")}
        />
        <KpiCard
          label={t("optimizer.kpis.drugClaimLines")}
          value={isUnavailable ? unavailableLabel : fmtNumOrUnavailable(drug.n_drugs_total)}
          sub={isUnavailable ? t("optimizer.kpis.dispensedLineItemsRequired") : t("optimizer.kpis.dispensedLinesValidated")}
        />
        <KpiCard
          label={t("optimizer.kpis.tierMismatches")}
          value={isUnavailable ? unavailableLabel : fmtNumOrUnavailable(tierMismatches)}
          valueColor={!isUnavailable && tierMismatches && tierMismatches > 0 ? "#B45309" : undefined}
          sub={isUnavailable ? t("optimizer.kpis.actualClaimAmountsRequired") : t("optimizer.kpis.payableVsTierExpectation")}
        />
        <KpiCard
          label={t("optimizer.kpis.discountSavings")}
          value={isUnavailable ? unavailableLabel : fmtTRY2OrUnavailable(drug.total_discount_savings_try ?? null)}
          valueColor="#B45309"
          sub={isUnavailable ? t("optimizer.kpis.exactClaimInputsRequired") : t("optimizer.kpis.billedMinusExpectedPayable")}
        />
      </div>
    </>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   TAB EXPORTS — Compliance and Revenue (Option A split)
   ═══════════════════════════════════════════════════════════════════════════ */

export function SUTComplianceTab({
  cohortPatientIds,
  cohortFilterActive,
}: {
  cohortPatientIds: Set<string>;
  cohortFilterActive: boolean;
}) {
  const t = useT();
  const { getRevealProps } = useStaggeredReveal(2, { baseDelayMs: 40, stepMs: 140, threshold: 0.15 });
  const r0 = getRevealProps(0);
  const r1 = getRevealProps(1);

  return (
    <div className="relative space-y-6">
      <p
        className={`text-sm leading-snug text-[var(--text-secondary)] ${r0.staggerClass}`}
        style={r0.staggerStyle}
        {...r0.staggerAttrs}
      >
        {t("optimizer.tabs.complianceDescription")}
      </p>
      <div className={r1.staggerClass} style={r1.staggerStyle} {...r1.staggerAttrs}>
        <ComplianceAlerts
          cohortPatientIds={cohortPatientIds}
          cohortFilterActive={cohortFilterActive}
        />
      </div>
    </div>
  );
}

export function SUTRevenueTab({
  cohortPatientIds,
  cohortFilterActive,
}: {
  cohortPatientIds: Set<string>;
  cohortFilterActive: boolean;
}) {
  const t = useT();
  const { getRevealProps } = useStaggeredReveal(2, { baseDelayMs: 40, stepMs: 140, threshold: 0.15 });
  const r0 = getRevealProps(0);
  const r1 = getRevealProps(1);

  return (
    <div className="relative space-y-6">
      <p
        className={`text-sm leading-snug text-[var(--text-secondary)] ${r0.staggerClass}`}
        style={r0.staggerStyle}
        {...r0.staggerAttrs}
      >
        {t("optimizer.tabs.revenueDescription")}
      </p>
      <div className={r1.staggerClass} style={r1.staggerStyle} {...r1.staggerAttrs}>
        <RevenueRecoveryDashboard
          cohortPatientIds={cohortPatientIds}
          cohortFilterActive={cohortFilterActive}
        />
      </div>
    </div>
  );
}

/** @deprecated Use SUTComplianceTab or SUTRevenueTab */
export default function SUTOptimizer() {
  const emptySet = new Set<string>();
  return <SUTComplianceTab cohortPatientIds={emptySet} cohortFilterActive={false} />;
}
