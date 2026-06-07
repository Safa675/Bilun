"use client";

import { theme } from "@/lib/theme";
import type { OptimizationSummary } from "@/lib/domains/sut";
import {
  ACCENT_LOCAL,
  fmtNum,
  fmtPct,
  fmtTRY2,
  fmtPctRatio,
  KpiCard,
  MethodologyBadge,
} from "../shared";
import { DataTable, Surface } from "@/components/primitives";
import { useT } from "@/lib/i18n/useTranslations";
import { translateMethodology } from "@/lib/apiMessages";

export function TemporalPriceSection({ data }: { data: OptimizationSummary }) {
  const t = useT();
  const temporal = data.temporal_price_validation;

  if (!temporal) {
    return (
      <Surface variant="base" padding="lg" className="text-center">
        <p className="text-sm text-[var(--text-secondary)]">{t("sections.temporalPrice.notAvailable")}</p>
      </Surface>
    );
  }

  const { ek2b, ek2c } = temporal;
  const dateLabels = ek2b.effective_dates?.length > 0 ? ek2b.effective_dates : ek2c.effective_dates ?? [];

  return (
    <div className="space-y-5">
      <MethodologyBadge
        text={translateMethodology(temporal.methodology)}
        badgeLabel={t("sections.temporalPrice.gazetteDataBadge")}
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard
          label={t("sections.temporalPrice.kpi.procedureCodes")}
          value={fmtNum(ek2b.n_codes)}
          sub={t("sections.temporalPrice.kpi.gazetteDatesSub", { count: fmtNum(ek2b.n_effective_dates) })}
        />
        <KpiCard
          label={t("sections.temporalPrice.kpi.packageCodes")}
          value={fmtNum(ek2c.n_codes)}
          sub={t("sections.temporalPrice.kpi.gazetteDatesSub", { count: fmtNum(ek2c.n_effective_dates) })}
        />
        <KpiCard
          label={t("sections.temporalPrice.kpi.codesWithChanges")}
          value={fmtNum(ek2b.n_codes_with_changes + ek2c.n_codes_with_changes)}
          valueColor="#B45309"
          sub={t("sections.temporalPrice.kpi.changesSub", {
            procRate: fmtPctRatio(ek2b.price_change_rate),
            pkgRate: fmtPctRatio(ek2c.price_change_rate),
          })}
        />
        <KpiCard
          label={t("sections.temporalPrice.kpi.meanPriceDelta")}
          value={`${ek2b.mean_price_delta_pct > 0 ? "+" : ""}${fmtPct(ek2b.mean_price_delta_pct)}`}
          valueColor={ek2b.mean_price_delta_pct > 0 ? "#B91C1C" : theme.accent}
          sub={t("sections.temporalPrice.kpi.meanDeltaSub")}
        />
      </div>

      {dateLabels.length > 0 && (
        <Surface variant="base" padding="md">
          <div className="text-xs font-bold uppercase tracking-wider mb-2" style={{ color: "#A1A1AA" }}>
            {t("sections.temporalPrice.gazetteAmendmentTimeline")}
          </div>
          <div className="flex flex-wrap gap-2">
            {dateLabels.map((d: string) => (
              <span key={d} className="inline-block px-2 py-0.5 rounded text-xs font-medium" style={{ background: theme.accentAlpha(0.08), color: ACCENT_LOCAL }}>
                {d}
              </span>
            ))}
          </div>
        </Surface>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <PriceChangeTable title={t("sections.temporalPrice.topProcedureIncreases")} items={ek2b.top_increases} direction="up" t={t} />
        <PriceChangeTable title={t("sections.temporalPrice.topPackageIncreases")} items={ek2c.top_increases} direction="up" t={t} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <PriceChangeTable title={t("sections.temporalPrice.topProcedureDecreases")} items={ek2b.top_decreases} direction="down" t={t} />
        <PriceChangeTable title={t("sections.temporalPrice.topPackageDecreases")} items={ek2c.top_decreases} direction="down" t={t} />
      </div>
    </div>
  );
}

function PriceChangeTable({
  title,
  items,
  direction,
  t,
}: {
  title: string;
  items: { code: string; name: string; old_price: number; new_price: number; delta_pct: number; old_date?: string; new_date?: string }[];
  direction: "up" | "down";
  t: ReturnType<typeof useT>;
}) {
  const color = direction === "up" ? "#B91C1C" : theme.accent;
  const fmtDate = (d?: string) => d ? d.slice(0, 10) : t("sections.temporalPrice.missingDate");
  return (
    <Surface variant="base" padding="md">
      <div className="text-xs font-bold uppercase tracking-wider mb-3" style={{ color }}>
        {title}
      </div>
      {items.length > 0 ? (
        <DataTable className="text-xs">
          <thead>
            <tr>
              <th>{t("sections.temporalPrice.table.code")}</th>
              <th>{t("sections.temporalPrice.table.name")}</th>
              <th className="num-col">{t("sections.temporalPrice.table.priceAtDate", { date: fmtDate(items[0]?.old_date) })}</th>
              <th className="num-col">{t("sections.temporalPrice.table.priceAtDate", { date: fmtDate(items[0]?.new_date) })}</th>
              <th className="num-col">{t("sections.temporalPrice.table.change")}</th>
            </tr>
          </thead>
          <tbody>
            {items.slice(0, 8).map((item, i) => (
              <tr key={i}>
                <td className="font-mono" style={{ color: ACCENT_LOCAL }}>{item.code}</td>
                <td className="truncate max-w-[180px]" title={item.name}>{item.name}</td>
                <td className="num-col">{fmtTRY2(item.old_price)}</td>
                <td className="num-col">{fmtTRY2(item.new_price)}</td>
                <td className="num-col font-bold" style={{ color }}>
                  {direction === "up" ? "+" : ""}{fmtPct(item.delta_pct)}
                </td>
              </tr>
            ))}
          </tbody>
        </DataTable>
      ) : (
        <p className="text-sm text-[var(--text-secondary)]">
          {direction === "up" ? t("sections.temporalPrice.noIncreases") : t("sections.temporalPrice.noDecreases")}
        </p>
      )}
    </Surface>
  );
}
