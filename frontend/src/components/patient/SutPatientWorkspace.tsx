"use client";

import Link from "next/link";
import { ArrowLeft, ShieldAlert } from "lucide-react";
import type {
  CopayExemptionResult,
  BillingActionReport,
  PatientClaimSummary,
  PatientOptimization,
  SutPatientOutcomeData,
} from "@/lib/domains/sut";
import { PatientFinancialSummary } from "@/components/patient/PatientFinancialSummary";
import { buildSutHomeHref } from "@/lib/constants";
import { fmtNum, fmtPctRatio } from "@/components/tabs/sut/shared";
import { getUnavailableMessage, isExactOutput } from "@/lib/sutExactness";
import { theme } from "@/lib/theme";
import { ExemptionBasisChips } from "@/components/sut/ExemptionBasisChips";
import { PatientExemptionRuleSourceAttribution } from "@/components/sut/RegulatorySourceChips";
import { Chip, Eyebrow, ExactnessBlock, Stat, Surface, Button } from "@/components/primitives";
import {
  formatExemptionBasisSummary,
  getExemptionCategories,
  hasEk1aExemption,
} from "@/lib/copayExemption";
import { useT } from "@/lib/i18n/useTranslations";

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
  const basisSummary = formatExemptionBasisSummary(categories, t);
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
          <p className="mt-2 font-display text-lg font-medium tracking-normal text-[var(--text-primary)]">
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
            <div className="mt-3 space-y-2">
              <ExemptionBasisChips copay={copay} />
              <PatientExemptionRuleSourceAttribution copay={copay} />
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
          <h2 className="font-display text-lg font-medium tracking-normal text-[var(--text-primary)]">
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
            <ExactnessBlock
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
            <ExactnessBlock
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
            <ExactnessBlock
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
  billingReport,
  selectedClaimId = null,
  claimCount,
  selectedClaimSummary = null,
}: {
  patientId: string;
  outcome: SutPatientOutcomeData | null;
  optimization: PatientOptimization | null;
  billingReport?: BillingActionReport | null;
  selectedClaimId?: string | null;
  claimCount?: number;
  selectedClaimSummary?: PatientClaimSummary | null;
}) {
  const t = useT();

  return (
    <div className="space-y-4">
      <Surface variant="base" padding="md">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <Eyebrow>{t("patient.workspace.eyebrow")}</Eyebrow>
            <h1 className="mt-1 font-display text-2xl font-medium leading-tight tracking-normal text-[var(--text-primary)] sm:text-3xl">
              {t("patient.workspace.billingTitle")}{" "}
              <em className="not-italic font-display italic text-[var(--gold)]">
                {t("patient.workspace.billingEmphasis")}
              </em>
            </h1>
            <p className="mt-1 font-mono text-xs text-[var(--text-secondary)]">{patientId}</p>
            <p className="sr-only">
              {t("patient.workspace.description")}
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <Button asChild variant="secondary" className="max-w-full whitespace-normal text-left">
              <Link href={buildSutHomeHref("patients")}>
                <ArrowLeft className="h-4 w-4 shrink-0" />
                {t("patient.workspace.backToPatients")}
              </Link>
            </Button>
          </div>
        </div>
      </Surface>

      <PatientFinancialSummary
        outcome={outcome}
        billingReport={billingReport ?? null}
        selectedClaimId={selectedClaimId}
        claimCount={claimCount}
        selectedClaimSummary={selectedClaimSummary}
      />
    </div>
  );
}

export function PatientClinicalSnapshot({ optimization }: { optimization: PatientOptimization }) {
  const t = useT();
  const statuses = [...new Set([
    optimization.surcharge_exposure.exactness_status,
    optimization.copay_rate_exposure.exactness_status,
    optimization.drg_unbundling?.exactness_status,
  ].map((status) => status ? t(`billing.recommendedActions.exactness.${status}`) : t("common.unavailable")))];
  const primaryFocusLabel = optimization.copay_exemptions.exempt
    ? t("patient.workspace.focusCopay")
    : t("patient.workspace.focusExactness");
  const primaryFocusColor = optimization.copay_exemptions.exempt
    ? theme.accent
    : undefined;

  return (
    <details className="rounded-[var(--r-lg)] border border-[var(--border-subtle)] p-3">
      <summary className="cursor-pointer text-sm font-semibold text-[var(--text-primary)]">
        {t("patient.workspace.clinicalSnapshotEyebrow")} · {t("patient.workspace.diagnoses")}: <span className="tabular-nums">{fmtNum(optimization.n_diagnoses)}</span>
        <span className="mt-1 block text-xs font-normal text-[var(--text-secondary)]">{statuses.join(" · ")}</span>
      </summary>
      <div className="mt-3">
  <Surface variant="soft" padding="lg" className="space-y-6">
    <div>
      <Eyebrow>{t("patient.workspace.clinicalSnapshotEyebrow")}</Eyebrow>
      <p className="mt-1 text-sm leading-snug text-[var(--text-secondary)]">
        {t("patient.workspace.clinicalSnapshotDescription")}
      </p>
    </div>
    <div className="grid gap-6 sm:grid-cols-3">
      <Stat
        label={t("patient.workspace.diagnoses")}
        value={fmtNum(optimization.n_diagnoses)}
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
      </div>
    </details>
  );
}
