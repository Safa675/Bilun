"use client";

import type { PatientOptimization } from "@/lib/domains/sut";
import { getSutAlertBadgeLabel } from "@/lib/sutLabels";
import { useT } from "@/lib/i18n/useTranslations";
import { isExactOutput } from "@/lib/sutExactness";
import { ExemptionBasisChips } from "@/components/sut/ExemptionBasisChips";
import { Chip, ExactnessBlock as ExactnessNotice, Eyebrow } from "@/components/primitives";
import { getExemptionCategories } from "@/lib/copayExemption";
import { fmtNum, fmtRiskLabel, fmtTRY2OrUnavailable } from "@/components/tabs/sut/shared";
import { BillingSectionShell } from "./shared";

function MoneyHint({ labelKey, amount }: { labelKey: string; amount: number | null | undefined }) {
  const t = useT();
  const marker = "__bilun_money__";
  const [before, after] = t(labelKey, { amount: marker }).split(marker);
  return (
    <p className="text-xs text-[var(--text-secondary)]">
      {before}<span className="whitespace-nowrap tabular-nums">{fmtTRY2OrUnavailable(amount)}</span>{after}
    </p>
  );
}

export function SutOptimizationSection({ optimization }: { optimization: PatientOptimization }) {
  const t = useT();
  const surchargeExact = isExactOutput(optimization.surcharge_exposure);
  const rateExact = isExactOutput(optimization.copay_rate_exposure);
  const drgExact = isExactOutput(optimization.drg_unbundling);
  const surchargeCount = optimization.surcharge_exposure.n_applicable_procedures;
  const rateCount = optimization.copay_rate_exposure.n_applicable_procedures;
  const drgRiskLabel = optimization.drg_unbundling?.has_unbundling_risk ? fmtRiskLabel("high") : fmtRiskLabel("low");

  return (
    <BillingSectionShell title={t("billing.sutOptimization.title")}>
      <dl data-sut-optimization-summary className="@container/optimization space-y-3">
        <div data-optimization-metric="copay" className="grid min-w-0 grid-cols-1 items-start gap-x-6 gap-y-2 @min-[400px]/optimization:grid-cols-[minmax(0,1fr)_auto]">
          <dt><Eyebrow className="tracking-normal">{t("billing.sutOptimization.copayEyebrow")}</Eyebrow></dt>
          <dd className="min-w-0 space-y-2 @min-[400px]/optimization:max-w-80">
          <div className="flex flex-wrap items-center gap-2">
            <Chip variant={optimization.copay_exemptions.exempt ? "success" : "neutral"}>
              {optimization.copay_exemptions.exempt
                ? getSutAlertBadgeLabel("exempt")
                : getSutAlertBadgeLabel("notExempt")}
            </Chip>
            {optimization.copay_exemptions.exempt && (
              <ExemptionBasisChips copay={optimization.copay_exemptions} max={3} />
            )}
          </div>
          <p className="text-xs text-[var(--text-secondary)]">
            {getExemptionCategories(optimization.copay_exemptions).includes("ek1a_chronic")
              ? t("billing.sutOptimization.ek1aQualifying", {
                  count: fmtNum(optimization.copay_exemptions.qualifying_diagnoses.length),
                })
              : optimization.copay_exemptions.exempt
                ? t("billing.sutOptimization.exemptStatusVisit")
                : t("billing.sutOptimization.noWaiver")}
          </p>
          </dd>
        </div>

        <div data-optimization-metric="surcharge" className="grid min-w-0 grid-cols-1 items-start gap-x-6 gap-y-2 @min-[400px]/optimization:grid-cols-[minmax(0,1fr)_auto]">
          <dt><Eyebrow className="tracking-normal">{t("billing.sutOptimization.surchargeEyebrow")}</Eyebrow></dt>
          <dd className="min-w-0 space-y-2 @min-[400px]/optimization:max-w-80">
          <Chip
            variant={
              !surchargeExact
                ? "neutral"
                : (surchargeCount ?? 0) > 0
                  ? "warning"
                  : "success"
            }
          >
            {surchargeExact
              ? ((surchargeCount ?? 0) > 0
                ? t("billing.sutOptimization.flags", { count: fmtNum(surchargeCount ?? 0) })
                : getSutAlertBadgeLabel("clear"))
              : getSutAlertBadgeLabel("unavailable")}
          </Chip>
          {!surchargeExact && (
            <ExactnessNotice
              block={optimization.surcharge_exposure}
              fallback={t("billing.sutOptimization.surchargeUnavailable")}
            />
          )}
          </dd>
        </div>

        <div data-optimization-metric="copay-rate" className="grid min-w-0 grid-cols-1 items-start gap-x-6 gap-y-2 @min-[400px]/optimization:grid-cols-[minmax(0,1fr)_auto]">
          <dt><Eyebrow className="tracking-normal">{t("billing.sutOptimization.copayRateEyebrow")}</Eyebrow></dt>
          <dd className="min-w-0 space-y-2 @min-[400px]/optimization:max-w-80">
          <p className="text-sm font-semibold text-[var(--text-primary)]">
            {rateExact
              ? ((rateCount ?? 0) > 0
                ? t("billing.sutOptimization.cappedProcedures", { count: fmtNum(rateCount ?? 0) })
                : t("billing.sutOptimization.noRateCaps"))
              : t("common.unavailable")}
          </p>
          {!rateExact && (
            <ExactnessNotice
              block={optimization.copay_rate_exposure}
              fallback={t("billing.sutOptimization.copayRateUnavailable")}
            />
          )}
          </dd>
        </div>

        {optimization.drg_unbundling && (
          <div data-optimization-metric="drg" className="grid min-w-0 grid-cols-1 items-start gap-x-6 gap-y-2 @min-[400px]/optimization:grid-cols-[minmax(0,1fr)_auto]">
            <dt><Eyebrow className="tracking-normal">{t("billing.sutOptimization.drgEyebrow")}</Eyebrow></dt>
            <dd className="min-w-0 space-y-2 @min-[400px]/optimization:max-w-80">
            <Chip
              variant={
                !drgExact
                  ? "neutral"
                  : optimization.drg_unbundling.has_unbundling_risk
                    ? "danger"
                    : "success"
              }
            >
              {drgExact ? drgRiskLabel : getSutAlertBadgeLabel("unavailable")}
            </Chip>
            {drgExact ? (
              <>
                <MoneyHint labelKey="billing.sutOptimization.recoverableSavings" amount={optimization.drg_unbundling.total_potential_savings} />
                {(optimization.drg_unbundling.total_sourced_savings ?? 0) > 0 && (
                  <MoneyHint labelKey="billing.sutOptimization.drgSourcedSavings" amount={optimization.drg_unbundling.total_sourced_savings} />
                )}
              </>
            ) : (
              <ExactnessNotice
                block={optimization.drg_unbundling}
                fallback={t("billing.sutOptimization.drgUnavailable")}
              />
            )}
            </dd>
          </div>
        )}
      </dl>
    </BillingSectionShell>
  );
}
