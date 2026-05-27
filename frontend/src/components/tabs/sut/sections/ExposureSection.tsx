"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  ResponsiveContainer,
  PieChart,
  Pie,
} from "recharts";
import type { ExposureSummaryResponse } from "@/lib/domains/sut";
import { theme } from "@/lib/theme";
import {
  fmtTRY,
  fmtTRY2,
  fmtPct,
  fmtNum,
  KpiCard,
  TIER_COLORS,
  CATEGORY_COLORS,
  ACCENT_LOCAL,
} from "../shared";
import { DataTable, Surface } from "@/components/primitives";

export function RevenueExposureSection({ data }: { data: ExposureSummaryResponse }) {
  const sut = data.sut_summary;
  const sgk = sut.sgk_exposure;
  const copay = sut.copayment;
  const conc = sut.high_cost_concentration;

  const tierData = Object.entries(sut.tier_distribution)
    .map(([name, count]) => ({ name, value: count, color: TIER_COLORS[name] || "#A1A1AA" }))
    .sort((a, b) => b.value - a.value);

  const categoryData = Object.entries(sut.category_totals).map(([key, range]) => {
    const mid = ((range.min + range.max) / 2);
    return { name: key.charAt(0).toUpperCase() + key.slice(1), value: Math.round(mid), color: CATEGORY_COLORS[key] || ACCENT_LOCAL };
  });

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard
          label="Total SGK Exposure"
          value={fmtTRY(sgk?.total_sgk_exposure_mid ?? 0)}
          valueColor="#B91C1C"
          sub={`${fmtNum(sut.n_patients)} patients`}
        />
        <KpiCard
          label="Mean SGK / Patient"
          value={fmtTRY(sgk?.mean_sgk_exposure_mid ?? 0)}
          valueColor={ACCENT_LOCAL}
        />
        <KpiCard
          label="Total Copayment (OOP)"
          value={fmtTRY(copay?.total_copay_mid ?? 0)}
          valueColor="#B45309"
          sub={`${fmtTRY2(copay?.mean_copay_mid ?? 0)} / patient`}
        />
        <KpiCard
          label="Top 10% Cost Share"
          value={fmtPct(conc?.top_10pct_cost_share ?? 0)}
          valueColor={conc && conc.top_10pct_cost_share > 50 ? "#B91C1C" : "#B45309"}
          sub={`${conc?.top_10pct_patients ?? 0} patients`}
        />
      </div>

      <Surface variant="base" padding="lg">
        <h3 className="text-sm font-semibold uppercase tracking-wider mb-1" style={{ color: ACCENT_LOCAL }}>
          Cost Distribution (Per Patient)
        </h3>
        <p className="text-xs mb-4" style={{ color: "#A1A1AA" }}>
          Median: {fmtTRY(sut.median_cost_mid)} &middot; Mean: {fmtTRY(sut.mean_cost_mid)} &middot;
          P10: {fmtTRY(sut.cost_distribution?.p10 ?? 0)} &middot; P90: {fmtTRY(sut.cost_distribution?.p90 ?? 0)}
        </p>
        <div className="w-full h-3 rounded-full overflow-hidden" style={{ background: theme.accentAlpha(0.06) }}>
          {(() => {
            const p10 = sut.cost_distribution?.p10 ?? 0;
            const p90 = sut.cost_distribution?.p90 ?? 1;
            const maxVal = sut.cost_distribution?.p90 ?? 1;
            const median = sut.median_cost_mid;
            const medianPct = maxVal > 0 ? Math.min((median / maxVal) * 100, 100) : 50;
            return (
              <div className="relative h-full" style={{ width: "100%" }}>
                <div
                  className="absolute h-full rounded-full"
                  style={{
                    left: `${maxVal > 0 ? (p10 / maxVal) * 100 : 0}%`,
                    right: `${maxVal > 0 ? 100 - (p90 / maxVal) * 100 : 0}%`,
                    background: `linear-gradient(90deg, ${ACCENT_LOCAL}33, ${ACCENT_LOCAL}88)`,
                  }}
                />
                <div
                  className="absolute top-0 w-0.5 h-full"
                  style={{ left: `${medianPct}%`, background: ACCENT_LOCAL }}
                />
              </div>
            );
          })()}
        </div>
      </Surface>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Surface variant="base" padding="lg">
          <h3 className="text-sm font-semibold uppercase tracking-wider mb-4" style={{ color: ACCENT_LOCAL }}>
            Cost Tier Distribution
          </h3>
          <div className="flex items-center gap-4">
            <div style={{ width: 160, height: 160 }}>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={tierData}
                    cx="50%"
                    cy="50%"
                    innerRadius={45}
                    outerRadius={72}
                    dataKey="value"
                    stroke="none"
                  >
                    {tierData.map((entry, i) => (
                      <Cell key={i} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value) => [`${value ?? 0} patients`, ""]}
                    contentStyle={{
                      background: "rgba(255,255,255,0.95)",
                      border: `1px solid ${theme.accentAlpha(0.15)}`,
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="flex-1 space-y-1.5">
              {tierData.map((t) => (
                <div key={t.name} className="flex items-center gap-2 text-xs">
                  <span className="w-2.5 h-2.5 rounded-sm shrink-0" style={{ background: t.color }} />
                  <span className="flex-1" style={{ color: "#71717A" }}>{t.name}</span>
                  <span className="font-semibold" style={{ color: "#1A1A1A" }}>{t.value}</span>
                  <span style={{ color: "#A1A1AA" }}>
                    ({sut.n_patients > 0 ? fmtPct((t.value / sut.n_patients) * 100) : "0%"})
                  </span>
                </div>
              ))}
            </div>
          </div>
        </Surface>

        <Surface variant="base" padding="lg">
          <h3 className="text-sm font-semibold uppercase tracking-wider mb-4" style={{ color: ACCENT_LOCAL }}>
            Cost by Category (Midpoint)
          </h3>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={categoryData} layout="vertical" margin={{ left: 0, right: 8, top: 0, bottom: 0 }}>
              <CartesianGrid stroke="#F4F4F5" horizontal={false} opacity={0.08} />
              <XAxis type="number" tick={{ fill: "#71717A", fontSize: 12 }} tickFormatter={(v: number) => fmtTRY(v)} />
              <YAxis type="category" dataKey="name" tick={{ fill: "#71717A", fontSize: 12 }} width={80} />
              <Tooltip
                formatter={(value) => [fmtTRY2(Number(value ?? 0)), "Total (Cohort)"]}
                contentStyle={{
                  background: "rgba(255,255,255,0.95)",
                  border: `1px solid ${theme.accentAlpha(0.15)}`,
                  borderRadius: 8,
                  fontSize: 12,
                }}
              />
              <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={20}>
                {categoryData.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Surface>
      </div>

      {sut.top_5_high_cost && sut.top_5_high_cost.length > 0 && (
        <Surface variant="base" padding="lg">
          <h3 className="text-sm font-semibold uppercase tracking-wider mb-3" style={{ color: ACCENT_LOCAL }}>
            Top 5 Highest-Cost Patients
          </h3>
          <DataTable>
              <thead>
                <tr>
                  <th className="text-left">Rank</th>
                  <th className="text-left">Patient ID</th>
                  <th className="text-right tabular-nums">Est. Cost (Mid)</th>
                  <th className="text-center">Tier</th>
                  <th className="text-right tabular-nums">Visits</th>
                  <th className="text-right tabular-nums">Prescriptions</th>
                </tr>
              </thead>
              <tbody>
                {sut.top_5_high_cost.map((p, i) => (
                  <tr key={p.patient_id}>
                    <td className="text-left text-xs font-semibold" style={{ color: ACCENT_LOCAL }}>#{i + 1}</td>
                    <td className="text-left text-sm font-mono" style={{ color: "#1A1A1A" }}>{p.patient_id}</td>
                    <td className="text-right text-sm font-semibold tabular-nums" style={{ color: "#1A1A1A" }}>{fmtTRY2(p.cost_mid)}</td>
                    <td className="text-center">
                      <span
                        className="inline-block rounded-full px-2 py-0.5 text-xs font-semibold"
                        style={{
                          background: `${TIER_COLORS[p.cost_tier] || "#A1A1AA"}18`,
                          color: TIER_COLORS[p.cost_tier] || "#A1A1AA",
                        }}
                      >
                        {p.cost_tier}
                      </span>
                    </td>
                    <td className="text-right text-sm tabular-nums" style={{ color: "#71717A" }}>{p.n_visits}</td>
                    <td className="text-right text-sm tabular-nums" style={{ color: "#71717A" }}>{p.n_prescriptions}</td>
                  </tr>
                ))}
              </tbody>
          </DataTable>
        </Surface>
      )}

      <Surface
        variant="soft"
        padding="md"
        style={{ background: theme.accentAlpha(0.03), borderColor: theme.accentAlpha(0.12) }}
      >
        <p className="text-xs leading-relaxed text-[var(--text-secondary)]">
          <strong className="text-[var(--text-secondary)]">Methodology:</strong> SGK exposure is the midpoint of SUT min/max cost estimates per patient, aggregated across the cohort.
          Lab and visit prices are from EK-2B gazette (7,129 procedures); material prices from EK-3 annexes (4,385 items).
          Drug costs use estimated tier ranges (basic/moderate/specialty) — not actual ITS/IEGM reference prices.
          Copayment rates are from gazette JSON. All figures are SUT-ceiling estimates, not actual hospital charges.
        </p>
      </Surface>
    </div>
  );
}
