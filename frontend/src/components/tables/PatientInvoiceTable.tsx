"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getRevenueRecovery, getSutPatients } from "@/lib/api/sut";
import type { CohortRecoverySummary } from "@/lib/domains/sut";
import type { PatientMeta } from "@/lib/domains/patient";
import { DataTable, Eyebrow, Surface } from "@/components/primitives";
import { fmtTRY2, fmtPriorityLabel, fmtNum } from "@/components/tabs/sut/shared";
import { buildSutPatientHref } from "@/lib/constants";

interface PatientRow {
  patient_id: string;
  age: number | null;
  sex: string | null;
  total_recoverable_try: number | null;
  priority: string | null;
  action_count: number | null;
  top_action_type: string | null;
}

export default function PatientInvoiceTable() {
  const router = useRouter();
  const [rows, setRows] = useState<PatientRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        setLoading(true);
        setError(null);

        const [patientsData, recoveryData] = await Promise.all([
          getSutPatients().catch(() => null),
          getRevenueRecovery().catch(() => null),
        ]);

        if (cancelled) return;

        const metaLookup = new Map<string, PatientMeta>();
        patientsData?.patient_meta?.forEach((m) => {
          metaLookup.set(m.patient_id, m);
        });

        const recovery = recoveryData as CohortRecoverySummary | null;
        const topMap = new Map<string, CohortRecoverySummary["top_patients"][number]>();
        recovery?.top_patients?.forEach((p) => {
          topMap.set(p.patient_id, p);
        });

        const allIds = patientsData?.patients ?? recovery?.top_patients?.map((p) => p.patient_id) ?? [];

        const merged: PatientRow[] = allIds.map((pid) => {
          const meta = metaLookup.get(pid);
          const top = topMap.get(pid);
          return {
            patient_id: pid,
            age: meta?.age ?? null,
            sex: meta?.sex ?? null,
            total_recoverable_try: top?.total_recoverable_try ?? null,
            priority: top?.priority ?? null,
            action_count: top?.action_count ?? null,
            top_action_type: top?.top_action_type ?? null,
          };
        });

        setRows(merged);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load patient data");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <Surface variant="base" padding="lg">
        <Eyebrow tone="muted">Patient invoices</Eyebrow>
        <p className="mt-3 text-sm text-[var(--text-secondary)]">Loading patient data…</p>
      </Surface>
    );
  }

  if (error) {
    return (
      <Surface variant="base" padding="lg">
        <Eyebrow tone="muted">Patient invoices</Eyebrow>
        <p className="mt-3 text-sm text-[var(--text-danger)]">{error}</p>
      </Surface>
    );
  }

  if (rows.length === 0) {
    return (
      <Surface variant="base" padding="lg">
        <Eyebrow tone="muted">Patient invoices</Eyebrow>
        <p className="mt-3 text-sm text-[var(--text-secondary)]">No patients found in the current cohort.</p>
      </Surface>
    );
  }

  return (
    <Surface variant="base" padding="lg" className="space-y-4">
      <div className="flex items-center justify-between">
        <Eyebrow tone="muted">Patient invoices</Eyebrow>
        <span className="text-xs text-[var(--text-muted)]">
          {rows.length} patient{rows.length === 1 ? "" : "s"}
        </span>
      </div>

      <DataTable minWidth={720} className="text-[0.82rem]">
        <thead>
          <tr>
            <th>Patient ID</th>
            <th>Age</th>
            <th>Sex</th>
            <th className="num-col tabular-nums text-right">Recoverable</th>
            <th>Priority</th>
            <th className="num-col tabular-nums text-right">Actions</th>
            <th>Top action</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.patient_id}
              className="cursor-pointer hover:bg-[var(--surface-tint)] transition-colors"
              onClick={() => router.push(buildSutPatientHref(row.patient_id))}
            >
              <td className="font-mono text-xs font-medium">{row.patient_id}</td>
              <td>{row.age ?? "—"}</td>
              <td className="capitalize">{row.sex ?? "—"}</td>
              <td className="num-col tabular-nums text-right font-semibold text-[var(--text-primary)]">
                {row.total_recoverable_try !== null ? fmtTRY2(row.total_recoverable_try) : "—"}
              </td>
              <td>
                {row.priority ? (
                  <span
                    className="inline-flex rounded-full px-2 py-0.5 text-[0.7rem] font-semibold uppercase tracking-wide"
                    style={{
                      background:
                        row.priority === "high"
                          ? "rgba(185,28,28,0.1)"
                          : row.priority === "medium"
                            ? "rgba(217,119,6,0.1)"
                            : "rgba(5,150,105,0.1)",
                      color:
                        row.priority === "high"
                          ? "#B91C1C"
                          : row.priority === "medium"
                            ? "#D97706"
                            : "var(--success)",
                    }}
                  >
                    {fmtPriorityLabel(row.priority)}
                  </span>
                ) : (
                  "—"
                )}
              </td>
              <td className="num-col tabular-nums text-right">
                {row.action_count !== null ? fmtNum(row.action_count) : "—"}
              </td>
              <td className="text-[var(--text-secondary)]">{row.top_action_type ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </DataTable>
    </Surface>
  );
}
