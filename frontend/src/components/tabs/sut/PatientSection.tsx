"use client";

import type {
  DRGSummaryData,
  SutPatientOutcomeData,
} from "@/lib/domains/sut";
import { getUnavailableMessage, isExactOutput } from "@/lib/sutExactness";
import useStaggeredReveal from "@/hooks/useStaggeredReveal";
import { SutPatientAnalyticsSkeleton } from "@/components/skeletons/SutSkeletons";
import { Chip, DataTable, Eyebrow, Surface } from "@/components/primitives";
import PatientInvoiceTable from "@/components/tables/PatientInvoiceTable";
import { useT } from "@/lib/i18n/useTranslations";
import {
  fmtNum,
  fmtTRY,
  fmtTRYOrUnavailable,
  getSutOutcomeViewState,
  KpiCard,
} from "./shared";

export function PatientSUTContent({
  data,
  error,
  loading,
  reveal,
  selectedPatientId,
  onPatientSelect,
  onRetry,
  cohortPatientIds,
  cohortFilterActive,
}: {
  data: SutPatientOutcomeData | null;
  error: string | null;
  loading: boolean;
  reveal: ReturnType<typeof useStaggeredReveal>;
  selectedPatientId: string | null;
  onPatientSelect: (patientId: string) => void;
  onRetry: () => void;
  cohortPatientIds?: Set<string>;
  cohortFilterActive?: boolean;
}) {
  const t = useT();
  const outcomeState = getSutOutcomeViewState({
    selectedPatientId,
    loading,
    error,
    hasData: Boolean(data),
  });

  const getReveal = (index: number) =>
    reveal.getRevealProps?.(index, "scale") ?? {
      staggerAttrs: {},
      staggerClass: "",
      staggerStyle: undefined,
    };

  const summaryReveal = getReveal(0);
  const warningReveal = getReveal(1);
  const claimReveal = getReveal(2);
  const drgReveal = getReveal(3);

  const statusMessage =
    outcomeState === "loading"
      ? t("patient.section.selectedPatient.statusLoading")
      : outcomeState === "error"
        ? t("patient.section.selectedPatient.statusError")
        : outcomeState === "empty"
          ? t("patient.section.selectedPatient.statusEmpty")
          : t("patient.section.selectedPatient.statusReady");

  return (
    <div>
      {selectedPatientId && (
        <Surface variant="base" padding="lg" className="mb-6">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <Eyebrow>{t("patient.section.selectedPatient.eyebrow")}</Eyebrow>
              <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">
                {t("patient.section.selectedPatient.label", { patientId: selectedPatientId })}
              </p>
            </div>
            <p className="text-xs text-[var(--text-secondary)]">{statusMessage}</p>
          </div>
        </Surface>
      )}

      {outcomeState === "idle" ? (
        <PatientInvoiceTable
          cohortPatientIds={cohortPatientIds}
          cohortFilterActive={cohortFilterActive}
        />
      ) : outcomeState === "loading" ? (
        <SutPatientAnalyticsSkeleton patientId={selectedPatientId} />
      ) : outcomeState === "error" ? (
        <Surface variant="base" padding="lg" className="space-y-3">
          <div>
            <Chip variant="danger">{error}</Chip>
            <p className="mt-2 text-xs text-[var(--text-secondary)]">
              {t("patient.section.errors.retryHint")}
            </p>
          </div>
          <div>
            <button
              type="button"
              className="sut-section-btn sut-section-btn-active sut-section-btn-compact"
              onClick={onRetry}
            >
              <span className="text-xs font-semibold">{t("patient.section.errors.retryButton")}</span>
            </button>
          </div>
        </Surface>
      ) : outcomeState === "empty" ? (
        <div className="empty-state space-y-3">
          <p className="empty-state-text">
            {t("patient.section.emptyState.message", { patientId: selectedPatientId ?? "" })}
          </p>
          <div>
            <button
              type="button"
              className="sut-section-btn sut-section-btn-compact"
              onClick={onRetry}
            >
              <span className="text-xs font-semibold">{t("patient.section.errors.retryButton")}</span>
            </button>
          </div>
        </div>
      ) : data ? (
        <div className="space-y-6">
          <Surface
            variant="base"
            padding="lg"
            {...summaryReveal.staggerAttrs}
            className={summaryReveal.staggerClass}
            style={summaryReveal.staggerStyle}
          >
            <Eyebrow>{t("patient.section.outcomeSummary.eyebrow")}</Eyebrow>
            <h3 className="mt-2 text-lg font-semibold text-[var(--text-primary)]">
              {t("patient.section.outcomeSummary.title")}
            </h3>
            <div className="mt-3 space-y-2 text-sm leading-relaxed text-[var(--text-secondary)]">
              <p>{t("patient.section.outcomeSummary.paragraph1")}</p>
              <p>{t("patient.section.outcomeSummary.paragraph2")}</p>
            </div>
          </Surface>

          {data.consistency_warnings && data.consistency_warnings.length > 0 && (
            <div
              {...warningReveal.staggerAttrs}
              className={`rounded-lg border border-green-200 bg-green-50/50 px-4 py-3 ${warningReveal.staggerClass}`}
              style={warningReveal.staggerStyle}
            >
              {data.consistency_warnings.map((warning, index) => (
                <p key={index} className="text-xs text-amber-800">
                  {warning}
                </p>
              ))}
            </div>
          )}

          {data.sut_claim_totals && (
            <Surface
              variant="base"
              padding="lg"
              {...claimReveal.staggerAttrs}
              className={claimReveal.staggerClass}
              style={claimReveal.staggerStyle}
            >
              <ClaimSummaryPanel data={data} />
            </Surface>
          )}

          {data.drg_summary && data.drg_summary.n_episodes > 0 ? (
            <Surface
              variant="base"
              padding="lg"
              {...drgReveal.staggerAttrs}
              className={drgReveal.staggerClass}
              style={drgReveal.staggerStyle}
            >
              <DRGPanel data={data.drg_summary} />
            </Surface>
          ) : (
            <Surface
              variant="base"
              padding="lg"
              {...drgReveal.staggerAttrs}
              className={drgReveal.staggerClass}
              style={drgReveal.staggerStyle}
            >
              <p className="text-sm font-semibold text-[var(--text-primary)]">
                {t("patient.section.noDrgSummary.title")}
              </p>
              <p className="mt-2 text-sm text-[var(--text-secondary)]">
                {t("patient.section.noDrgSummary.body")}
              </p>
            </Surface>
          )}
        </div>
      ) : null}
    </div>
  );
}

export function ClaimSummaryPanel({ data }: { data: SutPatientOutcomeData }) {
  const t = useT();
  const totals = data.sut_claim_totals;
  const summary = data.sut_claim_summary;
  if (!totals) {
    return null;
  }

  return (
    <div className="space-y-5">
      <div>
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wider text-text-secondary">
          {t("patient.section.claimSummary.title")}
        </h3>
        <p className="text-xs text-slate-400">{t("patient.section.claimSummary.description")}</p>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiCard
          label={t("patient.section.claimSummary.totalBilled")}
          value={fmtTRYOrUnavailable(totals.total_billed_try)}
          sub={t("patient.section.claimSummary.exactClaimLineAmount")}
        />
        <KpiCard
          label={t("patient.section.claimSummary.expectedPayable")}
          value={fmtTRYOrUnavailable(totals.total_expected_payable_try)}
          sub={t("patient.section.claimSummary.syntheticExpectedOutput")}
        />
        <KpiCard label={t("patient.section.claimSummary.claims")} value={fmtNum(totals.claim_count)} />
        <KpiCard
          label={t("patient.section.claimSummary.procedureLines")}
          value={fmtNum(totals.procedure_line_count)}
        />
      </div>

      {summary && (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <KpiCard
              label={t("patient.section.claimSummary.materialLines")}
              value={fmtNum(summary.material_line_count)}
            />
            <KpiCard label={t("patient.section.claimSummary.drugLines")} value={fmtNum(summary.drug_line_count)} />
            <KpiCard label={t("patient.section.claimSummary.diagnoses")} value={fmtNum(summary.diagnosis_count)} />
            <KpiCard
              label={t("patient.section.claimSummary.ruleFlags")}
              value={fmtNum(
                summary.top_procedures.filter((procedure) =>
                  procedure.surcharge_applicable || procedure.copay_rate_applicable
                ).length,
              )}
              sub={t("patient.section.claimSummary.ruleFlagsSub")}
            />
          </div>

          {summary.top_procedures.length > 0 && (
            <DataTable minWidth={720} className="text-xs">
              <thead>
                <tr>
                  <th>{t("patient.section.claimSummary.table.date")}</th>
                  <th>{t("patient.section.claimSummary.table.procedure")}</th>
                  <th className="num-col">{t("patient.section.claimSummary.table.billed")}</th>
                  <th className="text-center">{t("patient.section.claimSummary.table.surcharge")}</th>
                  <th className="text-center">{t("patient.section.claimSummary.table.copayRate")}</th>
                </tr>
              </thead>
              <tbody>
                {summary.top_procedures.slice(0, 6).map((procedure) => (
                  <tr key={procedure.procedure_line_id}>
                    <td className="font-mono">{procedure.procedure_date ?? t("common.dash")}</td>
                    <td>
                      <span className="font-semibold">{procedure.procedure_code}</span>
                      <span className="ml-2 text-[var(--text-muted)]">{procedure.procedure_name}</span>
                    </td>
                    <td className="num-col font-medium">{fmtTRYOrUnavailable(procedure.billed_amount_try)}</td>
                    <td className="text-center">
                      {procedure.surcharge_applicable ? t("common.yes") : t("common.no")}
                    </td>
                    <td className="text-center">
                      {procedure.copay_rate_applicable ? t("common.yes") : t("common.no")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          )}
        </>
      )}
    </div>
  );
}

export function DRGPanel({ data }: { data: DRGSummaryData }) {
  const t = useT();
  const drgExact = isExactOutput(data);
  const totalPkgPrice = drgExact ? data.total_drg_package_price : null;

  return (
    <>
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-text-secondary">
        {t("patient.section.drgPanel.title")}
      </h3>
      <p className="mb-3 text-xs text-slate-400">{t("patient.section.drgPanel.description")}</p>
      {!drgExact && (
        <div
          className="mb-4 rounded-2xl border px-4 py-3 text-sm"
          style={{ borderColor: "rgba(113, 113, 122, 0.2)", color: "#52525B" }}
        >
          {getUnavailableMessage(data, t("patient.section.drgPanel.unavailableFallback"))}
        </div>
      )}
      <div className="mb-4 flex flex-wrap gap-6 text-sm">
        <div>
          <span className="text-slate-400">{t("patient.section.drgPanel.episodes")}</span>{" "}
          <span className="font-bold text-text-primary">{fmtNum(data.n_episodes)}</span>
        </div>
        <div>
          <span className="text-slate-400">{t("patient.section.drgPanel.itemizedCost")}</span>{" "}
          <span className="font-bold tabular-nums text-[var(--text-primary)]">{fmtTRY(data.total_drg_cost)}</span>
        </div>
        <div>
          <span className="text-slate-400">{t("patient.section.drgPanel.drgPackagePrice")}</span>{" "}
          <span className="font-bold text-amber-800">{fmtTRYOrUnavailable(totalPkgPrice)}</span>
        </div>
        <div>
          <span className="text-slate-400">{t("patient.section.drgPanel.meanEpisode")}</span>{" "}
          <span className="font-bold text-text-primary">{fmtTRY(data.mean_episode_cost)}</span>
        </div>
        <div>
          <span className="text-slate-400">{t("patient.section.drgPanel.costliest")}</span>{" "}
          <span className="font-bold text-amber-800">{data.most_expensive_drg}</span>
        </div>
      </div>
      <DataTable className="text-xs">
        <thead>
          <tr>
            <th>{t("patient.section.drgPanel.table.index")}</th>
            <th>{t("patient.section.drgPanel.table.icd10")}</th>
            <th>{t("patient.section.drgPanel.table.description")}</th>
            <th className="text-center">{t("patient.section.drgPanel.table.group")}</th>
            <th className="num-col">{t("patient.section.drgPanel.table.los")}</th>
            <th className="num-col">{t("patient.section.drgPanel.table.lab")}</th>
            <th className="num-col">{t("patient.section.drgPanel.table.visit")}</th>
            <th className="num-col">{t("patient.section.drgPanel.table.rx")}</th>
            <th className="num-col">{t("patient.section.drgPanel.table.proc")}</th>
            <th className="num-col">{t("patient.section.drgPanel.table.itemized")}</th>
            <th className="num-col">{t("patient.section.drgPanel.table.drgPrice")}</th>
          </tr>
        </thead>
        <tbody>
          {data.episodes.map((ep) => {
            const episodeExact = isExactOutput(ep);
            return (
              <tr key={ep.episode_id}>
                <td className="text-[var(--text-muted)]">{fmtNum(ep.episode_id + 1)}</td>
                <td className="font-mono tabular-nums">{ep.primary_icd10}</td>
                <td>{ep.description}</td>
                <td className="text-center">
                  <span className="rounded bg-[var(--surface-tint)] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--text-muted)]">
                    {ep.ek2c_group || t("common.dash")}
                  </span>
                </td>
                <td className="num-col">{fmtNum(ep.los_days)}</td>
                <td className="num-col">{fmtTRY(ep.lab_cost)}</td>
                <td className="num-col">{fmtTRY(ep.visit_cost)}</td>
                <td className="num-col">{fmtTRY(ep.rx_cost)}</td>
                <td className="num-col">{fmtTRY(ep.procedure_cost)}</td>
                <td className="num-col font-semibold">{fmtTRY(ep.total_cost)}</td>
                <td className="num-col font-semibold text-[var(--warning)]">
                  {fmtTRYOrUnavailable(episodeExact ? ep.drg_package_price : null)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </DataTable>
    </>
  );
}
