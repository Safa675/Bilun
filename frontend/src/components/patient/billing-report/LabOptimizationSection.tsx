"use client";

import type { BillingActionReport } from "@/lib/domains/sut";
import { useT } from "@/lib/i18n/useTranslations";
import { isExactOutput } from "@/lib/sutExactness";
import { Chip, ExactnessBlock as ExactnessNotice } from "@/components/primitives";
import { fmtLabel, fmtTRY2, fmtTRY2OrUnavailable } from "@/components/tabs/sut/shared";
import { WRAPPED_HEADER_STYLE, chipVariantFromColor, BillingSectionShell, TableWrap } from "./shared";

export function LabOptimizationSection({ labData }: { labData: BillingActionReport["lab"] }) {
  const t = useT();
  if (!isExactOutput(labData)) {
    return (
      <BillingSectionShell id="billing-lab" title={t("billing.lab.title")}>
        <ExactnessNotice block={labData} fallback={t("billing.lab.unavailable")} />
      </BillingSectionShell>
    );
  }

  if (labData.flagged_tests.length === 0) {
    return null;
  }

  const combinedSavings = labData.hemogram_bundling_savings == null || labData.session_fraction_savings == null
    ? null
    : labData.hemogram_bundling_savings + labData.session_fraction_savings;

  return (
    <BillingSectionShell id="billing-lab" title={t("billing.lab.title")} total={combinedSavings == null ? "—" : fmtTRY2(combinedSavings)}>
      <TableWrap minWidth={820}>
        <thead>
          <tr>
            <th>{t("billing.lab.test")}</th>
            <th>{t("billing.lab.sutCode")}</th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.lab.gazettePrice")}</th>
            <th>{t("billing.lab.flag")}</th>
            <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.lab.savings")}</th>
          </tr>
        </thead>
        <tbody>
          {labData.flagged_tests.map((test, index) => (
            <tr key={`${test.sut_code}-${index}`}>
              <td>{test.test_name}</td>
              <td className="font-mono text-xs">{test.sut_code}</td>
              <td className="num-col tabular-nums text-right">{fmtTRY2(test.gazette_price)}</td>
              <td>
                <Chip
                  variant={chipVariantFromColor(
                    test.flag_type === "hemogram_unbundling"
                      ? "#D97706"
                      : test.flag_type === "session_fraction_overbilling"
                        ? "#B45309"
                        : "#B91C1C",
                  )}
                >
                  {fmtLabel(test.flag_type)}
                </Chip>
              </td>
              <td className="num-col tabular-nums text-right font-semibold text-[var(--text-primary)]">
                {fmtTRY2OrUnavailable(test.savings_try ?? null)}
              </td>
            </tr>
          ))}
        </tbody>
      </TableWrap>
    </BillingSectionShell>
  );
}
