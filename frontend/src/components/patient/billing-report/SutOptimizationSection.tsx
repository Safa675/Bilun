"use client";

import type { PatientOptimization } from "@/lib/domains/sut";
import { getSutAlertBadgeLabel } from "@/lib/sutLabels";
import { useT } from "@/lib/i18n/useTranslations";
import { isExactOutput } from "@/lib/sutExactness";
import { ExemptionBasisChips } from "@/components/sut/ExemptionBasisChips";
import { Chip, ExactnessBlock as ExactnessNotice, Eyebrow, Surface } from "@/components/primitives";
import { getExemptionCategories } from "@/lib/copayExemption";
import { fmtNum, fmtRiskLabel, fmtTRY2OrUnavailable } from "@/components/tabs/sut/shared";
import { BillingSectionShell } from "./shared";

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
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <Surface variant="soft" padding="md" className="space-y-2">
          <Eyebrow>{t("billing.sutOptimization.copayEyebrow")}</Eyebrow>
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
        </Surface>

        <Surface variant="soft" padding="md" className="space-y-2">
          <Eyebrow>{t("billing.sutOptimization.surchargeEyebrow")}</Eyebrow>
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
        </Surface>

        <Surface variant="soft" padding="md" className="space-y-2">
          <Eyebrow>{t("billing.sutOptimization.copayRateEyebrow")}</Eyebrow>
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
        </Surface>

        {optimization.drg_unbundling && (
          <Surface variant="soft" padding="md" className="space-y-2">
            <Eyebrow>{t("billing.sutOptimization.drgEyebrow")}</Eyebrow>
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
                <p className="text-xs text-[var(--text-secondary)]">
                  {t("billing.sutOptimization.recoverableSavings", {
                    amount: fmtTRY2OrUnavailable(optimization.drg_unbundling.total_potential_savings),
                  })}
                </p>
                {(optimization.drg_unbundling.total_sourced_savings ?? 0) > 0 && (
                  <p className="text-xs text-[var(--text-secondary)]">
                    {t("billing.sutOptimization.drgSourcedSavings", {
                      amount: fmtTRY2OrUnavailable(optimization.drg_unbundling.total_sourced_savings),
                    })}
                  </p>
                )}
              </>
            ) : (
              <ExactnessNotice
                block={optimization.drg_unbundling}
                fallback={t("billing.sutOptimization.drgUnavailable")}
              />
            )}
          </Surface>
        )}
      </div>
    </BillingSectionShell>
  );
}
