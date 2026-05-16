"use client";

import Link from "next/link";
import { ArrowLeft, ArrowRight, ReceiptText, ShieldAlert } from "lucide-react";
import type { CSSProperties } from "react";
import type {
  CopayExemptionResult,
  PatientOptimization,
  SutPatientOutcomeData,
} from "@/lib/domains/sut";
import {
  buildSutBillingHref,
  buildSutHomeHref,
} from "@/lib/constants";
import { DRGPanel } from "@/components/tabs/sut/PatientSection";
import {
  fmtLabel,
  fmtNum,
  fmtPctRatio,
  KpiCard,
} from "@/components/tabs/sut/shared";
import { getUnavailableMessage, isExactOutput } from "@/lib/sutExactness";
import { theme } from "@/lib/theme";
import { SyntheticDemoProvenance } from "@/components/sut/SyntheticDemoProvenance";

const MUTED_CHIP_COLOR = "#64748B";

function statusChipStyle(color: string): CSSProperties {
  return { "--sut-chip-color": color } as CSSProperties;
}

function ExactnessNotice({
  block,
  fallback,
}: {
  block: {
    unavailable_reason?: string | null;
    required_inputs_missing?: string[] | null;
  } | null | undefined;
  fallback: string;
}) {
  return <div className="sut-exactness-notice">{getUnavailableMessage(block, fallback)}</div>;
}

function CopayExemptionSummary({
  copay,
}: {
  copay: CopayExemptionResult;
}) {
  const topMatch = copay.qualifying_diagnoses[0];
  return (
    <div className="sut-panel-card">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="sut-muted-label">Copay exemption</p>
          <h3 className="mt-2 text-lg font-semibold text-slate-950">
            {copay.exempt ? "Eligible" : "No qualifying exemption found"}
          </h3>
          <p className="sut-section-description mt-2">
            {copay.exempt
              ? `The patient currently matches ${fmtNum(copay.n_qualifying)} qualifying diagnosis${copay.n_qualifying === 1 ? "" : "es"} for outpatient copay waiver review.`
              : "No qualifying exemption diagnosis is currently present in the cached SUT diagnosis set."}
          </p>
        </div>
        <span
          className="sut-status-chip"
          style={statusChipStyle(copay.exempt ? theme.accent : MUTED_CHIP_COLOR)}
        >
          {copay.exempt ? "Actionable" : "Clear"}
        </span>
      </div>

      {topMatch && (
        <div className="sut-panel-card sut-panel-card-soft mt-4 px-4 py-3 text-sm">
          <p className="font-semibold text-slate-900">{topMatch.disease}</p>
          <p className="sut-section-description mt-1">
            ICD-10 {topMatch.icd10} &middot; Gazette range {topMatch.range}
          </p>
        </div>
      )}
    </div>
  );
}

export function PatientOptimizationSnapshot({
  optimization,
}: {
  optimization: PatientOptimization;
}) {
  const surchargeExact = isExactOutput(optimization.surcharge_exposure);
  const copayRateExact = isExactOutput(optimization.copay_rate_exposure);
  const drgExact = isExactOutput(optimization.drg_unbundling);

  return (
    <section className="space-y-4">
      <div className="flex items-center gap-2">
        <ShieldAlert className="sut-icon-accent h-5 w-5" />
        <div>
          <h2 className="text-lg font-semibold text-slate-950">Optimization snapshot</h2>
          <p className="sut-section-description">
            Patient-level SUT rule findings stay exactness-aware: unavailable inputs stay unavailable.
          </p>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <CopayExemptionSummary copay={optimization.copay_exemptions} />

        <div className="sut-panel-card">
          <p className="sut-muted-label">Surcharge exposure</p>
          <h3 className="mt-2 text-lg font-semibold text-slate-950">Procedure surcharge controls</h3>
          <div className="mt-4">
            {surchargeExact ? (
              <div className="grid gap-3 sm:grid-cols-2">
                <KpiCard
                  label="Applicable procedures"
                  value={fmtNum(optimization.surcharge_exposure.n_applicable_procedures ?? 0)}
                />
                <KpiCard
                  label="Exposure rate"
                  value={fmtPctRatio((optimization.surcharge_exposure.exposure_rate ?? 0), 1)}
                />
              </div>
            ) : (
              <ExactnessNotice
                block={optimization.surcharge_exposure}
                fallback="Surcharge exposure stays unavailable until exact billed procedure lines are present."
              />
            )}
          </div>
        </div>

        <div className="sut-panel-card">
          <p className="sut-muted-label">Copay-rate exposure</p>
          <h3 className="mt-2 text-lg font-semibold text-slate-950">Rate-cap review</h3>
          <div className="mt-4">
            {copayRateExact ? (
              <div className="grid gap-3 sm:grid-cols-2">
                <KpiCard
                  label="Applicable procedures"
                  value={fmtNum(optimization.copay_rate_exposure.n_applicable_procedures ?? 0)}
                />
                <KpiCard
                  label="Mean rate"
                  value={fmtPctRatio((optimization.copay_rate_exposure.mean_rate ?? 0) / 100, 1)}
                />
              </div>
            ) : (
              <ExactnessNotice
                block={optimization.copay_rate_exposure}
                fallback="Copay-rate exposure stays unavailable until exact billed procedure lines are present."
              />
            )}
          </div>
        </div>

        <div className="sut-panel-card">
          <p className="sut-muted-label">DRG package review</p>
          <h3 className="mt-2 text-lg font-semibold text-slate-950">Package-vs-itemized check</h3>
          <div className="mt-4">
            {drgExact ? (
              <div className="space-y-3">
                <KpiCard
                  label="Chapters analyzed"
                  value={fmtNum(optimization.drg_unbundling?.n_chapters_analyzed ?? 0)}
                />
                <KpiCard
                  label="Risk state"
                  value={
                    optimization.drg_unbundling?.has_unbundling_risk
                      ? "Potential package opportunity"
                      : "No risk flagged"
                  }
                  valueColor={optimization.drg_unbundling?.has_unbundling_risk ? "#B45309" : theme.accent}
                />
              </div>
            ) : (
              <ExactnessNotice
                block={optimization.drg_unbundling}
                fallback="DRG unbundling review stays unavailable until exact itemized claim lines exist."
              />
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

export default function SutPatientWorkspace({
  patientId,
  outcome,
  optimization,
}: {
  patientId: string;
  outcome: SutPatientOutcomeData | null;
  optimization: PatientOptimization | null;
}) {
  const workspaceDataSources = [outcome, optimization];

  return (
    <div className="space-y-6">
      <header className="frost-panel sut-premium-panel sut-home-header">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="sut-premium-eyebrow">SUT patient workspace</div>
            <h1 className="sut-patient-id-title mt-2">{patientId}</h1>
            <p className="sut-premium-subtitle mt-3 max-w-3xl">
              A dedicated patient-level exact-only workspace that composes surviving SUT outcome and
              optimization data before handing off to the deeper billing review.
            </p>
            <SyntheticDemoProvenance dataSources={workspaceDataSources} className="mt-4" />
          </div>

          <div className="flex flex-wrap gap-3">
            <Link href={buildSutHomeHref("analytics")} className="sut-section-btn">
              <ArrowLeft className="h-4 w-4" />
              Back to analytics
            </Link>
            <Link href={buildSutBillingHref(patientId)} className="sut-section-btn sut-section-btn-active">
              <ReceiptText className="h-4 w-4" />
              Open billing review
            </Link>
          </div>
        </div>
      </header>

      {optimization && (
        <div className="frost-panel sut-premium-glass p-5">
          <div className="mb-4 flex flex-wrap gap-3">
            <KpiCard label="Diagnoses" value={fmtNum(optimization.n_diagnoses)} />
            <KpiCard
              label="ICD chapters"
              value={optimization.icd10_chapters.length > 0 ? optimization.icd10_chapters.join(", ") : "None"}
            />
            <KpiCard
              label="Primary focus"
              value={optimization.copay_exemptions.exempt ? "Copay exemption" : "Exactness review"}
              valueColor={optimization.copay_exemptions.exempt ? theme.accent : "#64748B"}
            />
          </div>
          <PatientOptimizationSnapshot optimization={optimization} />
        </div>
      )}

      {outcome?.consistency_warnings && outcome.consistency_warnings.length > 0 && (
        <div className="rounded-lg border border-green-200 bg-green-50/50 px-4 py-3">
          {outcome.consistency_warnings.map((warning, index) => (
            <p key={index} className="text-xs text-amber-800">
              {warning}
            </p>
          ))}
        </div>
      )}
      {outcome?.drg_summary && outcome.drg_summary.n_episodes > 0 && (
        <div className="frost-panel sut-premium-glass p-5">
          <DRGPanel data={outcome.drg_summary} />
        </div>
      )}

      <section className="frost-panel sut-premium-glass p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="sut-muted-label">Billing handoff</p>
            <h2 className="mt-2 text-lg font-semibold text-slate-950">Move into the detailed billing review</h2>
            <p className="sut-section-description mt-2 max-w-3xl">
              This patient workspace keeps the high-level DRG and optimization story in one place,
              while the full section-by-section billing report stays on its dedicated route.
            </p>
            <p className="sut-section-description mt-3 max-w-3xl">
              Exactness note: this page does not invent billing totals locally. Open the dedicated billing
              review to inspect section-level exactness, unavailable states, and detailed recovery actions.
            </p>
          </div>

          <Link href={buildSutBillingHref(patientId)} className="sut-section-btn sut-section-btn-active">
            Open billing review
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>

        {optimization?.diagnoses && optimization.diagnoses.length > 0 && (
          <div className="sut-panel-card mt-5">
            <p className="sut-muted-label">Diagnosis context</p>
            <p className="sut-section-description mt-2">
              {optimization.diagnoses.slice(0, 6).map((diagnosis) => fmtLabel(diagnosis)).join(", ")}
              {optimization.diagnoses.length > 6 ? " ..." : ""}
            </p>
          </div>
        )}
      </section>
    </div>
  );
}
