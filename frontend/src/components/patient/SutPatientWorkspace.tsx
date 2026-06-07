"use client";

import Link from "next/link";
import { ArrowLeft, ShieldAlert } from "lucide-react";
import type {
  CopayExemptionResult,
  PatientOptimization,
  SutPatientOutcomeData,
} from "@/lib/domains/sut";
import { buildSutHomeHref } from "@/lib/constants";
import { DRGPanel } from "@/components/tabs/sut/PatientSection";
import { fmtNum, fmtPctRatio } from "@/components/tabs/sut/shared";
import { getUnavailableMessage, isExactOutput } from "@/lib/sutExactness";
import { translateConsistencyWarning } from "@/lib/apiMessages";
import { theme } from "@/lib/theme";
import { ExemptionBasisChips } from "@/components/sut/ExemptionBasisChips";
import { Chip, Eyebrow, Stat, Surface } from "@/components/primitives";
import {
  formatExemptionBasisSummary,
  getExemptionCategories,
  hasEk1aExemption,
} from "@/lib/copayExemption";
import { useT } from "@/lib/i18n/useTranslations";

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
  const t = useT();
  const topMatch = copay.qualifying_diagnoses[0];
  const categories = getExemptionCategories(copay);
  const basisSummary = formatExemptionBasisSummary(categories);
  const ek1aOnly =
    copay.exempt && categories.length > 0 && categories.every((c) => c === "ek1a_chronic");
  const codeWord =
    copay.n_qualifying === 1
      ? t("patient.workspace.copayCodeSingular")
      : t("patient.workspace.copayCodePlural");

  return (
    <Surface variant="soft" padding="md" className="space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <Eyebrow>{t("patient.workspace.copayEyebrow")}</Eyebrow>
          <p className="mt-2 font-[var(--font-display)] text-lg font-medium tracking-tight text-[var(--text-primary)]">
            {copay.exempt ? t("patient.workspace.copayEligible") : t("patient.workspace.copayNoMatch")}
          </p>
          <p className="mt-2 text-sm leading-snug text-[var(--text-secondary)]">
            {copay.exempt
              ? ek1aOnly
                ? t("patient.workspace.copayEk1a", {
                    count: fmtNum(copay.n_qualifying),
                    codeWord,
                  })
                : basisSummary
                  ? t("patient.workspace.copayWaiverGrounds", { basis: basisSummary })
                  : t("patient.workspace.copayGenericMatch")
              : t("patient.workspace.copayNoInputs")}
          </p>
          {copay.exempt && categories.length > 0 && (
            <div className="mt-3">
              <ExemptionBasisChips copay={copay} />
            </div>
          )}
        </div>
        <Chip variant={copay.exempt ? "success" : "neutral"}>
          {copay.exempt ? t("patient.workspace.chipActionable") : t("patient.workspace.chipClear")}
        </Chip>
      </div>

      {topMatch && hasEk1aExemption(categories) && (
        <Surface variant="base" padding="sm" className="text-sm">
          <p className="font-semibold text-[var(--text-primary)]">{topMatch.disease}</p>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">
            {t("patient.workspace.topMatchDetail", {
              icd10: topMatch.icd10,
              range: topMatch.range,
            })}
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
  const t = useT();
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
            {t("patient.workspace.optimizationTitle")}
          </h2>
          <p className="mt-1 text-sm leading-snug text-[var(--text-secondary)]">
            {t("patient.workspace.optimizationDescription")}
          </p>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <CopayExemptionSummary copay={optimization.copay_exemptions} />

        <OptimizationCard title={t("patient.workspace.surchargeTitle")}>
          {surchargeExact ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <Stat
                label={t("patient.workspace.applicableProcedures")}
                value={fmtNum(optimization.surcharge_exposure.n_applicable_procedures ?? 0)}
              />
              <Stat
                label={t("patient.workspace.exposureRate")}
                value={fmtPctRatio(optimization.surcharge_exposure.exposure_rate ?? 0, 1)}
              />
            </div>
          ) : (
            <ExactnessNotice
              block={optimization.surcharge_exposure}
              fallback={t("patient.workspace.surchargeFallback")}
            />
          )}
        </OptimizationCard>

        <OptimizationCard title={t("patient.workspace.copayRateTitle")}>
          {copayRateExact ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <Stat
                label={t("patient.workspace.applicableProcedures")}
                value={fmtNum(optimization.copay_rate_exposure.n_applicable_procedures ?? 0)}
              />
              <Stat
                label={t("patient.workspace.meanRate")}
                value={fmtPctRatio((optimization.copay_rate_exposure.mean_rate ?? 0) / 100, 1)}
              />
            </div>
          ) : (
            <ExactnessNotice
              block={optimization.copay_rate_exposure}
              fallback={t("patient.workspace.copayRateFallback")}
            />
          )}
        </OptimizationCard>

        <OptimizationCard title={t("patient.workspace.drgTitle")}>
          {drgExact ? (
            <div className="space-y-3">
              <Stat
                label={t("patient.workspace.chaptersAnalyzed")}
                value={fmtNum(optimization.drg_unbundling?.n_chapters_analyzed ?? 0)}
              />
              <Stat
                label={t("patient.workspace.riskState")}
                value={
                  optimization.drg_unbundling?.has_unbundling_risk
                    ? t("patient.workspace.riskOpportunity")
                    : t("patient.workspace.riskNone")
                }
              />
              {optimization.drg_unbundling?.has_unbundling_risk ? (
                <Chip variant="warning">{t("patient.workspace.reviewPackage")}</Chip>
              ) : null}
            </div>
          ) : (
            <ExactnessNotice
              block={optimization.drg_unbundling}
              fallback={t("patient.workspace.drgFallback")}
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
  const t = useT();
  const primaryFocusLabel = optimization?.copay_exemptions.exempt
    ? t("patient.workspace.focusCopay")
    : t("patient.workspace.focusExactness");
  const primaryFocusColor = optimization?.copay_exemptions.exempt
    ? theme.accent
    : undefined;

  return (
    <div className="space-y-6">
      <Surface variant="base" padding="lg">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <Eyebrow>{t("patient.workspace.eyebrow")}</Eyebrow>
            <h1 className="mt-2 font-[var(--font-display)] text-3xl font-medium leading-tight tracking-tight text-[var(--text-primary)] sm:text-4xl">
              {t("patient.workspace.billingTitle")}{" "}
              <em className="not-italic font-[var(--font-display)] italic text-[var(--gold)]">
                {t("patient.workspace.billingEmphasis")}
              </em>
            </h1>
            <p className="mt-2 font-mono text-base text-[var(--text-secondary)]">{patientId}</p>
            <p className="mt-3 max-w-3xl text-sm leading-relaxed text-[var(--text-secondary)]">
              {t("patient.workspace.description")}
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <Link href={buildSutHomeHref("patients")} className="sut-section-btn">
              <ArrowLeft className="h-4 w-4" />
              {t("patient.workspace.backToPatients")}
            </Link>
          </div>
        </div>
      </Surface>

      {optimization && (
        <Surface variant="base" padding="lg" className="space-y-6">
          <div className="grid gap-6 sm:grid-cols-3">
            <Stat
              label={t("patient.workspace.diagnoses")}
              value={fmtNum(optimization.n_diagnoses)}
              display="gold"
            />
            <Stat
              label={t("patient.workspace.icdChapters")}
              value={
                optimization.icd10_chapters.length > 0
                  ? optimization.icd10_chapters.join(", ")
                  : t("patient.workspace.icdNone")
              }
            />
            <Stat
              label={t("patient.workspace.primaryFocus")}
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
          <Eyebrow tone="primary">{t("patient.workspace.consistencyEyebrow")}</Eyebrow>
          {outcome.consistency_warnings.map((warning, index) => (
            <p key={index} className="text-xs text-[var(--text-secondary)]">
              {translateConsistencyWarning(warning)}
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
