"use client";

import type {
  DRGSummaryData,
  SutPatientOutcomeData,
} from "@/lib/domains/sut";
import { getUnavailableMessage, isExactOutput } from "@/lib/sutExactness";
import useStaggeredReveal from "@/hooks/useStaggeredReveal";
import PatientSearch from "@/components/ui/PatientSearch";
import { searchSutPatients } from "@/lib/api/sut";
import { SutPatientAnalyticsSkeleton } from "@/components/skeletons/SutSkeletons";
import { Chip, DataTable, Eyebrow, Surface } from "@/components/primitives";
import PatientInvoiceTable from "@/components/tables/PatientInvoiceTable";
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
}: {
  data: SutPatientOutcomeData | null;
  error: string | null;
  loading: boolean;
  reveal: ReturnType<typeof useStaggeredReveal>;
  selectedPatientId: string | null;
  onPatientSelect: (patientId: string) => void;
  onRetry: () => void;
}) {
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

  return (
    <div>
      <Surface variant="base" padding="lg" className="mb-6">
        <div className="flex items-center gap-4">
          <span className="font-semibold whitespace-nowrap">Patient:</span>
          <PatientSearch
            id="patient-sut-search"
            selectedPatientId={selectedPatientId}
            onSelect={onPatientSelect}
            placeholder="Search patient ID for SUT analysis..."
            searchFn={searchSutPatients}
          />
        </div>
      </Surface>

      {selectedPatientId && (
        <Surface variant="base" padding="lg" className="mb-6">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <Eyebrow>Selected patient</Eyebrow>
              <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">Patient {selectedPatientId}</p>
            </div>
            <p className="text-xs text-[var(--text-secondary)]">
              {outcomeState === "loading"
                ? "Refreshing exact DRG analytics..."
                : outcomeState === "error"
                  ? "Patient analytics could not be loaded."
                  : outcomeState === "empty"
                    ? "Patient-level DRG analytics are not currently loaded."
                    : "Patient-level DRG analytics are ready."}
            </p>
          </div>
        </Surface>
      )}

      {outcomeState === "idle" ? (
        <PatientInvoiceTable />
      ) : outcomeState === "loading" ? (
        <SutPatientAnalyticsSkeleton patientId={selectedPatientId} />
      ) : outcomeState === "error" ? (
        <Surface variant="base" padding="lg" className="space-y-3">
          <div>
            <Chip variant="danger">{error}</Chip>
            <p className="mt-2 text-xs text-[var(--text-secondary)]">
              Retry this patient, or pick a different patient from the search box.
            </p>
          </div>
          <div>
            <button
              type="button"
              className="sut-section-btn sut-section-btn-active sut-section-btn-compact"
              onClick={onRetry}
            >
              <span className="text-xs font-semibold">Retry patient outcome</span>
            </button>
          </div>
        </Surface>
      ) : outcomeState === "empty" ? (
        <div className="empty-state space-y-3">
          <p className="empty-state-text">
            Patient-level SUT analytics are not currently loaded for patient {selectedPatientId}.
          </p>
          <div>
            <button
              type="button"
              className="sut-section-btn sut-section-btn-compact"
              onClick={onRetry}
            >
              <span className="text-xs font-semibold">Retry patient outcome</span>
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
            <Eyebrow>Exact-only patient outcome</Eyebrow>
            <h3 className="mt-2 text-lg font-semibold text-[var(--text-primary)]">DRG package review stays explicit</h3>
            <div className="mt-3 space-y-2 text-sm leading-relaxed text-[var(--text-secondary)]">
              <p>
                Estimate-backed SUT cost ranges and gap projections were removed.
              </p>
              <p>
                This patient view now keeps only the surviving DRG package outcome surface, and missing
                pricing metadata stays unavailable instead of being treated as exact.
              </p>
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
              <p className="text-sm font-semibold text-[var(--text-primary)]">No DRG episode summary available</p>
              <p className="mt-2 text-sm text-[var(--text-secondary)]">
                This patient outcome no longer includes estimate-backed fallback sections. If exact DRG
                pricing inputs are unavailable, the patient remains unavailable here.
              </p>
            </Surface>
          )}
        </div>
      ) : null}
    </div>
  );
}

export function ClaimSummaryPanel({ data }: { data: SutPatientOutcomeData }) {
  const totals = data.sut_claim_totals;
  const summary = data.sut_claim_summary;
  if (!totals) {
    return null;
  }

  return (
    <div className="space-y-5">
      <div>
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wider text-text-secondary">
          Exact Claim-Line Summary
        </h3>
        <p className="text-xs text-slate-400">
          Patient-level SUT totals are assembled from exact synthetic claim headers and claim lines.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiCard
          label="Total Billed"
          value={fmtTRYOrUnavailable(totals.total_billed_try)}
          sub="Exact claim-line amount"
        />
        <KpiCard
          label="Expected Payable"
          value={fmtTRYOrUnavailable(totals.total_expected_payable_try)}
          sub="Synthetic expected output"
        />
        <KpiCard label="Claims" value={fmtNum(totals.claim_count)} />
        <KpiCard label="Procedure Lines" value={fmtNum(totals.procedure_line_count)} />
      </div>

      {summary && (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <KpiCard label="Material Lines" value={fmtNum(summary.material_line_count)} />
            <KpiCard label="Drug Lines" value={fmtNum(summary.drug_line_count)} />
            <KpiCard label="Diagnoses" value={fmtNum(summary.diagnosis_count)} />
            <KpiCard
              label="Rule Flags"
              value={fmtNum(
                summary.top_procedures.filter((procedure) =>
                  procedure.surcharge_applicable || procedure.copay_rate_applicable
                ).length,
              )}
              sub="Visible top procedures"
            />
          </div>

          {summary.top_procedures.length > 0 && (
            <DataTable minWidth={720} className="text-xs">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Procedure</th>
                  <th className="num-col">Billed</th>
                  <th className="text-center">Surcharge</th>
                  <th className="text-center">Copay Rate</th>
                </tr>
              </thead>
              <tbody>
                {summary.top_procedures.slice(0, 6).map((procedure) => (
                  <tr key={procedure.procedure_line_id}>
                    <td className="font-mono">{procedure.procedure_date ?? "—"}</td>
                    <td>
                      <span className="font-semibold">{procedure.procedure_code}</span>
                      <span className="ml-2 text-[var(--text-muted)]">{procedure.procedure_name}</span>
                    </td>
                    <td className="num-col font-medium">{fmtTRYOrUnavailable(procedure.billed_amount_try)}</td>
                    <td className="text-center">{procedure.surcharge_applicable ? "Yes" : "No"}</td>
                    <td className="text-center">{procedure.copay_rate_applicable ? "Yes" : "No"}</td>
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
  const drgExact = isExactOutput(data);
  const totalPkgPrice = drgExact ? data.total_drg_package_price : null;

  return (
    <>
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-text-secondary">
        DRG Episode Cost Modeling
      </h3>
      <p className="mb-3 text-xs text-slate-400">
        Compares itemized episode costs against SGK bundled DRG package prices (EK-2C).
        Surplus means the DRG package covers more than itemized costs.
      </p>
      {!drgExact && (
        <div
          className="mb-4 rounded-2xl border px-4 py-3 text-sm"
          style={{ borderColor: "rgba(113, 113, 122, 0.2)", color: "#52525B" }}
        >
          {getUnavailableMessage(
            data,
            "DRG package pricing remains unavailable until every episode has an exact admission date and historical package price.",
          )}
        </div>
      )}
      <div className="mb-4 flex flex-wrap gap-6 text-sm">
        <div>
          <span className="text-slate-400">Episodes:</span>{" "}
          <span className="font-bold text-text-primary">{fmtNum(data.n_episodes)}</span>
        </div>
        <div>
          <span className="text-slate-400">Itemized Cost:</span>{" "}
          <span className="font-bold tabular-nums text-[var(--text-primary)]">{fmtTRY(data.total_drg_cost)}</span>
        </div>
        <div>
          <span className="text-slate-400">DRG Package Price:</span>{" "}
          <span className="font-bold text-amber-800">{fmtTRYOrUnavailable(totalPkgPrice)}</span>
        </div>
        <div>
          <span className="text-slate-400">Mean/Episode:</span>{" "}
          <span className="font-bold text-text-primary">{fmtTRY(data.mean_episode_cost)}</span>
        </div>
        <div>
          <span className="text-slate-400">Costliest:</span>{" "}
          <span className="font-bold text-amber-800">{data.most_expensive_drg}</span>
        </div>
      </div>
      <DataTable className="text-xs">
        <thead>
          <tr>
            <th>#</th>
            <th>ICD-10</th>
            <th>Description</th>
            <th className="text-center">Group</th>
            <th className="num-col">LOS</th>
            <th className="num-col">Lab</th>
            <th className="num-col">Visit</th>
            <th className="num-col">Rx</th>
            <th className="num-col">Proc</th>
            <th className="num-col">Itemized</th>
            <th className="num-col">DRG Price</th>
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
                    {ep.ek2c_group || "—"}
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
