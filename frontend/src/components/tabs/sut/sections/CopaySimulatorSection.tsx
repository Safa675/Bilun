"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import { simulateCopay } from "@/lib/api/sut";
import type { CopaySimulateRequest, CopaySimulateResult } from "@/lib/domains/sut";
import { theme } from "@/lib/theme";
import {
  ACCENT_LOCAL,
  FACILITY_TIERS,
  PATIENT_CATEGORIES,
  fmtTRY2,
  KpiCard,
} from "../shared";
import { Chip, Surface } from "@/components/primitives";

export function CopaySimulatorSection() {
  const [facilityTier, setFacilityTier] = useState("2_3_basamak_ozel");
  const [patientCategory, setPatientCategory] = useState("diger");
  const [nVisits, setNVisits] = useState(3);
  const [rxCost, setRxCost] = useState(500);
  const [nPrescriptions, setNPrescriptions] = useState(2);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CopaySimulateResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const handleSimulate = useCallback(async () => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);

    try {
      const req: CopaySimulateRequest = {
        facility_tier: facilityTier,
        patient_category: patientCategory,
        n_visits: nVisits,
        rx_cost: rxCost,
        n_prescriptions: nPrescriptions,
      };
      const res = await simulateCopay(req, { signal: controller.signal });
      if (!controller.signal.aborted) {
        setResult(res);
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      setError(err instanceof Error ? err.message : "Simulation failed");
    } finally {
      if (abortRef.current === controller) {
        setLoading(false);
        abortRef.current = null;
      }
    }
  }, [facilityTier, patientCategory, nVisits, rxCost, nPrescriptions]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const breakdownData = result
    ? [
        { name: "Visit Copay", value: result.visit.copay_total, color: theme.accent },
        { name: "Drug % Copay", value: result.drug.rx_copay_percentage, color: "#B45309" },
        { name: "Drug Flat Fee", value: result.drug.rx_copay_flat, color: "#B91C1C" },
      ].filter((d) => d.value > 0)
    : [];

  return (
    <div className="space-y-5">
      <Surface variant="base" padding="lg">
        <h3 className="text-sm font-semibold uppercase tracking-wider mb-4" style={{ color: ACCENT_LOCAL }}>
          Patient Scenario
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: "#71717A" }}>Facility Tier</label>
            <select
              value={facilityTier}
              onChange={(e) => setFacilityTier(e.target.value)}
              className="sut-input"
            >
              {FACILITY_TIERS.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: "#71717A" }}>Patient Category</label>
            <select
              value={patientCategory}
              onChange={(e) => setPatientCategory(e.target.value)}
              className="sut-input"
            >
              {PATIENT_CATEGORIES.map((c) => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: "#71717A" }}>Number of Visits</label>
            <input
              type="number"
              value={nVisits}
              onChange={(e) => setNVisits(Number(e.target.value))}
              className="sut-input"
              min="0"
              max="365"
            />
          </div>
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: "#71717A" }}>Total Drug Cost (TRY)</label>
            <input
              type="number"
              value={rxCost}
              onChange={(e) => setRxCost(Number(e.target.value))}
              className="sut-input"
              min="0"
              step="50"
            />
          </div>
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: "#71717A" }}>Prescriptions</label>
            <input
              type="number"
              value={nPrescriptions}
              onChange={(e) => setNPrescriptions(Number(e.target.value))}
              className="sut-input"
              min="0"
              max="100"
            />
          </div>
          <div className="flex items-end">
            <button
              type="button"
              onClick={handleSimulate}
              disabled={loading}
              className="sut-btn-primary w-full"
            >
              {loading ? "Simulating..." : "Simulate"}
            </button>
          </div>
        </div>
      </Surface>

      {error && (
        <Surface variant="soft" padding="md">
          <Chip variant="danger">{error}</Chip>
        </Surface>
      )}

      {result && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <KpiCard
              label="Total Out-of-Pocket"
              value={fmtTRY2(result.total_copay_mid)}
              valueColor="#B91C1C"
            />
            <KpiCard
              label="Visit Copayment"
              value={fmtTRY2(result.visit.copay_total)}
              valueColor={ACCENT_LOCAL}
              sub={`${fmtTRY2(result.visit.copay_per_visit)} x ${result.n_visits} visits`}
            />
            <KpiCard
              label="Drug Copayment"
              value={fmtTRY2(result.drug.rx_copay_total)}
              valueColor="#B45309"
              sub={`${(result.drug.rx_copay_rate * 100).toFixed(0)}% rate`}
            />
            <KpiCard
              label="Copay Range"
              value={`${fmtTRY2(result.total_copay_min)} - ${fmtTRY2(result.total_copay_max)}`}
              valueColor="#71717A"
              sub="min - max"
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <Surface variant="base" padding="lg">
              <h3 className="text-sm font-semibold uppercase tracking-wider mb-4" style={{ color: ACCENT_LOCAL }}>
                Copayment Breakdown
              </h3>
              {breakdownData.length > 0 ? (
                <div className="flex items-center gap-4">
                  <div style={{ width: 140, height: 140 }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={breakdownData}
                          cx="50%"
                          cy="50%"
                          innerRadius={40}
                          outerRadius={65}
                          dataKey="value"
                          stroke="none"
                        >
                          {breakdownData.map((entry, i) => (
                            <Cell key={i} fill={entry.color} />
                          ))}
                        </Pie>
                        <Tooltip
                          formatter={(value) => [fmtTRY2(Number(value ?? 0)), ""]}
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
                  <div className="flex-1 space-y-2">
                    {breakdownData.map((d) => (
                      <div key={d.name} className="flex items-center gap-2 text-xs">
                        <span className="w-2.5 h-2.5 rounded-sm shrink-0" style={{ background: d.color }} />
                        <span className="flex-1" style={{ color: "#71717A" }}>{d.name}</span>
                        <span className="font-semibold" style={{ color: "#1A1A1A" }}>{fmtTRY2(d.value)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="text-sm text-[var(--text-secondary)]">No copayment components</p>
              )}
            </Surface>

            <Surface variant="base" padding="lg">
              <h3 className="text-sm font-semibold uppercase tracking-wider mb-4" style={{ color: ACCENT_LOCAL }}>
                Calculation Detail
              </h3>
              <div className="space-y-3 text-sm">
                <div className="flex justify-between" style={{ color: "#71717A" }}>
                  <span>Visit copay per visit</span>
                  <span className="font-semibold" style={{ color: "#1A1A1A" }}>{fmtTRY2(result.visit.copay_per_visit)}</span>
                </div>
                <div className="flex justify-between" style={{ color: "#71717A" }}>
                  <span>Visit copay ({result.n_visits} visits)</span>
                  <span className="font-semibold" style={{ color: "#1A1A1A" }}>{fmtTRY2(result.visit.copay_total)}</span>
                </div>
                <hr style={{ borderColor: theme.accentAlpha(0.08) }} />
                <div className="flex justify-between" style={{ color: "#71717A" }}>
                  <span>Drug copay rate</span>
                  <span className="font-semibold" style={{ color: "#1A1A1A" }}>{(result.drug.rx_copay_rate * 100).toFixed(0)}%</span>
                </div>
                <div className="flex justify-between" style={{ color: "#71717A" }}>
                  <span>Drug % copay</span>
                  <span className="font-semibold" style={{ color: "#1A1A1A" }}>{fmtTRY2(result.drug.rx_copay_percentage)}</span>
                </div>
                <div className="flex justify-between" style={{ color: "#71717A" }}>
                  <span>Drug flat fee ({nPrescriptions} Rx)</span>
                  <span className="font-semibold" style={{ color: "#1A1A1A" }}>{fmtTRY2(result.drug.rx_copay_flat)}</span>
                </div>
                <hr style={{ borderColor: theme.accentAlpha(0.08) }} />
                <div className="flex justify-between font-bold" style={{ color: "#1A1A1A" }}>
                  <span>Total OOP (Mid)</span>
                  <span style={{ color: "#B91C1C" }}>{fmtTRY2(result.total_copay_mid)}</span>
                </div>
              </div>
            </Surface>
          </div>
        </>
      )}
    </div>
  );
}
