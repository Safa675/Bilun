"use client";

import type { BillingActionReport } from "@/lib/domains/sut";
import { useT } from "@/lib/i18n/useTranslations";
import { getModuleLocale } from "@/lib/i18n/localeModule";
import { translateApiText } from "@/lib/apiMessages";
import { isExactOutput } from "@/lib/sutExactness";
import { ExactnessBlock as ExactnessNotice } from "@/components/primitives";
import { WRAPPED_HEADER_STYLE, BillingSectionShell, TableWrap } from "./shared";

function localizedCorrectiveSteps(
  item: {
    corrective_steps_tr?: string[];
    corrective_steps_en?: string[];
  },
): string[] {
  const locale = getModuleLocale();
  if (locale === "en") {
    return item.corrective_steps_en ?? item.corrective_steps_tr ?? [];
  }
  return item.corrective_steps_tr ?? item.corrective_steps_en ?? [];
}

export function MedulaRejectionPlaybookSection({
  playbookData,
}: {
  playbookData: NonNullable<BillingActionReport["medula_rejection_playbook"]>;
}) {
  const t = useT();
  const playbookExact = isExactOutput(playbookData);
  const entries = playbookData.entries ?? [];

  if (entries.length === 0) {
    return null;
  }

  const entryCount = playbookData.entry_count ?? entries.length;

  return (
    <BillingSectionShell
      id="medula-playbook"
      title={t("billing.medulaPlaybook.title")}
      total={String(entryCount)}
    >
      <p className="mb-3 text-sm leading-relaxed text-[var(--text-secondary)]">
        {t("billing.medulaPlaybook.scopeFootnote")}
      </p>
      {!playbookExact && (
        <ExactnessNotice block={playbookData} fallback={t("billing.medulaPlaybook.unavailable")} className="mb-4" />
      )}
      <TableWrap minWidth={1180}>
        <thead>
          <tr>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.medulaPlaybook.claim")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.medulaPlaybook.stage")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.medulaPlaybook.code")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.medulaPlaybook.message")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.medulaPlaybook.procedure")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.medulaPlaybook.sutAnchor")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.medulaPlaybook.rebill")}</th>
            <th style={WRAPPED_HEADER_STYLE}>{t("billing.medulaPlaybook.steps")}</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((item, index) => (
            <tr key={`${item.claim_id}-${item.rejection_event_id}-${index}`}>
              <td className="font-semibold text-slate-950">{item.claim_id ?? "—"}</td>
              <td>{item.medula_stage ? translateApiText(item.medula_stage) : "—"}</td>
              <td className="font-mono text-xs">{item.sonuc_kodu ?? "—"}</td>
              <td>{item.hata_mesaji ? translateApiText(item.hata_mesaji) : "—"}</td>
              <td>
                <div className="font-mono text-xs">
                  {item.related_line_type === "procedure" && item.related_procedure_code
                    ? item.related_procedure_code
                    : item.related_line_id ?? "—"}
                </div>
                {item.related_line_type && item.related_line_type !== "procedure" && (
                  <div className="text-[0.65rem] font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                    {t(`billing.medulaPlaybook.lineType.${item.related_line_type}`)}
                  </div>
                )}
              </td>
              <td>{item.sut_anchor ?? "—"}</td>
              <td>{item.rebill_permitted ? t("billing.medulaPlaybook.yes") : t("billing.medulaPlaybook.no")}</td>
              <td>
                <ul className="list-disc space-y-1 pl-4 text-sm">
                  {localizedCorrectiveSteps(item).map((step, stepIndex) => (
                    <li key={`${item.playbook_id}-step-${stepIndex}`}>{step}</li>
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
