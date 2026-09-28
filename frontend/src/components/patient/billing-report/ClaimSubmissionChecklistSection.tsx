"use client";

import type { BillingActionReport, ClaimSubmissionChecklist } from "@/lib/domains/sut";
import { getSutSeverityLabel } from "@/lib/sutLabels";
import { useT } from "@/lib/i18n/useTranslations";
import { getModuleLocale } from "@/lib/i18n/localeModule";
import { isExactOutput } from "@/lib/sutExactness";
import { ExactnessBlock as ExactnessNotice } from "@/components/primitives";
import { WRAPPED_HEADER_STYLE, BillingSectionShell, TableWrap } from "./shared";

function localizedReadinessReminder(item: {
  reminder_tr?: string;
  reminder_en?: string;
}): string {
  const locale = getModuleLocale();
  if (locale === "en") {
    return item.reminder_en ?? item.reminder_tr ?? "—";
  }
  return item.reminder_tr ?? item.reminder_en ?? "—";
}

function localizedPreventiveSteps(
  item: {
    preventive_steps_tr?: string[];
    preventive_steps_en?: string[];
  },
): string[] {
  const locale = getModuleLocale();
  if (locale === "en") {
    return item.preventive_steps_en ?? item.preventive_steps_tr ?? [];
  }
  return item.preventive_steps_tr ?? item.preventive_steps_en ?? [];
}

export function ClaimSubmissionChecklistSection({
  checklistData,
}: {
  checklistData: NonNullable<BillingActionReport["claim_submission_checklist"]>;
}) {
  const t = useT();
  const checklistExact = isExactOutput(checklistData);
  const items = checklistData.items ?? [];

  if (items.length === 0) {
    return null;
  }

  const itemCount = checklistData.item_count ?? items.length;

  return (
    <BillingSectionShell
      id="claim-submission-checklist"
      title={t("billing.claimChecklist.title")}
      total={String(itemCount)}
    >
      <p className="mb-3 text-sm leading-relaxed text-[var(--text-secondary)]">
        {t("billing.claimChecklist.scopeFootnote")}
      </p>
      {!checklistExact && (
        <ExactnessNotice block={checklistData} fallback={t("billing.claimChecklist.unavailable")} className="mb-4" />
      )}
      <TableWrap minWidth={1120}>
        <thead>
          <tr>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.claimChecklist.claim")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.claimChecklist.line")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.claimChecklist.medulaRisk")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.claimChecklist.severity")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.claimChecklist.reminder")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.claimChecklist.sutAnchor")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.claimChecklist.steps")}</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item: ClaimSubmissionChecklist["items"][number], index: number) => (
            <tr key={`${item.claim_id}-${item.line_id}-${index}`}>
              <td className="font-semibold text-slate-950">{item.claim_id ?? "—"}</td>
              <td>
                <div>{item.line_name ?? "—"}</div>
                <div className="font-mono text-xs">{item.line_code ?? "—"}</div>
              </td>
              <td className="font-mono text-xs">{item.sonuc_kodu_risk ?? "—"}</td>
              <td>{item.severity ? getSutSeverityLabel(item.severity) : "—"}</td>
              <td>{localizedReadinessReminder(item)}</td>
              <td>{item.sut_anchor ?? "—"}</td>
              <td>
                <ul className="list-disc space-y-1 pl-4 text-sm">
                  {localizedPreventiveSteps(item).map((step, stepIndex) => (
                    <li key={`${item.checklist_id}-step-${stepIndex}`}>{step}</li>
                  ))}
                </ul>
              </td>
            </tr>
          ))}
        </tbody>
      </TableWrap>
    </BillingSectionShell>
  );
}
