"use client";

import Link from "next/link";
import { ArrowLeft, ShieldAlert } from "lucide-react";
import type {
  CopayExemptionResult,
  PatientOptimization,
  SutPatientOutcomeData,
} from "@/lib/domains/sut";
import {
  buildSutHomeHref,
} from "@/lib/constants";
import { DRGPanel } from "@/components/tabs/sut/PatientSection";
import {
  fmtNum,
  fmtPctRatio,
} from "@/components/tabs/sut/shared";
import { getUnavailableMessage, isExactOutput } from "@/lib/sutExactness";
import { theme } from "@/lib/theme";
import { Chip, Eyebrow, Stat, Surface } from "@/components/primitives";
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
  return (
    <p className="text-sm leading-relaxed text-[var(--text-secondary)]">
      {getUnavailableMessage(block, fallback)}
    </p>
  );
}

function OptimizationCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <Surface variant="soft" padding="md" className="space-y-3">
      <Eyebrow>{title}</Eyebrow>
      <div>{children}</div>
    </Surface>
  );
}

function CopayExemptionSummary({ copay }: { copay: CopayExemptionResult }) {
  const topMatch = copay.qualifying_diagnoses[0];
  return (
    <Surface variant="soft" padding="md" className="space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <Eyebrow>Copay exemption</Eyebrow>
          <p className="mt-2 font-[var(--font-display)] text-lg font-medium tracking-tight text-[var(--text-primary)]">
            {copay.exempt ? "Eligible" : "No qualifying exemption found"}
          </p>
          <p className="mt-2 text-sm leading-snug text-[var(--text-secondary)]">
            {copay.exempt
              ? `The patient currently matches ${fmtNum(copay.n_qualifying)} qualifying diagnosis${copay.n_qualifying === 1 ? "" : "es"} for outpatient copay waiver review.`
              : "No qualifying exemption diagnosis is currently present in the cached SUT diagnosis set."}
          </p>
        </div>
        <Chip variant={copay.exempt ? "success" : "neutral"}>
          {copay.exempt ? "Actionable" : "Clear"}
        </Chip>
      </div>

      {topMatch && (
        <Surface variant="base" padding="sm" className="text-sm">
          <p className="font-semibold text-[var(--text-primary)]">{topMatch.disease}</p>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">
            ICD-10 {topMatch.icd10} &middot; Gazette range {topMatch.range}
          </p>
        </Surface>
      )}
    </Surface>
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
      <div className="flex items-start gap-3">
        <ShieldAlert
          aria-hidden="true"
          className="mt-0.5 h-5 w-5 shrink-0 text-[var(--gold)]"
        />
        <div>
          <h2 className="font-[var(--font-display)] text-lg font-medium tracking-tight text-[var(--text-primary)]">
            Optimization snapshot
          </h2>
          <p className="mt-1 text-sm leading-snug text-[var(--text-secondary)]">
            Patient-level SUT rule findings stay exactness-aware: unavailable inputs stay unavailable.
          </p>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <CopayExemptionSummary copay={optimization.copay_exemptions} />

        <OptimizationCard title="Surcharge exposure">
          {surchargeExact ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <Stat
                label="Applicable procedures"
                value={fmtNum(optimization.surcharge_exposure.n_applicable_procedures ?? 0)}
              />
              <Stat
                label="Exposure rate"
                value={fmtPctRatio(optimization.surcharge_exposure.exposure_rate ?? 0, 1)}
              />
            </div>
          ) : (
            <ExactnessNotice
              block={optimization.surcharge_exposure}
              fallback="Surcharge exposure stays unavailable until exact billed procedure lines are present."
            />
          )}
        </OptimizationCard>

        <OptimizationCard title="Copay-rate exposure">
          {copayRateExact ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <Stat
                label="Applicable procedures"
                value={fmtNum(optimization.copay_rate_exposure.n_applicable_procedures ?? 0)}
              />
              <Stat
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
        </OptimizationCard>

        <OptimizationCard title="DRG package review">
          {drgExact ? (
            <div className="space-y-3">
              <Stat
                label="Chapters analyzed"
                value={fmtNum(optimization.drg_unbundling?.n_chapters_analyzed ?? 0)}
              />
              <Stat
                label="Risk state"
                value={
                  optimization.drg_unbundling?.has_unbundling_risk
                    ? "Potential package opportunity"
                    : "No risk flagged"
                }
              />
              {optimization.drg_unbundling?.has_unbundling_risk ? (
                <Chip variant="warning">Review package eligibility</Chip>
              ) : null}
            </div>
          ) : (
            <ExactnessNotice
              block={optimization.drg_unbundling}
              fallback="DRG unbundling review stays unavailable until exact itemized claim lines exist."
            />
          )}
        </OptimizationCard>
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
  const primaryFocusLabel = optimization?.copay_exemptions.exempt
    ? "Copay exemption"
    : "Exactness review";
  const primaryFocusColor = optimization?.copay_exemptions.exempt
    ? theme.accent
    : undefined;

  return (
    <div className="space-y-6">
      <Surface variant="base" padding="lg">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <Eyebrow>SUT patient workspace</Eyebrow>
            <h1 className="mt-2 font-[var(--font-display)] text-3xl font-medium leading-tight tracking-tight text-[var(--text-primary)] sm:text-4xl">
              Billing{" "}
              <em className="not-italic font-[var(--font-display)] italic text-[var(--gold)]">
                Report
              </em>
            </h1>
            <p className="mt-2 font-mono text-base text-[var(--text-secondary)]">{patientId}</p>
            <p className="mt-3 max-w-3xl text-sm leading-relaxed text-[var(--text-secondary)]">
              A dedicated patient-level exact-only workspace that composes surviving SUT outcome and
              optimization data before handing off to the deeper billing review.
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <Link href={buildSutHomeHref("analytics")} className="sut-section-btn">
              <ArrowLeft className="h-4 w-4" />
              Back to analytics
            </Link>
          </div>
        </div>
      </Surface>

      {optimization && (
        <Surface variant="base" padding="lg" className="space-y-6">
          <div className="grid gap-6 sm:grid-cols-3">
            <Stat
              label="Diagnoses"
              value={fmtNum(optimization.n_diagnoses)}
              display="gold"
            />
            <Stat
              label="ICD chapters"
              value={
                optimization.icd10_chapters.length > 0
                  ? optimization.icd10_chapters.join(", ")
                  : "None"
              }
            />
            <Stat
              label="Primary focus"
              value={
                <span style={primaryFocusColor ? { color: primaryFocusColor } : undefined}>
                  {primaryFocusLabel}
                </span>
              }
            />
          </div>
          <PatientOptimizationSnapshot optimization={optimization} />
        </Surface>
      )}

      {outcome?.consistency_warnings && outcome.consistency_warnings.length > 0 && (
        <Surface variant="soft" padding="md" className="space-y-2">
          <Eyebrow tone="primary">Consistency note</Eyebrow>
          {outcome.consistency_warnings.map((warning, index) => (
            <p key={index} className="text-xs text-[var(--text-secondary)]">
              {warning}
            </p>
          ))}
        </Surface>
      )}

      {outcome?.drg_summary && outcome.drg_summary.n_episodes > 0 && (
        <Surface variant="base" padding="lg">
          <DRGPanel data={outcome.drg_summary} />
        </Surface>
      )}
    </div>
  );
}
